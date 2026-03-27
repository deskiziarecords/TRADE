"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   CROSS-ASSET CAUSAL TRANSMISSION ENGINE                                    ║
║   Module: causal_transmission.py                                            ║
║                                                                              ║
║   Thesis: Reversals originate in one asset and propagate to others          ║
║   through measurable causal channels with finite lag.                       ║
║                                                                              ║
║   Math Stack:                                                                ║
║     • Granger Causality       — linear predictive causality (VAR-based)     ║
║     • Transfer Entropy        — nonlinear information flow T(X→Y)           ║
║     • Cross-Correlation Map   — lag-resolved Pearson / Spearman             ║
║     • Convergent Cross-Mapping (CCM) — nonlinear attractor causality        ║
║     • Causal Graph (DiGraph)  — live weighted directed transmission network ║
║     • Regime-Conditional Betas — how coupling shifts across market regimes  ║
║     • Transmission Probability — P(reversal_Y | reversal_X, lag τ)         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import spearmanr
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass, field
from itertools import permutations
import warnings
warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CausalEdge:
    """
    A directed causal relationship: source → target.
    Encodes strength, lag, method of detection, and regime-conditionality.
    """
    source:          str
    target:          str
    granger_pval:    float        # p-value from Granger F-test (lower = stronger)
    transfer_entropy: float       # T(source → target) in nats
    optimal_lag:     int          # bars of lead (source leads target by this many bars)
    peak_xcorr:      float        # peak cross-correlation coefficient
    ccm_score:       float        # convergent cross-mapping score [0,1]
    regime_betas:    Dict[str, float] = field(default_factory=dict)  # beta per regime
    transmission_prob: float = 0.0  # P(reversal propagates within optimal_lag bars)

    @property
    def composite_strength(self) -> float:
        """
        Composite causal strength ∈ [0,1].
        Fuses all detection methods with reliability weighting.
        """
        granger_score = max(0.0, 1.0 - self.granger_pval * 10)
        te_score      = min(self.transfer_entropy / 0.3, 1.0)
        xcorr_score   = abs(self.peak_xcorr)
        ccm_s         = self.ccm_score
        return (0.30 * granger_score +
                0.30 * te_score +
                0.20 * xcorr_score +
                0.20 * ccm_s)

    @property
    def is_significant(self) -> bool:
        return (self.granger_pval < 0.05 and
                self.composite_strength > 0.25)


@dataclass
class TransmissionSignal:
    """
    A live causal transmission alert:
    Asset X just reversed — here is how that propagates.
    """
    origin_asset:       str
    origin_direction:   str            # "UP" or "DOWN"
    origin_reversal_prob: float
    propagation:        List[dict]     # sorted by probability × lag-discounted
    causal_graph_density: float
    regime:             str
    timestamp:          str


# ─────────────────────────────────────────────────────────────────────────────
# I.  GRANGER CAUSALITY
# ─────────────────────────────────────────────────────────────────────────────

class GrangerCausality:
    """
    Tests whether X Granger-causes Y via VAR(p) F-test.

    H₀: lagged X does not improve prediction of Y beyond lagged Y alone.
    Reject H₀ (low p-value) → X Granger-causes Y.

    Note: Granger causality is predictive, not mechanistic.
    We use it as one signal in a multi-method fusion.
    """

    def __init__(self, max_lags: int = 10):
        self.max_lags = max_lags

    def _var_residuals(self,
                        y: np.ndarray,
                        X: np.ndarray,
                        lags: int) -> Tuple[np.ndarray, int]:
        """Fit VAR(lags) and return residuals + df."""
        n = len(y)
        T = n - lags
        # Build regressor matrix
        cols = [np.ones(T)]
        for lag in range(1, lags + 1):
            cols.append(y[lags - lag : n - lag])
        for lag in range(1, lags + 1):
            cols.append(X[lags - lag : n - lag])
        Z = np.column_stack(cols)
        y_dep = y[lags:]
        # OLS
        try:
            beta = np.linalg.lstsq(Z, y_dep, rcond=None)[0]
            resid = y_dep - Z @ beta
            return resid, T - Z.shape[1]
        except Exception:
            return np.zeros(T), T - 1

    def test(self,
              X: np.ndarray,
              Y: np.ndarray,
              lags: int) -> float:
        """
        F-test: does X Granger-cause Y at given lag?
        Returns p-value.
        """
        n = len(Y)
        if n < lags * 3 + 10:
            return 1.0

        # Restricted model: Y ~ lagged Y only
        T = n - lags
        cols_r = [np.ones(T)]
        for lag in range(1, lags + 1):
            cols_r.append(Y[lags - lag : n - lag])
        Z_r = np.column_stack(cols_r)
        y_dep = Y[lags:]
        try:
            beta_r = np.linalg.lstsq(Z_r, y_dep, rcond=None)[0]
            rss_r  = np.sum((y_dep - Z_r @ beta_r) ** 2)
        except Exception:
            return 1.0

        # Unrestricted model: Y ~ lagged Y + lagged X
        cols_u = cols_r.copy()
        for lag in range(1, lags + 1):
            cols_u.append(X[lags - lag : n - lag])
        Z_u = np.column_stack(cols_u)
        try:
            beta_u = np.linalg.lstsq(Z_u, y_dep, rcond=None)[0]
            rss_u  = np.sum((y_dep - Z_u @ beta_u) ** 2)
        except Exception:
            return 1.0

        # F-statistic
        df_r   = lags
        df_u   = T - Z_u.shape[1]
        if df_u <= 0 or rss_u <= 0:
            return 1.0
        F = ((rss_r - rss_u) / df_r) / (rss_u / df_u)
        if F < 0:
            return 1.0
        pval = 1.0 - stats.f.cdf(F, df_r, df_u)
        return float(pval)

    def best_lag(self, X: np.ndarray, Y: np.ndarray) -> Tuple[int, float]:
        """Find lag that minimizes p-value."""
        best_lag  = 1
        best_pval = 1.0
        for lag in range(1, self.max_lags + 1):
            p = self.test(X, Y, lag)
            if p < best_pval:
                best_pval = p
                best_lag  = lag
        return best_lag, best_pval


# ─────────────────────────────────────────────────────────────────────────────
# II.  TRANSFER ENTROPY
# ─────────────────────────────────────────────────────────────────────────────

class TransferEntropy:
    """
    Transfer Entropy T(X→Y) quantifies how much knowing X's past
    reduces uncertainty about Y's future beyond Y's own past.

    T(X→Y) = H(Y_t | Y_{t-1}) - H(Y_t | Y_{t-1}, X_{t-τ})

    where H is Shannon entropy estimated via symbolic / binned approach.

    This captures NONLINEAR causal relationships missed by Granger.
    """

    def __init__(self, n_bins: int = 6, lag: int = 1, history: int = 1):
        self.n_bins  = n_bins
        self.lag     = lag
        self.history = history

    def _discretize(self, x: np.ndarray) -> np.ndarray:
        """Bin continuous series into n_bins discrete symbols."""
        bins = np.percentile(x, np.linspace(0, 100, self.n_bins + 1))
        bins[0]  -= 1e-10
        bins[-1] += 1e-10
        return np.digitize(x, bins) - 1

    def _joint_entropy(self, *arrays) -> float:
        """H(X₁, X₂, ...) via joint frequency table."""
        combined = list(zip(*arrays))
        counts = {}
        for tup in combined:
            counts[tup] = counts.get(tup, 0) + 1
        n = len(combined)
        if n == 0:
            return 0.0
        probs = [c / n for c in counts.values()]
        return float(-np.sum([p * np.log(p + 1e-12) for p in probs]))

    def compute(self, X: np.ndarray, Y: np.ndarray) -> float:
        """
        T(X→Y) in nats.
        Positive value = X carries information about Y's future.
        """
        lag = self.lag
        k   = self.history
        n   = min(len(X), len(Y))
        if n < lag + k + 10:
            return 0.0

        X_d = self._discretize(X[:n])
        Y_d = self._discretize(Y[:n])

        # Build aligned windows
        Y_future = Y_d[lag + k :]
        Y_past   = Y_d[k      : n - lag]
        X_past   = X_d[0      : n - lag - k]

        min_len = min(len(Y_future), len(Y_past), len(X_past))
        if min_len < 5:
            return 0.0

        Y_f = Y_future[:min_len]
        Y_p = Y_past[:min_len]
        X_p = X_past[:min_len]

        # T(X→Y) = H(Y_f, Y_p) + H(Y_p, X_p) - H(Y_p) - H(Y_f, Y_p, X_p)
        h_yf_yp     = self._joint_entropy(Y_f, Y_p)
        h_yp_xp     = self._joint_entropy(Y_p, X_p)
        h_yp        = self._joint_entropy(Y_p,)
        h_yf_yp_xp  = self._joint_entropy(Y_f, Y_p, X_p)

        te = h_yf_yp + h_yp_xp - h_yp - h_yf_yp_xp
        return float(max(te, 0.0))

    def scan_lags(self, X: np.ndarray, Y: np.ndarray,
                   max_lag: int = 10) -> Tuple[int, float]:
        """Find lag τ maximizing T(X_{t-τ} → Y_t)."""
        best_lag = 1
        best_te  = 0.0
        orig_lag = self.lag
        for lag in range(1, max_lag + 1):
            self.lag = lag
            te = self.compute(X, Y)
            if te > best_te:
                best_te  = te
                best_lag = lag
        self.lag = orig_lag
        return best_lag, best_te


# ─────────────────────────────────────────────────────────────────────────────
# III.  CROSS-CORRELATION MAP
# ─────────────────────────────────────────────────────────────────────────────

class CrossCorrelationMap:
    """
    Lag-resolved cross-correlation between asset return series.
    Identifies: (1) lead-lag sign, (2) peak lag, (3) correlation decay rate.

    Uses rank-based (Spearman) to be robust to fat tails.
    """

    def __init__(self, max_lag: int = 20):
        self.max_lag = max_lag

    def compute_map(self,
                     X_ret: np.ndarray,
                     Y_ret: np.ndarray) -> Dict[int, float]:
        """
        Returns dict {lag: ρ(X_{t-lag}, Y_t)} for lag ∈ [-max_lag, max_lag].
        Positive lag = X leads Y.
        Negative lag = Y leads X.
        """
        n = min(len(X_ret), len(Y_ret))
        corr_map = {}
        for lag in range(-self.max_lag, self.max_lag + 1):
            if lag > 0:
                x = X_ret[:n - lag]
                y = Y_ret[lag:]
            elif lag < 0:
                x = X_ret[-lag:]
                y = Y_ret[:n + lag]
            else:
                x = X_ret[:n]
                y = Y_ret[:n]
            min_len = min(len(x), len(y))
            if min_len < 10:
                corr_map[lag] = 0.0
                continue
            rho, _ = spearmanr(x[:min_len], y[:min_len])
            corr_map[lag] = float(rho) if not np.isnan(rho) else 0.0
        return corr_map

    def lead_lag_summary(self,
                          X_ret: np.ndarray,
                          Y_ret: np.ndarray) -> Tuple[int, float, float]:
        """
        Returns (optimal_lag, peak_corr, decay_rate).
        optimal_lag > 0 means X leads Y.
        decay_rate = how quickly correlation drops off from peak.
        """
        cmap = self.compute_map(X_ret, Y_ret)
        lags  = np.array(list(cmap.keys()))
        corrs = np.array(list(cmap.values()))

        # Peak by absolute correlation
        peak_idx  = np.argmax(np.abs(corrs))
        peak_lag  = int(lags[peak_idx])
        peak_corr = float(corrs[peak_idx])

        # Decay: correlation at lag ± 2 from peak
        decay_lags  = [peak_lag - 2, peak_lag + 2]
        decay_corrs = [cmap.get(l, 0.0) for l in decay_lags]
        decay_rate  = abs(peak_corr) - np.mean(np.abs(decay_corrs))

        return peak_lag, peak_corr, float(decay_rate)


# ─────────────────────────────────────────────────────────────────────────────
# IV.  CONVERGENT CROSS-MAPPING (CCM)
# ─────────────────────────────────────────────────────────────────────────────

class ConvergentCrossMapping:
    """
    CCM (Sugihara et al. 2012) tests for nonlinear causality via
    attractor reconstruction.

    Key idea: if X causally influences Y, then the attractor of Y
    contains information about X's past trajectory.

    We test: can we predict X from Y's attractor?
    If yes (and skill increases with library size L), X drives Y.

    This distinguishes true causality from spurious correlation,
    particularly important for co-integrated forex pairs.
    """

    def __init__(self, E: int = 3, tau: int = 1, lib_sizes: Optional[List[int]] = None):
        self.E    = E     # embedding dimension
        self.tau  = tau   # time delay
        self.lib_sizes = lib_sizes or [20, 40, 60, 80, 100]

    def _embed(self, x: np.ndarray, E: int, tau: int) -> np.ndarray:
        """Time-delay embedding: x → [x_t, x_{t-τ}, x_{t-2τ}, ...]"""
        n = len(x)
        max_lag = (E - 1) * tau
        if n <= max_lag:
            return np.zeros((1, E))
        M = np.column_stack([x[i * tau : n - (E - 1 - i) * tau]
                              for i in range(E)])
        return M

    def _knn_predict(self,
                      manifold: np.ndarray,
                      target: np.ndarray,
                      lib_size: int,
                      k: int = 4) -> np.ndarray:
        """Predict target values using k-NN on manifold."""
        n = min(len(manifold), len(target), lib_size)
        if n < k + 2:
            return np.zeros(len(target))

        predictions = []
        for t in range(k, len(manifold)):
            lib_end = min(t, n)
            if lib_end < k:
                predictions.append(np.mean(target[:max(1, lib_end)]))
                continue
            dists = np.linalg.norm(manifold[:lib_end] - manifold[t], axis=1)
            nn_idx = np.argsort(dists)[1:k+1]
            # Weighted average (exponential kernel)
            w = np.exp(-dists[nn_idx] / (np.mean(dists[nn_idx]) + 1e-10))
            w /= w.sum() + 1e-10
            pred = np.dot(w, target[nn_idx])
            predictions.append(pred)

        return np.array(predictions)

    def skill(self, X: np.ndarray, Y: np.ndarray, lib_size: int) -> float:
        """
        Prediction skill of X from Y's manifold (ρ between predicted and actual X).
        If Y → X causally, this skill should increase with lib_size.
        """
        MY = self._embed(Y, self.E, self.tau)
        offset = (self.E - 1) * self.tau
        Xt = X[offset:offset + len(MY)]
        if len(MY) < 5 or len(Xt) < 5:
            return 0.0
        X_hat = self._knn_predict(MY, Xt, lib_size)
        min_len = min(len(X_hat), len(Xt))
        if min_len < 4:
            return 0.0
        rho, _ = spearmanr(X_hat[:min_len], Xt[:min_len])
        return float(max(rho, 0.0)) if not np.isnan(rho) else 0.0

    def test_causality(self, X: np.ndarray, Y: np.ndarray) -> float:
        """
        Does X cause Y? (Test: can we predict X from Y's manifold?)
        Returns CCM score ∈ [0, 1], where higher = stronger causality.
        Also checks convergence (score increases with lib size).
        """
        n = min(len(X), len(Y))
        available_libs = [l for l in self.lib_sizes if l < n - 5]
        if not available_libs:
            return 0.0

        skills = [self.skill(X[:n], Y[:n], l) for l in available_libs]

        # Convergence: does skill increase with library size?
        if len(skills) >= 3:
            convergence = np.polyfit(available_libs[:len(skills)],
                                     skills, 1)[0]   # slope
            convergence_bonus = min(max(convergence * 50, 0.0), 0.3)
        else:
            convergence_bonus = 0.0

        return float(min(np.mean(skills) + convergence_bonus, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# V.   REGIME-CONDITIONAL BETA ESTIMATOR
# ─────────────────────────────────────────────────────────────────────────────

class RegimeConditionalBeta:
    """
    Estimates how the coupling β between two assets changes across regimes.

    β_regime(X→Y) = Cov(Y_ret, X_ret | regime) / Var(X_ret | regime)

    Regimes are identified via hidden Markov-like volatility clustering:
      - Low vol    → accumulation / consolidation
      - Medium vol → trend / retracement
      - High vol   → expansion / reversal
    """

    def __init__(self, vol_window: int = 20):
        self.vol_window = vol_window

    def _assign_regimes(self, returns: np.ndarray) -> np.ndarray:
        """
        Assign each bar to: 0=low-vol, 1=mid-vol, 2=high-vol.
        Based on rolling 20-bar realized volatility percentile.
        """
        n   = len(returns)
        vol = pd.Series(returns).rolling(self.vol_window, min_periods=5).std().values
        # Percentile thresholds
        p33 = np.nanpercentile(vol, 33)
        p67 = np.nanpercentile(vol, 67)
        regimes = np.where(vol < p33, 0, np.where(vol < p67, 1, 2))
        return regimes

    def compute(self,
                 X_ret: np.ndarray,
                 Y_ret: np.ndarray) -> Dict[str, float]:
        """
        Returns β(X→Y) for each volatility regime.
        """
        n       = min(len(X_ret), len(Y_ret))
        regimes = self._assign_regimes(X_ret[:n])
        names   = {0: "low_vol", 1: "mid_vol", 2: "high_vol"}
        betas   = {}
        for r, name in names.items():
            mask = regimes == r
            if mask.sum() < 5:
                betas[name] = 0.0
                continue
            x = X_ret[:n][mask]
            y = Y_ret[:n][mask]
            var_x = np.var(x)
            if var_x < 1e-12:
                betas[name] = 0.0
            else:
                betas[name] = float(np.cov(x, y)[0, 1] / var_x)
        return betas


# ─────────────────────────────────────────────────────────────────────────────
# VI.  CAUSAL TRANSMISSION GRAPH
# ─────────────────────────────────────────────────────────────────────────────

class CausalTransmissionGraph:
    """
    Directed weighted graph of causal market linkages.

    Nodes = assets.
    Edges = CausalEdge instances (significant causality only).

    Methods:
      build()         — fit all pairwise causal relationships
      propagate()     — given a reversal in asset X, compute
                        transmission probabilities to all other assets
      strongest_path()— find the causal chain X → A → B → ... → Y
      hub_assets()    — rank assets by out-degree causal influence
    """

    def __init__(self,
                 max_lags:  int = 10,
                 min_bars:  int = 60,
                 verbose:   bool = True):
        self.max_lags = max_lags
        self.min_bars = min_bars
        self.verbose  = verbose

        self.granger  = GrangerCausality(max_lags=max_lags)
        self.te_calc  = TransferEntropy(n_bins=6)
        self.xcorr    = CrossCorrelationMap(max_lag=max_lags)
        self.ccm      = ConvergentCrossMapping(E=3, tau=1)
        self.beta_est = RegimeConditionalBeta()

        # Graph storage
        self.edges:  Dict[Tuple[str,str], CausalEdge] = {}
        self.assets: List[str] = []
        self._returns: Dict[str, np.ndarray] = {}

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [CTG] {msg}")

    def build(self, price_data: Dict[str, np.ndarray]) -> "CausalTransmissionGraph":
        """
        Fit full pairwise causal graph from price data.

        price_data: dict {asset_name: price_array}
        """
        self.assets = list(price_data.keys())
        self._log(f"Building causal graph for {len(self.assets)} assets: {self.assets}")

        # Compute log returns
        for asset, prices in price_data.items():
            ret = np.diff(np.log(prices + 1e-12))
            self._returns[asset] = ret

        # Pairwise directed edges
        pairs = list(permutations(self.assets, 2))
        self._log(f"Testing {len(pairs)} directed pairs...")

        for source, target in pairs:
            X = self._returns[source]
            Y = self._returns[target]
            n = min(len(X), len(Y))
            if n < self.min_bars:
                continue

            X, Y = X[:n], Y[:n]

            # Granger
            g_lag, g_pval = self.granger.best_lag(X, Y)

            # Transfer Entropy
            te_lag, te_val = self.te_calc.scan_lags(X, Y, max_lag=self.max_lags)

            # Cross-correlation
            opt_lag, peak_xcorr, _ = self.xcorr.lead_lag_summary(X, Y)

            # CCM (only for significant edges to save compute)
            if g_pval < 0.15:
                ccm_score = self.ccm.test_causality(X[:n], Y[:n])
            else:
                ccm_score = 0.0

            # Regime betas
            regime_betas = self.beta_est.compute(X, Y)

            # Resolve best lag (mode of the three estimates)
            lag_votes = [g_lag, te_lag, max(opt_lag, 1)]
            optimal_lag = int(np.median(lag_votes))

            edge = CausalEdge(
                source=source,
                target=target,
                granger_pval=g_pval,
                transfer_entropy=te_val,
                optimal_lag=optimal_lag,
                peak_xcorr=peak_xcorr,
                ccm_score=ccm_score,
                regime_betas=regime_betas,
            )

            # Compute transmission probability
            edge.transmission_prob = self._estimate_transmission_prob(X, Y, edge)
            self.edges[(source, target)] = edge

        sig_count = sum(1 for e in self.edges.values() if e.is_significant)
        self._log(f"Graph built: {len(self.edges)} edges, {sig_count} significant")
        return self

    def _estimate_transmission_prob(self,
                                     X: np.ndarray,
                                     Y: np.ndarray,
                                     edge: CausalEdge) -> float:
        """
        Empirical P(reversal in Y within lag τ | reversal in X).

        A reversal in X is defined as a 1.5σ move followed by reversal.
        We count how often Y then reverses within `edge.optimal_lag` bars.
        """
        n   = min(len(X), len(Y))
        lag = max(edge.optimal_lag, 1)
        sigma_x = np.std(X[:n]) + 1e-12
        threshold = 1.5 * sigma_x

        reversal_x = []
        for i in range(5, n - lag):
            # X reversal: 5-bar trend reverses
            trend = X[i] - X[i-5]
            if abs(trend) > threshold:
                reversal_x.append((i, np.sign(trend)))

        if not reversal_x:
            return edge.composite_strength * 0.5

        # Count Y reversals following X reversals
        success = 0
        sigma_y = np.std(Y[:n]) + 1e-12
        for idx, direction in reversal_x:
            window = Y[idx : min(idx + lag + 1, n)]
            if len(window) == 0:
                continue
            # Y should move in same direction as X (or opposite for inverse pairs)
            y_move = window[-1] - Y[idx]
            corr_sign = np.sign(edge.peak_xcorr)
            expected_move = direction * corr_sign
            if expected_move * y_move > 0 and abs(y_move) > 0.5 * sigma_y:
                success += 1

        return float(success / len(reversal_x))

    def propagate(self,
                   origin: str,
                   direction: str = "DOWN",
                   current_regime: str = "mid_vol",
                   min_prob: float = 0.20) -> List[dict]:
        """
        Given a reversal in `origin`, compute transmission to all other assets.

        Returns list of propagation targets sorted by adjusted probability.
        """
        results = []
        for (source, target), edge in self.edges.items():
            if source != origin:
                continue
            if not edge.is_significant:
                continue

            # Regime-adjusted beta
            beta = edge.regime_betas.get(current_regime,
                   edge.regime_betas.get("mid_vol", 1.0))

            # Transmission probability adjusted for regime and lag discount
            lag_discount = np.exp(-0.1 * edge.optimal_lag)  # decay with lag
            adj_prob = edge.transmission_prob * lag_discount * min(abs(beta), 2.0)
            adj_prob = float(np.clip(adj_prob, 0, 1))

            # Direction of transmission
            if edge.peak_xcorr > 0:
                trans_dir = direction
            else:
                trans_dir = "UP" if direction == "DOWN" else "DOWN"

            if adj_prob >= min_prob:
                results.append({
                    "target":           target,
                    "direction":        trans_dir,
                    "probability":      round(adj_prob, 3),
                    "lag_bars":         edge.optimal_lag,
                    "granger_pval":     round(edge.granger_pval, 4),
                    "transfer_entropy": round(edge.transfer_entropy, 4),
                    "peak_xcorr":       round(edge.peak_xcorr, 3),
                    "ccm_score":        round(edge.ccm_score, 3),
                    "regime_beta":      round(beta, 3),
                    "composite_strength": round(edge.composite_strength, 3),
                })

        return sorted(results, key=lambda x: x["probability"], reverse=True)

    def strongest_path(self, source: str, target: str,
                        max_depth: int = 4) -> List[str]:
        """
        Find strongest causal chain from source to target via Dijkstra
        on edge weight = -log(composite_strength).
        """
        import heapq
        dist  = {a: float("inf") for a in self.assets}
        prev  = {a: None for a in self.assets}
        dist[source] = 0.0
        pq = [(0.0, source)]

        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for (s, t), edge in self.edges.items():
                if s != u or not edge.is_significant:
                    continue
                w = -np.log(edge.composite_strength + 1e-6)
                if dist[u] + w < dist[t]:
                    dist[t] = dist[u] + w
                    prev[t] = u
                    heapq.heappush(pq, (dist[t], t))

        # Reconstruct path
        path = []
        node = target
        depth = 0
        while node is not None and depth < max_depth:
            path.append(node)
            node = prev[node]
            depth += 1
        return list(reversed(path)) if path[-1] == source else []

    def hub_assets(self) -> List[Tuple[str, float]]:
        """
        Rank assets by total outgoing causal strength (causal hubs).
        High hub score = this asset frequently leads others.
        """
        out_strength: Dict[str, float] = {a: 0.0 for a in self.assets}
        for (source, target), edge in self.edges.items():
            if edge.is_significant:
                out_strength[source] += edge.composite_strength
        return sorted(out_strength.items(), key=lambda x: x[1], reverse=True)

    def adjacency_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """Return weighted adjacency matrix and asset list."""
        n   = len(self.assets)
        idx = {a: i for i, a in enumerate(self.assets)}
        A   = np.zeros((n, n))
        for (s, t), edge in self.edges.items():
            if edge.is_significant:
                A[idx[s], idx[t]] = edge.composite_strength
        return A, self.assets

    def density(self) -> float:
        """Graph edge density of significant edges."""
        n   = len(self.assets)
        if n < 2:
            return 0.0
        possible = n * (n - 1)
        sig = sum(1 for e in self.edges.values() if e.is_significant)
        return sig / possible

    def print_report(self) -> None:
        print(f"\n{'═'*65}")
        print(f"  CAUSAL TRANSMISSION GRAPH REPORT")
        print(f"{'═'*65}")
        print(f"  Assets:           {self.assets}")
        print(f"  Graph density:    {self.density():.2f}")
        print(f"\n  Causal Hubs (outgoing strength):")
        for asset, strength in self.hub_assets():
            bar = "█" * int(strength * 15)
            print(f"    {asset:10s} {strength:.3f}  |{bar:<20}|")
        print(f"\n  Significant Edges (source → target):")
        for (s, t), edge in sorted(self.edges.items(),
                                    key=lambda x: x[1].composite_strength,
                                    reverse=True):
            if not edge.is_significant:
                continue
            print(f"    {s:10s} → {t:10s}  "
                  f"strength={edge.composite_strength:.3f}  "
                  f"lag={edge.optimal_lag}  "
                  f"TE={edge.transfer_entropy:.4f}  "
                  f"GrangerP={edge.granger_pval:.3f}  "
                  f"Ptrans={edge.transmission_prob:.3f}")
        print(f"{'═'*65}\n")
