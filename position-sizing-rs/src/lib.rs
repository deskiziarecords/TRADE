//! # Position Sizing Library
//!
//! Complete position sizing algorithms for trading systems.
//! Converted from Python — all algorithms are faithful translations.

use statrs::distribution::{Beta, ContinuousCDF};
use std::collections::HashMap;

// ============================================================================
// SHARED TYPES
// ============================================================================

/// A trade result recorded for adaptive learning.
#[derive(Debug, Clone)]
pub struct TradeResult {
    pub is_win: bool,
    pub profit_loss: f64,
    pub timestamp: Option<f64>,
}

/// Market regime classification.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum MarketRegime {
    Trending,
    Choppy,
    Crisis,
    Bull,
    Bear,
}

// ============================================================================
// 1. RISK OF RUIN
// ============================================================================

/// Calculate probability of ruin before reaching `target_multiple`.
///
/// Formula: P(ruin) = ((1 - p) / p) ^ (target / risk)
pub fn risk_of_ruin(win_rate: f64, risk_per_trade: f64, target_multiple: f64) -> f64 {
    if win_rate <= 0.0 || win_rate >= 1.0 { return 1.0; }
    let risk = risk_per_trade.min(0.25);
    let kelly_fraction = 2.0 * win_rate - 1.0;
    if kelly_fraction <= 0.0 { return 1.0; }
    let odds_ratio = (1.0 - win_rate) / win_rate;
    odds_ratio.powf(target_multiple / risk).min(1.0)
}

/// Calculate the maximum safe risk per trade given a ruin-probability constraint.
///
/// Solves `ruin_prob = ((1-p)/p)^(target/risk)` for `risk`.
pub fn maximum_safe_risk(win_rate: f64, target_multiple: f64, max_ruin_prob: f64) -> f64 {
    if win_rate <= 0.5 { return 0.0; }
    let odds_ratio = (1.0 - win_rate) / win_rate;
    let risk = target_multiple / (max_ruin_prob.ln() / odds_ratio.ln());
    risk.min(0.25)
}

// ============================================================================
// 2. VOLATILITY TARGETING
// ============================================================================

/// Exponentially Weighted Moving Average volatility.
///
/// `lambda_decay` of 0.94 is typical for daily data.
pub fn calculate_ewma_vol(atr_history: &[f64], window: usize, lambda_decay: f64) -> f64 {
    if atr_history.is_empty() { return 1.0; }
    let recent: &[f64] = if atr_history.len() > window {
        &atr_history[atr_history.len() - window..]
    } else {
        atr_history
    };
    let n = recent.len();
    let raw_weights: Vec<f64> = (0..n).map(|i| lambda_decay.powi((n - 1 - i) as i32)).collect();
    let weight_sum: f64 = raw_weights.iter().sum();
    let weights: Vec<f64> = raw_weights.iter().map(|w| w / weight_sum).collect();
    let ewma: f64 = weights.iter().zip(recent.iter()).map(|(w, v)| w * v).sum();
    ewma.max(0.0001)
}

/// Position scaling factor to maintain constant portfolio volatility.
pub fn volatility_targeting(
    atr_history: &[f64],
    target_vol: f64,
    max_scaling: f64,
    min_scaling: f64,
) -> f64 {
    let current_vol = calculate_ewma_vol(atr_history, 20, 0.94);
    if current_vol <= 0.0 { return 1.0; }
    (target_vol / current_vol).clamp(min_scaling, max_scaling)
}

// ============================================================================
// 3. ADAPTIVE KELLY
// ============================================================================

/// Kelly criterion with regime-adaptive parameters.
pub struct AdaptiveKelly {
    pub base_lambda: f64,
    pub regime_multipliers: HashMap<MarketRegime, f64>,
}

impl Default for AdaptiveKelly {
    fn default() -> Self { Self::new(0.25, None) }
}

impl AdaptiveKelly {
    pub fn new(base_lambda: f64, overrides: Option<HashMap<MarketRegime, f64>>) -> Self {
        let mut multipliers = HashMap::from([
            (MarketRegime::Trending, 1.2),
            (MarketRegime::Bull,     1.1),
            (MarketRegime::Choppy,   0.6),
            (MarketRegime::Bear,     0.4),
            (MarketRegime::Crisis,   0.1),
        ]);
        if let Some(ov) = overrides { multipliers.extend(ov); }
        Self { base_lambda, regime_multipliers: multipliers }
    }

    /// Adaptive Kelly fraction: `f* = λ × (p × b − (1 − p)) / b`
    pub fn calculate(&self, win_rate: f64, win_loss_ratio: f64, regime: MarketRegime) -> f64 {
        if win_rate <= 0.0 || win_loss_ratio <= 0.0 { return 0.0; }
        let kelly = (win_rate * win_loss_ratio - (1.0 - win_rate)) / win_loss_ratio;
        if kelly <= 0.0 { return 0.0; }
        let mult = self.regime_multipliers.get(&regime).copied().unwrap_or(1.0);
        (self.base_lambda * kelly * mult).min(0.25)
    }
}

// ============================================================================
// 4. CORRELATION-ADJUSTED SIZING
// ============================================================================

/// Adjust position sizes using a risk-parity approach over the correlation matrix.
///
/// `correlation_matrix` is a flat row-major N×N slice.
pub fn correlation_adjusted_size(
    position_sizes: &[f64],
    correlation_matrix: &[f64],
    risk_budget: f64,
    max_concentration: f64,
) -> Vec<f64> {
    let n = position_sizes.len();
    if n == 0 { return vec![]; }

    let vol_contributions: Vec<f64> = (0..n).map(|i| {
        let marginal: f64 = (0..n)
            .map(|j| position_sizes[i] * position_sizes[j] * correlation_matrix[i * n + j])
            .sum();
        marginal.max(0.0).sqrt()
    }).collect();

    let total_risk: f64 = vol_contributions.iter().sum();

    let mut adjusted: Vec<f64> = if total_risk > 0.0 {
        position_sizes.iter().map(|&s| s * (risk_budget / total_risk)).collect()
    } else {
        position_sizes.to_vec()
    };

    for s in &mut adjusted { *s = s.min(max_concentration); }
    adjusted
}

/// Total portfolio volatility given correlations and individual vols.
pub fn calculate_portfolio_volatility(
    position_sizes: &[f64],
    correlation_matrix: &[f64],
    individual_vols: &[f64],
) -> f64 {
    let n = position_sizes.len();
    let cov: Vec<f64> = (0..n).flat_map(|i| {
        (0..n).map(move |j| individual_vols[i] * individual_vols[j] * correlation_matrix[i * n + j])
    }).collect();
    let var: f64 = (0..n)
        .map(|i| position_sizes[i] * (0..n).map(|j| cov[i * n + j] * position_sizes[j]).sum::<f64>())
        .sum();
    var.max(0.0).sqrt()
}

// ============================================================================
// 5. BAYESIAN SIZER
// ============================================================================

/// Bayesian adaptive sizer — win rate modelled as Beta, win/loss ratio as Gamma.
pub struct BayesianSizer {
    win_rate_alpha: f64,
    win_rate_beta:  f64,
    wlr_shape: f64,
    wlr_scale: f64,
    pub trades: Vec<TradeResult>,
}

impl Default for BayesianSizer {
    fn default() -> Self { Self::new(10.0, 10.0, 5.0, 1.0) }
}

impl BayesianSizer {
    pub fn new(
        prior_wr_alpha: f64,
        prior_wr_beta:  f64,
        prior_wlr_shape: f64,
        prior_wlr_scale: f64,
    ) -> Self {
        Self {
            win_rate_alpha: prior_wr_alpha,
            win_rate_beta:  prior_wr_beta,
            wlr_shape: prior_wlr_shape,
            wlr_scale: prior_wlr_scale,
            trades: Vec::new(),
        }
    }

    /// Update posterior with a new trade.
    pub fn update(&mut self, trade: TradeResult) {
        self.trades.push(trade);

        let wins   = self.trades.iter().filter(|t| t.is_win).count() as f64;
        let losses = self.trades.len() as f64 - wins;

        // Beta conjugate update
        self.win_rate_alpha = 10.0 + wins;   // reset to prior + data
        self.win_rate_beta  = 10.0 + losses;

        let total_wins: f64 = self.trades.iter()
            .filter(|t| t.is_win && t.profit_loss > 0.0).map(|t| t.profit_loss).sum();
        let total_losses: f64 = self.trades.iter()
            .filter(|t| !t.is_win && t.profit_loss < 0.0).map(|t| t.profit_loss.abs()).sum();

        if total_wins > 0.0 && total_losses > 0.0 {
            let avg_win  = total_wins  / wins.max(1.0);
            let avg_loss = total_losses / losses.max(1.0);
            let current_wlr = avg_win / avg_loss;
            self.wlr_shape += 0.1;
            self.wlr_scale  = self.wlr_scale * 0.9 + current_wlr * 0.1;
        }
    }

    /// Beta posterior mean: α / (α + β)
    pub fn expected_win_rate(&self) -> f64 {
        self.win_rate_alpha / (self.win_rate_alpha + self.win_rate_beta)
    }

    /// Beta posterior variance: αβ / ((α+β)²(α+β+1))
    pub fn win_rate_variance(&self) -> f64 {
        let a = self.win_rate_alpha;
        let b = self.win_rate_beta;
        (a * b) / ((a + b).powi(2) * (a + b + 1.0))
    }

    /// Gamma posterior mean: shape × scale
    pub fn expected_wlr(&self) -> f64 { self.wlr_shape * self.wlr_scale }

    /// Gamma posterior variance: shape × scale²
    pub fn wlr_variance(&self) -> f64 { self.wlr_shape * self.wlr_scale.powi(2) }

    /// Kelly fraction penalised for posterior uncertainty.
    pub fn current_kelly(&self, lambda_frac: f64) -> f64 {
        let wr  = self.expected_win_rate();
        let wlr = self.expected_wlr();
        if wr <= 0.5 || wlr <= 0.0 { return 0.0; }
        let kelly = (wr * wlr - (1.0 - wr)) / wlr;
        if kelly <= 0.0 { return 0.0; }
        let penalty = 1.0 / (1.0 + 10.0 * (self.win_rate_variance() + self.wlr_variance()));
        lambda_frac * kelly * penalty
    }

    /// Confidence interval for win rate via Beta quantiles.
    pub fn confidence_interval(&self, confidence: f64) -> (f64, f64) {
        let dist = Beta::new(self.win_rate_alpha, self.win_rate_beta)
            .expect("Invalid Beta parameters");
        let alpha = 1.0 - confidence;
        (dist.inverse_cdf(alpha / 2.0), dist.inverse_cdf(1.0 - alpha / 2.0))
    }
}

// ============================================================================
// 6. MAXIMUM ADVERSE EXCURSION (MAE)
// ============================================================================

/// Position scaling from MAE analysis (minimum 25% of full size).
pub fn max_adverse_excursion(stop_distance: f64, historical_mae: &[f64], percentile: f64) -> f64 {
    if historical_mae.is_empty() { return 1.0; }
    let typical_mae = percentile_value(historical_mae, percentile);
    if typical_mae <= 0.0 { return 1.0; }
    if typical_mae > stop_distance {
        (stop_distance / typical_mae).max(0.25)
    } else {
        1.0
    }
}

fn percentile_value(data: &[f64], pct: f64) -> f64 {
    if data.is_empty() { return 0.0; }
    let mut sorted = data.to_vec();
    sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let idx = (pct * (sorted.len() - 1) as f64).round() as usize;
    sorted[idx.min(sorted.len() - 1)]
}

// ============================================================================
// 7. ENTROPY UNCERTAINTY
// ============================================================================

/// Shannon entropy of a price-outcome distribution, optionally normalised to [0, 1].
pub fn entropy_uncertainty(price_distribution: &[f64], normalize: bool) -> f64 {
    let total: f64 = price_distribution.iter().sum();
    if total == 0.0 { return 0.0; }
    let probs: Vec<f64> = price_distribution.iter()
        .map(|&p| p / total).filter(|&p| p > 0.0).collect();
    if probs.is_empty() { return 0.0; }
    let entropy: f64 = -probs.iter().map(|&p| p * p.ln()).sum::<f64>();
    if normalize {
        let max_e = (probs.len() as f64).ln();
        if max_e > 0.0 { return entropy / max_e; }
    }
    entropy
}

/// Convert entropy to a position scaling factor (minimum 10%).
pub fn uncertainty_scaling_factor(entropy: f64, scaling_power: f64) -> f64 {
    (1.0 - entropy.powf(scaling_power)).max(0.1)
}

// ============================================================================
// 8. OPTIMAL F (Ralph Vince)
// ============================================================================

/// Optimal f via grid search over the geometric growth rate.
pub fn optimal_f(trades: &[f64], max_loss: Option<f64>) -> f64 {
    if trades.is_empty() { return 0.0; }
    let worst = max_loss.unwrap_or_else(|| {
        trades.iter().cloned().fold(f64::INFINITY, f64::min).abs()
    });
    if worst <= 0.0 { return 0.0; }
    let normalised: Vec<f64> = trades.iter().map(|&t| t / worst).collect();
    let geometric_mean = |f: f64| -> f64 {
        let rets: Vec<f64> = normalised.iter().map(|&r| 1.0 + f * r).filter(|&r| r > 0.0).collect();
        if rets.is_empty() { return 0.0; }
        (rets.iter().map(|r| r.ln()).sum::<f64>() / rets.len() as f64).exp()
    };
    // Grid: 0.005, 0.010, ..., 0.500 (100 steps)
    (1..=100usize)
        .map(|i| i as f64 * 0.005)
        .max_by(|&a, &b| geometric_mean(a).partial_cmp(&geometric_mean(b)).unwrap_or(std::cmp::Ordering::Equal))
        .unwrap_or(0.0)
}

// ============================================================================
// 9. COMPREHENSIVE POSITION SIZER
// ============================================================================

#[derive(Debug)]
pub struct PositionComponents {
    pub bayesian_kelly: f64,
    pub regime_kelly:   f64,
    pub vol_scaling:    f64,
    pub mae_scaling:    f64,
    pub max_risk_cap:   f64,
}

#[derive(Debug)]
pub struct PositionResult {
    pub risk_fraction:     f64,
    pub risk_amount:       f64,
    pub notional_position: f64,
    pub components: PositionComponents,
}

/// Combines all algorithms into a single, adaptive position sizer.
pub struct ComprehensivePositionSizer {
    pub capital:       f64,
    pub trade_history: Vec<TradeResult>,
    pub atr_history:   Vec<f64>,
    pub mae_history:   Vec<f64>,
    bayesian_sizer: BayesianSizer,
    adaptive_kelly:  AdaptiveKelly,
}

impl ComprehensivePositionSizer {
    pub fn new(initial_capital: f64) -> Self {
        Self {
            capital: initial_capital,
            trade_history: Vec::new(),
            atr_history:   Vec::new(),
            mae_history:   Vec::new(),
            bayesian_sizer: BayesianSizer::default(),
            adaptive_kelly:  AdaptiveKelly::default(),
        }
    }

    /// Calculate position size using all signals.
    pub fn calculate_position(
        &self,
        win_rate_estimate: f64,
        win_loss_ratio: f64,
        stop_distance: f64,
        regime: MarketRegime,
        current_positions: Option<&[f64]>,
        correlation_matrix: Option<&[f64]>,
    ) -> PositionResult {
        let bayesian_kelly = self.bayesian_sizer.current_kelly(0.25);
        let regime_kelly   = self.adaptive_kelly.calculate(win_rate_estimate, win_loss_ratio, regime);
        let vol_scaling    = if !self.atr_history.is_empty() {
            volatility_targeting(&self.atr_history, 0.15, 3.0, 0.2)
        } else { 1.0 };
        let mae_scaling    = if !self.mae_history.is_empty() {
            max_adverse_excursion(stop_distance, &self.mae_history, 0.95)
        } else { 1.0 };
        let max_risk_cap   = maximum_safe_risk(win_rate_estimate, 2.0, 0.05);

        let raw_fraction   = bayesian_kelly * regime_kelly * vol_scaling * mae_scaling;
        let mut risk_fraction = raw_fraction.min(max_risk_cap);

        if let (Some(positions), Some(corr)) = (current_positions, correlation_matrix) {
            let mut all_positions = positions.to_vec();
            all_positions.push(risk_fraction);
            let adjusted = correlation_adjusted_size(&all_positions, corr, 1.0, 0.25);
            if let Some(&last) = adjusted.last() { risk_fraction = last; }
        }

        let risk_amount       = self.capital * risk_fraction;
        let notional_position = risk_amount / stop_distance;

        PositionResult {
            risk_fraction,
            risk_amount,
            notional_position,
            components: PositionComponents { bayesian_kelly, regime_kelly, vol_scaling, mae_scaling, max_risk_cap },
        }
    }

    /// Record a completed trade for adaptive learning.
    pub fn record_trade(&mut self, trade: TradeResult, atr_at_time: f64, mae: f64) {
        let pl = trade.profit_loss;
        self.atr_history.push(atr_at_time);
        self.mae_history.push(mae);
        self.bayesian_sizer.update(trade.clone());
        self.trade_history.push(trade);
        self.capital *= 1.0 + pl;
    }
}
