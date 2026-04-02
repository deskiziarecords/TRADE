"""
position_sizing_library.py
Complete position sizing algorithms for trading systems
"""

import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import warnings

# ============================================================================
# 1. RISK OF RUIN
# ============================================================================

def risk_of_ruin(win_rate: float, risk_per_trade: float, target_multiple: float) -> float:
    """
    Calculate probability of ruin before reaching target.
    
    Args:
        win_rate: Probability of winning trade (0.0 to 1.0)
        risk_per_trade: Fraction of capital risked per trade (0.0 to 1.0)
        target_multiple: Target profit as multiple of starting capital (e.g., 2.0 = 100% gain)
    
    Returns:
        Probability of ruin (0.0 to 1.0)
    
    Formula: P(ruin) = ( (1 - win_rate) / (win_rate) ) ^ (target / risk)
    """
    if win_rate <= 0.0 or win_rate >= 1.0:
        return 1.0
    
    # Correct formula for risk of ruin with fixed fractional betting
    risk_per_trade = min(risk_per_trade, 0.25)  # Cap at 25% per trade
    
    # Kelly-based ruin probability
    kelly_fraction = 2 * win_rate - 1
    if kelly_fraction <= 0:
        return 1.0
    
    # Calculate probability of ruin
    ruin_prob = ((1 - win_rate) / win_rate) ** (target_multiple / risk_per_trade)
    
    return min(ruin_prob, 1.0)


def maximum_safe_risk(win_rate: float, target_multiple: float, max_ruin_prob: float = 0.05) -> float:
    """
    Calculate maximum risk per trade given ruin probability constraint.
    
    Args:
        win_rate: Probability of winning trade
        target_multiple: Target profit multiple
        max_ruin_prob: Maximum acceptable ruin probability (e.g., 0.05 = 5%)
    
    Returns:
        Maximum safe risk per trade as fraction of capital
    """
    if win_rate <= 0.5:
        return 0.0  # Can't risk with negative edge
    
    # Solve for risk per trade: ruin_prob = ((1-p)/p)^(target/risk)
    # risk = target / (log(ruin_prob) / log((1-p)/p))
    risk = target_multiple / (np.log(max_ruin_prob) / np.log((1 - win_rate) / win_rate))
    
    return min(risk, 0.25)  # Cap at 25%


# ============================================================================
# 2. VOLATILITY TARGETING
# ============================================================================

def calculate_ewma_vol(atr_history: List[float], window: int = 20, lambda_decay: float = 0.94) -> float:
    """
    Calculate Exponentially Weighted Moving Average volatility.
    
    Args:
        atr_history: Historical ATR values (most recent last)
        window: Effective lookback window
        lambda_decay: Decay factor (0.94 is typical for daily data)
    
    Returns:
        Current EWMA volatility estimate
    """
    if not atr_history:
        return 1.0
    
    # Use only recent data
    recent_atr = atr_history[-window:] if len(atr_history) > window else atr_history
    
    # Calculate weights (exponential decay)
    n = len(recent_atr)
    weights = np.array([lambda_decay ** (n - 1 - i) for i in range(n)])
    weights = weights / weights.sum()
    
    # Calculate weighted average
    ewma_vol = np.sum(weights * np.array(recent_atr))
    
    return max(ewma_vol, 0.0001)  # Prevent division by zero


def volatility_targeting(
    atr_history: List[float], 
    target_vol: float = 0.15, 
    max_scaling: float = 3.0,
    min_scaling: float = 0.2
) -> float:
    """
    Calculate position scaling factor to maintain constant portfolio volatility.
    
    Args:
        atr_history: Historical ATR values
        target_vol: Target annualized volatility (e.g., 0.15 = 15%)
        max_scaling: Maximum position scaling factor
        min_scaling: Minimum position scaling factor
    
    Returns:
        Scaling factor to apply to position size
    """
    current_vol = calculate_ewma_vol(atr_history, 20)
    
    if current_vol <= 0:
        return 1.0
    
    scaling = target_vol / current_vol
    
    # Cap scaling to prevent extreme positions
    scaling = np.clip(scaling, min_scaling, max_scaling)
    
    return scaling


# ============================================================================
# 3. ADAPTIVE KELLY
# ============================================================================

class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING = "trending"
    CHOPPY = "choppy"
    CRISIS = "crisis"
    BULL = "bull"
    BEAR = "bear"


class AdaptiveKelly:
    """
    Kelly criterion with regime-adaptive parameters.
    More aggressive in trending markets, conservative in choppy/crisis.
    """
    
    def __init__(self, base_lambda: float = 0.25, regime_lambda_multipliers: Optional[dict] = None):
        """
        Args:
            base_lambda: Base Kelly fraction (0.25 = quarter Kelly)
            regime_lambda_multipliers: Dict mapping regimes to multipliers
        """
        self.base_lambda = base_lambda
        
        # Default regime multipliers
        self.regime_multipliers = {
            MarketRegime.TRENDING: 1.2,   # More aggressive in trends
            MarketRegime.BULL: 1.1,        # Slightly more aggressive in bull
            MarketRegime.CHOPPY: 0.6,      # Conservative in chop
            MarketRegime.BEAR: 0.4,        # Very conservative in bear
            MarketRegime.CRISIS: 0.1,      # Capital preservation in crisis
        }
        
        if regime_lambda_multipliers:
            self.regime_multipliers.update(regime_lambda_multipliers)
    
    def calculate(self, win_rate: float, win_loss_ratio: float, regime: MarketRegime) -> float:
        """
        Calculate adaptive Kelly fraction.
        
        Formula: f* = lambda * (p * b - (1-p)) / b
        where p = win rate, b = win/loss ratio
        
        Args:
            win_rate: Probability of winning trade (0.0 to 1.0)
            win_loss_ratio: Average win / average loss (>= 0)
            regime: Current market regime
        
        Returns:
            Optimal fraction of capital to risk
        """
        if win_rate <= 0.0 or win_loss_ratio <= 0.0:
            return 0.0
        
        # Standard Kelly formula
        kelly_fraction = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        if kelly_fraction <= 0.0:
            return 0.0
        
        # Apply regime multiplier
        regime_multiplier = self.regime_multipliers.get(regime, 1.0)
        
        # Apply base lambda and cap
        final_fraction = self.base_lambda * kelly_fraction * regime_multiplier
        
        return min(final_fraction, 0.25)  # Cap at 25%


# ============================================================================
# 4. CORRELATION-ADJUSTED SIZING
# ============================================================================

def correlation_adjusted_size(
    position_sizes: np.ndarray,
    correlation_matrix: np.ndarray,
    risk_budget: float = 1.0,
    max_concentration: float = 0.25
) -> np.ndarray:
    """
    Adjust position sizes based on correlations to prevent hidden concentration.
    
    Uses risk parity approach: positions scaled so that each contributes equally
    to portfolio risk.
    
    Args:
        position_sizes: Current position sizes as fractions of capital
        correlation_matrix: NxN correlation matrix between positions
        risk_budget: Total risk budget (1.0 = full risk capacity)
        max_concentration: Maximum single position size as fraction of capital
    
    Returns:
        Adjusted position sizes
    """
    n = len(position_sizes)
    
    if n == 0:
        return np.array([])
    
    # Calculate portfolio volatility contribution of each position
    vol_contributions = np.zeros(n)
    
    for i in range(n):
        # Marginal contribution to portfolio variance
        marginal_contrib = 0.0
        for j in range(n):
            marginal_contrib += position_sizes[i] * position_sizes[j] * correlation_matrix[i, j]
        vol_contributions[i] = np.sqrt(max(marginal_contrib, 0))
    
    # Normalize to risk budget
    total_risk = np.sum(vol_contributions)
    
    if total_risk > 0:
        adjusted_sizes = position_sizes * (risk_budget / total_risk)
    else:
        adjusted_sizes = position_sizes.copy()
    
    # Apply concentration cap
    adjusted_sizes = np.minimum(adjusted_sizes, max_concentration)
    
    return adjusted_sizes


def calculate_portfolio_volatility(
    position_sizes: np.ndarray,
    correlation_matrix: np.ndarray,
    individual_vols: np.ndarray
) -> float:
    """
    Calculate total portfolio volatility given correlations.
    
    Args:
        position_sizes: Position sizes
        correlation_matrix: Correlation matrix
        individual_vols: Individual asset volatilities
    
    Returns:
        Portfolio volatility
    """
    n = len(position_sizes)
    cov_matrix = np.outer(individual_vols, individual_vols) * correlation_matrix
    portfolio_var = position_sizes @ cov_matrix @ position_sizes
    return np.sqrt(max(portfolio_var, 0))


# ============================================================================
# 5. BAYESIAN SIZER
# ============================================================================

from scipy.stats import beta, gamma

@dataclass
class TradeResult:
    """Trade result data structure"""
    is_win: bool
    profit_loss: float
    timestamp: Optional[float] = None


class BayesianSizer:
    """
    Bayesian adaptive position sizer that updates beliefs with each trade.
    Naturally becomes more conservative when uncertain.
    """
    
    def __init__(
        self,
        prior_win_rate_alpha: float = 10.0,
        prior_win_rate_beta: float = 10.0,
        prior_win_loss_ratio_shape: float = 5.0,
        prior_win_loss_ratio_scale: float = 1.0
    ):
        """
        Initialize with prior distributions.
        
        Args:
            prior_win_rate_alpha: Beta prior alpha (successes)
            prior_win_rate_beta: Beta prior beta (failures)
            prior_win_loss_ratio_shape: Gamma prior shape parameter
            prior_win_loss_ratio_scale: Gamma prior scale parameter
        """
        # Prior distribution for win rate
        self.win_rate_prior = beta(prior_win_rate_alpha, prior_win_rate_beta)
        
        # Prior distribution for win/loss ratio
        self.wlr_prior = gamma(prior_win_loss_ratio_shape, scale=prior_win_loss_ratio_scale)
        
        # Track trade history
        self.trades: List[TradeResult] = []
    
    def update(self, trade_result: TradeResult) -> None:
        """
        Update distributions with new trade result.
        
        Args:
            trade_result: Trade outcome
        """
        self.trades.append(trade_result)
        
        # Update win rate distribution (Beta is conjugate for Bernoulli)
        wins = sum(1 for t in self.trades if t.is_win)
        losses = len(self.trades) - wins
        
        # Update Beta distribution parameters
        self.win_rate_prior = beta(
            self.win_rate_prior.args[0] + wins,
            self.win_rate_prior.args[1] + losses
        )
        
        # Update win/loss ratio distribution using wins and losses separately
        # This is a simplified approach; full Bayesian updating is complex
        total_wins = sum(t.profit_loss for t in self.trades if t.is_win and t.profit_loss > 0)
        total_losses = abs(sum(t.profit_loss for t in self.trades if not t.is_win and t.profit_loss < 0))
        
        if total_losses > 0 and total_wins > 0:
            avg_win = total_wins / max(wins, 1)
            avg_loss = total_losses / max(losses, 1)
            current_wlr = avg_win / avg_loss
            
            # Update Gamma distribution (simplified)
            self.wlr_prior = gamma(
                self.wlr_prior.args[0] + 0.1,  # Slow adaptation
                scale=self.wlr_prior.args[1] * 0.9 + current_wlr * 0.1
            )
    
    def current_kelly(self, lambda_frac: float = 0.25) -> float:
        """
        Calculate current Kelly fraction using posterior expectations.
        
        Args:
            lambda_frac: Kelly fraction multiplier (0.25 = quarter Kelly)
        
        Returns:
            Optimal fraction of capital to risk
        """
        # Get expected values from posterior distributions
        expected_win_rate = self.win_rate_prior.mean()
        expected_wlr = self.wlr_prior.mean()
        
        if expected_win_rate <= 0.5 or expected_wlr <= 0:
            return 0.0
        
        # Standard Kelly formula
        kelly = (expected_win_rate * expected_wlr - (1 - expected_win_rate)) / expected_wlr
        
        # Apply uncertainty penalty
        # Higher uncertainty (variance) reduces position size
        win_rate_uncertainty = self.win_rate_prior.var()
        wlr_uncertainty = self.wlr_prior.var()
        
        uncertainty_penalty = 1.0 / (1.0 + 10.0 * (win_rate_uncertainty + wlr_uncertainty))
        
        return lambda_frac * kelly * uncertainty_penalty
    
    def confidence_interval(self, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Get confidence interval for win rate.
        
        Args:
            confidence: Confidence level (0.0 to 1.0)
        
        Returns:
            (lower_bound, upper_bound) for win rate
        """
        alpha = 1 - confidence
        return self.win_rate_prior.ppf(alpha / 2), self.win_rate_prior.ppf(1 - alpha / 2)


# ============================================================================
# 6. MAXIMUM ADVERSE EXCURSION
# ============================================================================

def max_adverse_excursion(
    stop_distance: float,
    historical_mae: List[float],
    percentile: float = 0.95
) -> float:
    """
    Calculate position sizing adjustment based on MAE analysis.
    
    MAE measures how far price moves against the position before eventual outcome.
    High MAE relative to stop distance indicates premature stop hits.
    
    Args:
        stop_distance: Current stop distance as fraction of entry (e.g., 0.02 = 2%)
        historical_mae: Historical maximum adverse excursions as fractions of entry
        percentile: Percentile to use for MAE (95th percentile typical)
    
    Returns:
        Scaling factor (lower = reduce position size)
    """
    if not historical_mae:
        return 1.0
    
    # Calculate typical adverse excursion
    typical_mae = np.percentile(historical_mae, percentile)
    
    if typical_mae <= 0:
        return 1.0
    
    # If typical MAE exceeds stop distance, reduce position size
    if typical_mae > stop_distance:
        # Scaling = stop_distance / typical_mae
        scaling = stop_distance / typical_mae
        return max(scaling, 0.25)  # Don't reduce below 25%
    
    return 1.0


# ============================================================================
# 7. ENTROPY UNCERTAINTY
# ============================================================================

def entropy_uncertainty(price_distribution: np.ndarray, normalize: bool = True) -> float:
    """
    Calculate Shannon entropy of price distribution to measure market uncertainty.
    
    High entropy = high uncertainty = reduce position size.
    Low entropy = clear direction = increase position size.
    
    Args:
        price_distribution: Probability distribution of price outcomes
        normalize: Whether to normalize to [0, 1] range
    
    Returns:
        Entropy value (0 = certain, high = uncertain)
    """
    # Convert to numpy array
    probs = np.array(price_distribution, dtype=np.float64)
    
    # Ensure probabilities sum to 1
    probs = probs / np.sum(probs)
    
    # Remove zero probabilities to avoid log(0)
    probs = probs[probs > 0]
    
    if len(probs) == 0:
        return 0.0
    
    # Calculate Shannon entropy
    entropy = -np.sum(probs * np.log(probs))
    
    if normalize:
        # Normalize to [0, 1] where 1 = maximum entropy (uniform distribution)
        max_entropy = np.log(len(probs))
        if max_entropy > 0:
            entropy = entropy / max_entropy
    
    return entropy


def uncertainty_scaling_factor(entropy: float, scaling_power: float = 2.0) -> float:
    """
    Convert entropy to position scaling factor.
    
    Args:
        entropy: Entropy value (0 to 1)
        scaling_power: How aggressively to scale (higher = more aggressive reduction)
    
    Returns:
        Scaling factor (1.0 = full size, 0.0 = no position)
    """
    # Higher entropy = smaller position
    scaling = 1.0 - (entropy ** scaling_power)
    return max(scaling, 0.1)  # Never reduce below 10%


# ============================================================================
# 8. OPTIMAL F (Ralph Vince)
# ============================================================================

def optimal_f(trades: List[float], max_loss: Optional[float] = None) -> float:
    """
    Calculate Optimal f as per Ralph Vince.
    
    Optimal f maximizes the geometric growth rate by finding the fraction
    of capital to risk per trade based on historical trade outcomes.
    
    Args:
        trades: List of trade profits/losses as fractions of capital
        max_loss: Optional maximum loss to use (uses worst historical if not provided)
    
    Returns:
        Optimal fraction of capital to risk per trade
    """
    if not trades:
        return 0.0
    
    # Convert to numpy array
    trades = np.array(trades, dtype=np.float64)
    
    # Find worst loss
    if max_loss is None:
        max_loss = abs(min(trades))
    
    if max_loss <= 0:
        return 0.0
    
    # Convert trades to multiples of max loss
    normalized_trades = trades / max_loss
    
    # Search for f that maximizes geometric mean
    def geometric_mean(f: float) -> float:
        """Calculate geometric mean for given f"""
        returns = 1.0 + f * normalized_trades
        # Filter out negative returns (avoid log of negative)
        returns = returns[returns > 0]
        if len(returns) == 0:
            return 0.0
        return np.exp(np.mean(np.log(returns)))
    
    # Grid search for optimal f
    f_values = np.linspace(0.01, 0.5, 100)
    gmeans = [geometric_mean(f) for f in f_values]
    
    optimal_f_value = f_values[np.argmax(gmeans)]
    
    return optimal_f_value


# ============================================================================
# 9. COMPREHENSIVE POSITION SIZER
# ============================================================================

class ComprehensivePositionSizer:
    """
    Combines multiple position sizing algorithms for robust capital allocation.
    """
    
    def __init__(self, initial_capital: float):
        self.capital = initial_capital
        self.trade_history: List[TradeResult] = []
        self.atr_history: List[float] = []
        self.mae_history: List[float] = []
        
        # Initialize components
        self.bayesian_sizer = BayesianSizer()
        self.adaptive_kelly = AdaptiveKelly()
    
    def calculate_position(
        self,
        win_rate_estimate: float,
        win_loss_ratio: float,
        atr: float,
        stop_distance: float,
        regime: MarketRegime,
        current_positions: Optional[np.ndarray] = None,
        correlation_matrix: Optional[np.ndarray] = None
    ) -> dict:
        """
        Calculate position size using multiple factors.
        
        Returns:
            Dictionary containing position size and all contributing factors
        """
        # 1. Bayesian Kelly (adapts with trade history)
        bayesian_kelly = self.bayesian_sizer.current_kelly()
        
        # 2. Regime-adaptive Kelly
        regime_kelly = self.adaptive_kelly.calculate(win_rate_estimate, win_loss_ratio, regime)
        
        # 3. Volatility targeting
        if self.atr_history:
            vol_scaling = volatility_targeting(self.atr_history)
        else:
            vol_scaling = 1.0
        
        # 4. MAE adjustment
        if self.mae_history:
            mae_scaling = max_adverse_excursion(stop_distance, self.mae_history)
        else:
            mae_scaling = 1.0
        
        # 5. Risk of ruin constraint
        max_risk_fraction = maximum_safe_risk(win_rate_estimate, 2.0, 0.05)
        
        # Combine factors
        raw_fraction = (
            bayesian_kelly * regime_kelly * vol_scaling * mae_scaling
        )
        
        # Apply risk of ruin cap
        risk_fraction = min(raw_fraction, max_risk_fraction)
        
        # Apply correlation adjustment if multiple positions
        if current_positions is not None and correlation_matrix is not None:
            new_position = np.array([risk_fraction])
            all_positions = np.concatenate([current_positions, new_position])
            adjusted = correlation_adjusted_size(all_positions, correlation_matrix)
            risk_fraction = adjusted[-1]
        
        # Calculate actual position size
        risk_amount = self.capital * risk_fraction
        notional_position = risk_amount / stop_distance
        
        return {
            'risk_fraction': risk_fraction,
            'risk_amount': risk_amount,
            'notional_position': notional_position,
            'components': {
                'bayesian_kelly': bayesian_kelly,
                'regime_kelly': regime_kelly,
                'vol_scaling': vol_scaling,
                'mae_scaling': mae_scaling,
                'max_risk_cap': max_risk_fraction
            }
        }
    
    def record_trade(self, trade_result: TradeResult, atr_at_time: float, mae: float) -> None:
        """Record trade outcome for adaptive learning"""
        self.trade_history.append(trade_result)
        self.atr_history.append(atr_at_time)
        self.mae_history.append(mae)
        self.bayesian_sizer.update(trade_result)
        
        # Update capital
        self.capital *= (1 + trade_result.profit_loss)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def example_usage():
    """Demonstrate usage of all position sizing algorithms"""
    
    print("=" * 60)
    print("POSITION SIZING LIBRARY - EXAMPLE USAGE")
    print("=" * 60)
    
    # 1. Risk of Ruin
    print("\n1. RISK OF RUIN")
    print("-" * 40)
    ruin_prob = risk_of_ruin(win_rate=0.55, risk_per_trade=0.02, target_multiple=2.0)
    print(f"Risk of ruin: {ruin_prob:.2%}")
    
    max_risk = maximum_safe_risk(win_rate=0.55, target_multiple=2.0, max_ruin_prob=0.05)
    print(f"Maximum safe risk per trade: {max_risk:.2%}")
    
    # 2. Volatility Targeting
    print("\n2. VOLATILITY TARGETING")
    print("-" * 40)
    atr_history = [0.12, 0.15, 0.18, 0.20, 0.22, 0.19, 0.16, 0.14, 0.13, 0.12]
    scaling = volatility_targeting(atr_history, target_vol=0.15)
    print(f"Volatility scaling factor: {scaling:.2f}x")
    
    # 3. Adaptive Kelly
    print("\n3. ADAPTIVE KELLY")
    print("-" * 40)
    kelly = AdaptiveKelly()
    kelly_fraction = kelly.calculate(win_rate=0.55, win_loss_ratio=1.5, regime=MarketRegime.TRENDING)
    print(f"Adaptive Kelly fraction: {kelly_fraction:.2%}")
    
    # 4. Bayesian Sizer
    print("\n4. BAYESIAN SIZER")
    print("-" * 40)
    bayesian = BayesianSizer()
    bayesian.update(TradeResult(is_win=True, profit_loss=0.10))
    bayesian.update(TradeResult(is_win=False, profit_loss=-0.05))
    bayesian.update(TradeResult(is_win=True, profit_loss=0.12))
    print(f"Bayesian Kelly fraction: {bayesian.current_kelly():.2%}")
    conf_interval = bayesian.confidence_interval()
    print(f"Win rate confidence interval: {conf_interval[0]:.2%} - {conf_interval[1]:.2%}")
    
    # 5. Optimal f
    print("\n5. OPTIMAL F")
    print("-" * 40)
    trades = [0.10, -0.05, 0.12, -0.03, 0.08, -0.04, 0.15, -0.02]
    opt_f = optimal_f(trades)
    print(f"Optimal f: {opt_f:.2%}")
    
    # 6. Entropy
    print("\n6. ENTROPY UNCERTAINTY")
    print("-" * 40)
    price_dist = [0.05, 0.10, 0.15, 0.20, 0.25, 0.15, 0.05, 0.03, 0.02]
    entropy = entropy_uncertainty(price_dist)
    print(f"Market entropy: {entropy:.3f}")
    uncertainty_scaling = uncertainty_scaling_factor(entropy)
    print(f"Uncertainty scaling factor: {uncertainty_scaling:.2f}x")
    
    # 7. Comprehensive Position Sizer
    print("\n7. COMPREHENSIVE POSITION SIZER")
    print("-" * 40)
    sizer = ComprehensivePositionSizer(initial_capital=100_000)
    
    result = sizer.calculate_position(
        win_rate_estimate=0.55,
        win_loss_ratio=1.5,
        atr=0.02,
        stop_distance=0.01,
        regime=MarketRegime.TRENDING,
        current_positions=None,
        correlation_matrix=None
    )
    
    print(f"Risk fraction: {result['risk_fraction']:.2%}")
    print(f"Risk amount: ${result['risk_amount']:,.2f}")
    print(f"Notional position: ${result['notional_position']:,.2f}")
    print("\nComponent breakdown:")
    for comp, value in result['components'].items():
        if isinstance(value, float):
            print(f"  {comp}: {value:.2%}")
    
    print("\n" + "=" * 60)
    print("All algorithms executed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    example_usage()
