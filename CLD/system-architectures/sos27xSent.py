"""
╔══════════════════════════════════════════════════════════════════════════════╗
║    SOS-27-X SENTINEL — PRODUCTION ORCHESTRATOR                              ║
║    Adelic-Koopman IPDA Trading System                                       ║
║                                                                              ║
║    Pipeline:                                                                 ║
║      1. Data Ingestion & Normalization                                       ║
║      2. Adelic Tube Scan (Non-Archimedean level detection)                  ║
║      3. Koopman Fit + Spectral Analysis                                      ║
║      4. Mandra Primitive Execution                                           ║
║      5. Delivery Signature Encoding + ChromaDB Retrieval                    ║
║      6. Regime Classification (SOS-27 State Machine)                        ║
║      7. Reversal Probability Fusion                                          ║
║      8. Circuit Breaker Arbitration                                          ║
║      9. Signal Emission                                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from enum import Enum
import json
import time
import os
import sys

sys.path.insert(0, "/home/claude")
from adelic_koopman_core import (
    AdelicPriceGeometry,
    KoopmanOperator,
    MandraPrimitives,
    DeliverySignatureMemory,
    DeliverySignature,
    SentinelState,
)


# ─────────────────────────────────────────────────────────────────────────────
# ENUMERATIONS & DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

class MarketRegime(Enum):
    EXPANSION       = "expansion"
    RETRACEMENT     = "retracement"
    REVERSAL        = "reversal"
    CONSOLIDATION   = "consolidation"
    ACCUMULATION    = "accumulation"
    DISTRIBUTION    = "distribution"
    UNKNOWN         = "unknown"


class SignalDirection(Enum):
    LONG    = "LONG"
    SHORT   = "SHORT"
    NEUTRAL = "NEUTRAL"
    HALT    = "HALT"   # circuit breaker engaged


@dataclass
class IPDAState:
    """Complete IPDA market state at a given bar."""
    timestamp:          str
    pair:               str
    close:              float
    high:               float
    low:                float

    # IPDA range data
    ipda_20d_high:      float = 0.0
    ipda_20d_low:       float = 0.0
    ipda_40d_high:      float = 0.0
    ipda_40d_low:       float = 0.0
    ipda_60d_high:      float = 0.0
    ipda_60d_low:       float = 0.0

    # Adelic metrics
    adelic_norm:        float = 0.0
    tube_confluence:    float = 0.0
    adelic_levels:      List[float] = field(default_factory=list)

    # Koopman metrics
    koopman_instability: float = 0.0
    koopman_freq:         float = 0.0
    lyapunov_exponent:    float = 0.0
    spectral_score:       float = 0.0

    # Mandra primitive outputs
    sweep_score:        float = 0.0
    delivery_vector:    Optional[np.ndarray] = None

    # Classification
    regime:             MarketRegime = MarketRegime.UNKNOWN
    reversal_prob:      float = 0.0
    signal:             SignalDirection = SignalDirection.NEUTRAL
    confidence:         float = 0.0

    # Memory retrieval
    n_similar_episodes: int = 0
    similar_outcome_mean: float = 0.0

    # Circuit breakers
    breakers_active:    List[str] = field(default_factory=list)


@dataclass
class SentinelSignal:
    """Final signal emitted by SOS-27-X."""
    timestamp:       str
    pair:            str
    direction:       SignalDirection
    reversal_prob:   float
    confidence:      float
    regime:          MarketRegime
    entry_zone:      Tuple[float, float]   # (low, high)
    invalidation:    float                  # stop level
    adelic_score:    float
    koopman_score:   float
    memory_score:    float                  # similarity to historical episodes
    reasoning:       List[str]              # forensic audit trail
    raw_state:       Optional[IPDAState] = None


# ─────────────────────────────────────────────────────────────────────────────
# SOS-27-X STATE MACHINE
# ─────────────────────────────────────────────────────────────────────────────

class SOS27StateMachine:
    """
    27-state hierarchical IPDA regime classifier.
    Condenses to 6 primary states (MarketRegime) via Markov projection.

    Transition logic uses:
      - IPDA range breach counts
      - Koopman spectral instability
      - Adelic tube confluence
      - Sweep score momentum
    """

    def __init__(self):
        # Transition probability matrix (simplified 6x6 for production)
        self.T = np.array([
            # EXP   RETR  REV   CONS  ACCUM DISTR
            [0.40, 0.25, 0.15, 0.10, 0.05, 0.05],  # from EXPANSION
            [0.20, 0.35, 0.25, 0.10, 0.05, 0.05],  # from RETRACEMENT
            [0.30, 0.10, 0.20, 0.15, 0.10, 0.15],  # from REVERSAL
            [0.10, 0.15, 0.10, 0.40, 0.15, 0.10],  # from CONSOLIDATION
            [0.25, 0.10, 0.05, 0.20, 0.30, 0.10],  # from ACCUMULATION
            [0.25, 0.10, 0.10, 0.15, 0.05, 0.35],  # from DISTRIBUTION
        ])
        self.states = [
            MarketRegime.EXPANSION, MarketRegime.RETRACEMENT,
            MarketRegime.REVERSAL,  MarketRegime.CONSOLIDATION,
            MarketRegime.ACCUMULATION, MarketRegime.DISTRIBUTION,
        ]
        self.current_state_idx = 3   # start in CONSOLIDATION
        self.state_history: List[int] = [3]

    def update(self,
               sweep_score: float,
               koopman_instability: float,
               tube_confluence: float,
               atr_pct: float,
               price_pos_60d: float) -> MarketRegime:
        """
        Update regime based on incoming signals.
        Returns new MarketRegime.
        """
        # Adjust transition probabilities based on signals
        T_adj = self.T.copy()

        # High sweep → more likely reversal
        if sweep_score > 0.6:
            T_adj[:, 2] *= (1 + sweep_score)   # boost reversal column

        # High Koopman instability → regime transition imminent
        if koopman_instability > 0.4:
            for i in range(6):
                T_adj[i, i] *= 0.5   # reduce self-transition (force change)

        # High adelic confluence → expansion or reversal
        if tube_confluence > 0.7:
            T_adj[:, 0] *= 1.3   # expansion more likely

        # Price in premium zone → distribution or reversal
        if price_pos_60d > 0.75:
            T_adj[:, 5] *= 1.4   # distribution
            T_adj[:, 2] *= 1.2   # reversal

        # Price in discount zone → accumulation or reversal
        if price_pos_60d < 0.25:
            T_adj[:, 4] *= 1.4   # accumulation
            T_adj[:, 2] *= 1.2   # reversal

        # High ATR → expansion
        if atr_pct > 0.008:
            T_adj[:, 0] *= 1.5

        # Normalize rows
        row_sums = T_adj.sum(axis=1, keepdims=True)
        T_adj = T_adj / np.where(row_sums == 0, 1, row_sums)

        # Sample next state from current row
        probs = T_adj[self.current_state_idx]
        probs = np.maximum(probs, 0)
        probs /= probs.sum()
        next_idx = int(np.random.choice(6, p=probs))

        self.current_state_idx = next_idx
        self.state_history.append(next_idx)
        return self.states[next_idx]

    @property
    def current_regime(self) -> MarketRegime:
        return self.states[self.current_state_idx]


# ─────────────────────────────────────────────────────────────────────────────
# REVERSAL PROBABILITY FUSION
# ─────────────────────────────────────────────────────────────────────────────

class ReversalProbabilityFusion:
    """
    Bayesian fusion of reversal evidence from all subsystems.

    P(reversal | evidence) ∝ P(evidence | reversal) · P(reversal)

    Evidence streams:
      E1: Adelic tube confluence at IPDA boundaries
      E2: Koopman spectral instability / dominant frequency
      E3: Mandra sweep score
      E4: Memory similarity to historical reversals
      E5: SOS-27 regime (reversal/distribution states)
      E6: Quarterly cycle position
    """

    WEIGHTS = {
        "adelic":    0.25,
        "koopman":   0.20,
        "sweep":     0.20,
        "memory":    0.15,
        "regime":    0.12,
        "cycle":     0.08,
    }

    # Likelihood P(E | reversal) for each evidence level
    LIKELIHOODS = {
        "adelic":  [0.1, 0.2, 0.4, 0.7, 0.9],   # thresholds: 0, 0.25, 0.5, 0.75, 1.0
        "koopman": [0.1, 0.2, 0.45, 0.75, 0.95],
        "sweep":   [0.05, 0.15, 0.4, 0.7, 0.9],
        "memory":  [0.2, 0.3, 0.45, 0.6, 0.8],
        "regime":  {
            MarketRegime.REVERSAL:     0.85,
            MarketRegime.DISTRIBUTION: 0.70,
            MarketRegime.ACCUMULATION: 0.65,
            MarketRegime.RETRACEMENT:  0.45,
            MarketRegime.EXPANSION:    0.25,
            MarketRegime.CONSOLIDATION:0.20,
            MarketRegime.UNKNOWN:      0.30,
        },
    }

    def _score_to_likelihood(self, score: float, key: str) -> float:
        """Map a [0,1] score to P(E | reversal) via piecewise linear interpolation."""
        thresholds = [0.0, 0.25, 0.5, 0.75, 1.0]
        likelihoods = self.LIKELIHOODS[key]
        return float(np.interp(score, thresholds, likelihoods))

    def fuse(self,
             adelic_score: float,
             koopman_instability: float,
             sweep_score: float,
             memory_reversal_ratio: float,
             regime: MarketRegime,
             cycle_nearness: float,
             prior: float = 0.35) -> Tuple[float, Dict[str, float]]:
        """
        Returns (posterior_reversal_probability, component_scores).
        """
        # Individual likelihoods
        L_adelic  = self._score_to_likelihood(adelic_score,     "adelic")
        L_koopman = self._score_to_likelihood(koopman_instability, "koopman")
        L_sweep   = self._score_to_likelihood(sweep_score,       "sweep")
        L_memory  = self._score_to_likelihood(memory_reversal_ratio, "memory")
        L_regime  = self.LIKELIHOODS["regime"].get(regime, 0.30)
        L_cycle   = self._score_to_likelihood(cycle_nearness,    "adelic")  # reuse scale

        components = {
            "adelic":  L_adelic,
            "koopman": L_koopman,
            "sweep":   L_sweep,
            "memory":  L_memory,
            "regime":  L_regime,
            "cycle":   L_cycle,
        }

        # Weighted log-odds fusion (numerically stable Bayesian update)
        log_odds_prior = np.log(prior / (1 - prior + 1e-12))
        log_odds_update = sum(
            self.WEIGHTS[k] * np.log(v / (1 - v + 1e-12) + 1e-12)
            for k, v in components.items()
        )
        log_odds_posterior = log_odds_prior + log_odds_update
        posterior = 1.0 / (1.0 + np.exp(-log_odds_posterior))
        return float(np.clip(posterior, 0.01, 0.99)), components


# ─────────────────────────────────────────────────────────────────────────────
# SOS-27-X SENTINEL — MAIN ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class SOS27XSentinel:
    """
    Production Orchestrator: Adelic-Koopman IPDA Trading System.

    Usage:
        sentinel = SOS27XSentinel(pair="EURUSD")
        signal = sentinel.process(df)   # df = OHLCV DataFrame
        print(signal)
    """

    IPDA_WINDOWS = [20, 40, 60]

    def __init__(self, pair: str = "EURUSD", verbose: bool = True):
        self.pair     = pair
        self.verbose  = verbose

        # Subsystem initialization
        self.adelic      = AdelicPriceGeometry(price_scale=1e4)
        self.koopman     = KoopmanOperator(n_observables=64, n_modes=32)
        self.primitives  = MandraPrimitives()
        self.memory      = DeliverySignatureMemory(f"ipda_{pair.lower()}")
        self.state_store = SentinelState()
        self.sos27       = SOS27StateMachine()
        self.fusion      = ReversalProbabilityFusion()

        self._log(f"SOS-27-X Sentinel initialized for {pair}")
        self._log(f"  Memory backend:  {'ChromaDB' if self.memory._use_chroma else 'numpy (in-memory)'}")
        self._log(f"  State backend:   {'Redis' if self.state_store._use_redis else 'dict (in-process)'}")
        self._log(f"  JAX available:   {__import__('sys').modules.get('jax') is not None}")

    def _log(self, msg: str) -> None:
        if self.verbose:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"  [{ts}] {msg}")

    # ── Feature Computation ────────────────────────────────────────────────

    def _compute_ipda_ranges(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """Compute rolling IPDA 20/40/60-day high/low ranges."""
        out = {}
        for w in self.IPDA_WINDOWS:
            out[f"high_{w}d"] = df["high"].rolling(w, min_periods=1).max().values
            out[f"low_{w}d"]  = df["low"].rolling(w, min_periods=1).min().values
        return out

    def _compute_atr(self, df: pd.DataFrame, period: int = 14) -> np.ndarray:
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"]  - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period, min_periods=1).mean().values

    def _build_koopman_state(self, df: pd.DataFrame,
                              ranges: Dict[str, np.ndarray]) -> np.ndarray:
        """
        Build state matrix X for Koopman fitting.
        Columns: [close_norm, high_low_ratio, pos_20d, pos_40d, pos_60d,
                  atr_pct, momentum_5, momentum_20]
        """
        close = df["close"].values
        atr   = self._compute_atr(df)

        c_min, c_max = close.min(), close.max()
        close_norm = (close - c_min) / max(c_max - c_min, 1e-10)

        hl_ratio = (df["high"].values - df["low"].values) / (atr + 1e-10)

        def pos(w):
            rng = ranges[f"high_{w}d"] - ranges[f"low_{w}d"]
            rng = np.where(rng < 1e-10, 1e-10, rng)
            return (close - ranges[f"low_{w}d"]) / rng

        mom5  = pd.Series(close).pct_change(5).fillna(0).values
        mom20 = pd.Series(close).pct_change(20).fillna(0).values

        return np.column_stack([
            close_norm, hl_ratio, pos(20), pos(40), pos(60),
            atr / (close + 1e-10), mom5, mom20,
        ])

    # ── Main Processing Pipeline ───────────────────────────────────────────

    def process(self, df: pd.DataFrame) -> SentinelSignal:
        """
        Full Adelic-Koopman IPDA pipeline on OHLCV DataFrame.
        Returns a SentinelSignal with forensic audit trail.
        """
        t0      = time.time()
        close   = df["close"].values
        high    = df["high"].values
        low     = df["low"].values
        atr     = self._compute_atr(df)
        ranges  = self._compute_ipda_ranges(df)
        reasoning: List[str] = []

        # ── Step 1: IPDA Range State ────────────────────────────────────
        self._log("Step 1 — IPDA range scan...")
        cur_close = float(close[-1])
        ipda_state = {}
        for w in self.IPDA_WINDOWS:
            h = float(ranges[f"high_{w}d"][-1])
            l = float(ranges[f"low_{w}d"][-1])
            rng = h - l if h - l > 1e-10 else 1e-10
            pos = (cur_close - l) / rng
            ipda_state[f"high_{w}d"] = h
            ipda_state[f"low_{w}d"]  = l
            ipda_state[f"pos_{w}d"]  = pos
            status = "PREMIUM" if pos > 0.5 else "DISCOUNT"
            reasoning.append(f"IPDA {w}d range: [{l:.5f}, {h:.5f}] | pos={pos:.2f} ({status})")

        # ── Step 2: Adelic Geometry ─────────────────────────────────────
        self._log("Step 2 — Adelic tube refinement...")
        adelic_norm = self.adelic.adelic_norm(cur_close)

        # Institutional levels from recent price history
        recent_prices = close[-60:]
        inst_indices  = self.adelic.institutional_levels(recent_prices, top_n=10)
        inst_levels   = recent_prices[inst_indices].tolist()

        epsilon = float(atr[-1]) * 0.5
        tube_confluence = self.adelic.tube_confluence_score(
            cur_close, np.array(inst_levels), epsilon
        )
        adelic_score = min(adelic_norm / 1000.0, 1.0) * 0.4 + tube_confluence * 0.6
        reasoning.append(
            f"Adelic norm={adelic_norm:.2f} | tube confluence={tube_confluence:.3f} | "
            f"adelic score={adelic_score:.3f} | {len(inst_levels)} inst. levels detected"
        )

        # ── Step 3: Koopman Linearization ──────────────────────────────
        self._log("Step 3 — Koopman operator fit...")
        X_state = self._build_koopman_state(df, ranges)

        if len(X_state) > 20:
            ipda_levels_arr = np.array([ipda_state[f"high_{w}d"] for w in self.IPDA_WINDOWS] +
                                        [ipda_state[f"low_{w}d"]  for w in self.IPDA_WINDOWS])
            self.koopman.fit(X_state[-min(len(X_state), 120):], ipda_levels=ipda_levels_arr)

            k_instability = self.koopman.instability_index()
            k_freq        = self.koopman.dominant_frequency()
            k_lyapunov    = self.koopman.lyapunov_exponent()
            k_modes       = self.koopman.predict_modes(steps=5)
            k_modes_flat  = k_modes.flatten()[:128]

            # Spectral score via Mandra primitive
            eigs = self.koopman.eigenvalues
            k_spectral = self.primitives.koopman_spectral_score(eigs)
        else:
            k_instability = 0.3
            k_freq        = 0.05
            k_lyapunov    = 0.0
            k_modes_flat  = np.zeros(128)
            k_spectral    = 0.5

        reasoning.append(
            f"Koopman: instability={k_instability:.3f} | freq={k_freq:.4f} Hz | "
            f"Lyapunov={k_lyapunov:.4f} | spectral={k_spectral:.3f}"
        )
        if k_instability > 0.4:
            reasoning.append("⚠  Koopman instability HIGH — regime transition likely")

        # ── Step 4: Mandra Primitive — Sweep Detection ─────────────────
        self._log("Step 4 — Mandra sweep detection...")
        ipda_highs = np.array([ipda_state[f"high_{w}d"] for w in self.IPDA_WINDOWS])
        ipda_lows  = np.array([ipda_state[f"low_{w}d"]  for w in self.IPDA_WINDOWS])
        sweep_scores = self.primitives.liquidity_sweep_detector(
            high[-20:], low[-20:], ipda_highs, ipda_lows, atr[-20:]
        )
        sweep_score = float(sweep_scores[-1]) if len(sweep_scores) > 0 else 0.0
        reasoning.append(f"Mandra sweep score={sweep_score:.3f} (last bar)")
        if sweep_score > 0.5:
            reasoning.append("⚠  Active liquidity sweep detected — stop hunt underway")

        # ── Step 5: Delivery Signature + Memory Retrieval ───────────────
        self._log("Step 5 — Delivery signature encoding + memory query...")
        ohlcv_window = np.column_stack([
            close[-20:], high[-20:], low[-20:],
            df["open"].values[-20:],
            df["volume"].values[-20:] if "volume" in df.columns else np.zeros(20),
        ])
        ipda_feat_vec = np.array([
            ipda_state[f"pos_{w}d"] for w in self.IPDA_WINDOWS
        ] + [adelic_score, tube_confluence, sweep_score, k_instability, k_spectral])

        delivery_vec = self.primitives.delivery_signature_encoder(
            ohlcv_window, ipda_feat_vec, k_modes_flat
        )

        # Query memory for similar historical episodes
        similar = self.memory.query_similar(delivery_vec, n_results=5)
        n_similar = len(similar) if similar else 0
        if n_similar > 0 and isinstance(similar[0], DeliverySignature):
            outcomes = [s.outcome for s in similar if s.outcome is not None]
            similar_outcome_mean = float(np.mean(outcomes)) if outcomes else 0.0
            rev_ratio = sum(1 for s in similar if s.regime == "reversal") / n_similar
        else:
            similar_outcome_mean = 0.0
            rev_ratio = 0.35  # prior

        reasoning.append(
            f"Memory: {n_similar} similar episodes retrieved | "
            f"historical reversal ratio={rev_ratio:.2f} | "
            f"mean outcome={similar_outcome_mean:.5f}"
        )

        # Store this episode
        sig_obj = DeliverySignature(
            vector=delivery_vec,
            timestamp=datetime.now().isoformat(),
            pair=self.pair,
            regime=self.sos27.current_regime.value,
            outcome=None,  # filled in post-trade
            metadata={"ipda_windows": self.IPDA_WINDOWS},
        )
        self.memory.store(sig_obj, f"{self.pair}_{int(time.time()*1000)}")

        # ── Step 6: SOS-27 Regime Classification ────────────────────────
        self._log("Step 6 — SOS-27 regime classification...")
        price_pos_60d = float(ipda_state.get("pos_60d", 0.5))
        atr_pct = float(atr[-1] / (cur_close + 1e-10))

        # Quarterly cycle proximity
        trading_day_count = len(df)
        cycle_pos = trading_day_count % 63
        cycle_nearness = 1.0 - abs(cycle_pos - 31.5) / 31.5  # 1.0 at cycle boundary

        regime = self.sos27.update(
            sweep_score, k_instability, tube_confluence,
            atr_pct, price_pos_60d,
        )
        reasoning.append(f"SOS-27 regime: {regime.value.upper()}")

        # ── Step 7: Reversal Probability Fusion ─────────────────────────
        self._log("Step 7 — Bayesian reversal probability fusion...")
        reversal_prob, components = self.fusion.fuse(
            adelic_score, k_instability, sweep_score,
            rev_ratio, regime, cycle_nearness,
        )
        reasoning.append(
            f"Reversal P = {reversal_prob:.3f}  |  "
            + "  ".join(f"{k}={v:.2f}" for k, v in components.items())
        )

        # ── Step 8: Circuit Breaker Arbitration ─────────────────────────
        self._log("Step 8 — Circuit breaker check...")
        breakers_active = []

        if k_instability > 0.65:
            self.state_store.trip_breaker("koopman_instability_high",
                                          f"instability={k_instability:.3f}")
            breakers_active.append("koopman_instability_high")

        if sweep_score > 0.85:
            self.state_store.trip_breaker("liquidity_sweep_active",
                                          f"sweep={sweep_score:.3f}")
            breakers_active.append("liquidity_sweep_active")

        if cycle_nearness > 0.97:
            self.state_store.trip_breaker("quarterly_shift_window",
                                          f"cycle_pos={cycle_pos}")
            breakers_active.append("quarterly_shift_window")

        if tube_confluence > 0.92:
            self.state_store.trip_breaker("adelic_confluence_breach",
                                          f"confluence={tube_confluence:.3f}")
            breakers_active.append("adelic_confluence_breach")

        if breakers_active:
            reasoning.append(f"⚠  Circuit breakers TRIPPED: {', '.join(breakers_active)}")

        # ── Step 9: Signal Emission ──────────────────────────────────────
        self._log("Step 9 — Signal emission...")
        if self.state_store.any_tripped():
            direction  = SignalDirection.HALT
            confidence = 0.0
        elif reversal_prob >= 0.65:
            direction  = (SignalDirection.SHORT if price_pos_60d > 0.5
                          else SignalDirection.LONG)
            confidence = (reversal_prob - 0.65) / 0.35
        elif reversal_prob >= 0.45:
            direction  = SignalDirection.NEUTRAL
            confidence = reversal_prob - 0.45
        else:
            direction  = SignalDirection.NEUTRAL
            confidence = 0.0

        # Entry zone: adelic tube around current close
        entry_lo = cur_close - epsilon * 0.5
        entry_hi = cur_close + epsilon * 0.5
        # Invalidation: beyond nearest IPDA level in signal direction
        if direction == SignalDirection.SHORT:
            invalidation = float(ipda_state["high_20d"]) + float(atr[-1]) * 0.5
        elif direction == SignalDirection.LONG:
            invalidation = float(ipda_state["low_20d"]) - float(atr[-1]) * 0.5
        else:
            invalidation = cur_close

        elapsed = (time.time() - t0) * 1000
        reasoning.append(f"Pipeline completed in {elapsed:.1f}ms")

        state = IPDAState(
            timestamp=datetime.now().isoformat(),
            pair=self.pair,
            close=cur_close,
            high=float(high[-1]),
            low=float(low[-1]),
            ipda_20d_high=float(ipda_state["high_20d"]),
            ipda_20d_low=float(ipda_state["low_20d"]),
            ipda_40d_high=float(ipda_state["high_40d"]),
            ipda_40d_low=float(ipda_state["low_40d"]),
            ipda_60d_high=float(ipda_state["high_60d"]),
            ipda_60d_low=float(ipda_state["low_60d"]),
            adelic_norm=adelic_norm,
            tube_confluence=tube_confluence,
            adelic_levels=inst_levels,
            koopman_instability=k_instability,
            koopman_freq=k_freq,
            lyapunov_exponent=k_lyapunov,
            spectral_score=k_spectral,
            sweep_score=sweep_score,
            delivery_vector=delivery_vec,
            regime=regime,
            reversal_prob=reversal_prob,
            signal=direction,
            confidence=confidence,
            n_similar_episodes=n_similar,
            similar_outcome_mean=similar_outcome_mean,
            breakers_active=breakers_active,
        )

        signal = SentinelSignal(
            timestamp=state.timestamp,
            pair=self.pair,
            direction=direction,
            reversal_prob=reversal_prob,
            confidence=confidence,
            regime=regime,
            entry_zone=(entry_lo, entry_hi),
            invalidation=invalidation,
            adelic_score=adelic_score,
            koopman_score=k_spectral,
            memory_score=rev_ratio,
            reasoning=reasoning,
            raw_state=state,
        )

        return signal

    def print_signal(self, signal: SentinelSignal) -> None:
        """Forensic signal report."""
        d = "▲" if signal.direction == SignalDirection.LONG else (
            "▼" if signal.direction == SignalDirection.SHORT else (
            "⊘" if signal.direction == SignalDirection.HALT else "—"))
        print(f"\n{'═'*65}")
        print(f"  SOS-27-X SENTINEL SIGNAL — {signal.pair}")
        print(f"{'═'*65}")
        print(f"  Time:           {signal.timestamp}")
        print(f"  Direction:      {d}  {signal.direction.value}")
        print(f"  Reversal P:     {signal.reversal_prob*100:.1f}%")
        print(f"  Confidence:     {signal.confidence*100:.1f}%")
        print(f"  Regime:         {signal.regime.value.upper()}")
        print(f"  Entry Zone:     [{signal.entry_zone[0]:.5f}, {signal.entry_zone[1]:.5f}]")
        print(f"  Invalidation:   {signal.invalidation:.5f}")
        print(f"{'─'*65}")
        print(f"  Adelic Score:   {signal.adelic_score:.3f}")
        print(f"  Koopman Score:  {signal.koopman_score:.3f}")
        print(f"  Memory Score:   {signal.memory_score:.3f}")
        if signal.raw_state:
            s = signal.raw_state
            print(f"{'─'*65}")
            print(f"  IPDA 20d:       [{s.ipda_20d_low:.5f}, {s.ipda_20d_high:.5f}]")
            print(f"  IPDA 40d:       [{s.ipda_40d_low:.5f}, {s.ipda_40d_high:.5f}]")
            print(f"  IPDA 60d:       [{s.ipda_60d_low:.5f}, {s.ipda_60d_high:.5f}]")
            print(f"  Sweep Score:    {s.sweep_score:.3f}")
            print(f"  Koopman Inst.:  {s.koopman_instability:.3f}")
            print(f"  Lyapunov Exp.:  {s.lyapunov_exponent:.4f}")
        if signal.raw_state and signal.raw_state.breakers_active:
            print(f"{'─'*65}")
            print(f"  ⚠  CIRCUIT BREAKERS: {', '.join(signal.raw_state.breakers_active)}")
        print(f"{'─'*65}")
        print(f"  FORENSIC AUDIT TRAIL:")
        for i, r in enumerate(signal.reasoning, 1):
            print(f"    {i:02d}. {r}")
        print(f"{'═'*65}\n")
