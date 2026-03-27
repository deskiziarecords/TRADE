"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          ADELIC-KOOPMAN IPDA TRADING SYSTEM — CORE MATHEMATICS              ║
║          SOS-27-X Sentinel Production Orchestrator                          ║
║                                                                              ║
║  Math Stack:                                                                 ║
║    • Adelic Tube Refinement   — Non-Archimedean price geometry               ║
║    • Koopman Operator Theory  — Infinite-dim linearization of market flow    ║
║    • Mandra JAX-XLA Kernels   — Hardware-accelerated primitives              ║
║    • ChromaDB                 — 384-dim delivery signature memory            ║
║    • Redis                    — Global state & circuit breakers              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
import warnings
warnings.filterwarnings("ignore")

# ─── JAX / Mandra primitives (with CPU fallback) ─────────────────────────────
try:
    import jax
    import jax.numpy as jnp
    from jax import jit, vmap, grad
    JAX_AVAILABLE = True
except ImportError:
    import numpy as jnp
    JAX_AVAILABLE = False
    def jit(fn): return fn
    def vmap(fn): return fn

# ─────────────────────────────────────────────────────────────────────────────
# I.  NON-ARCHIMEDEAN / ADELIC GEOMETRY
# ─────────────────────────────────────────────────────────────────────────────

class AdelicPriceGeometry:
    """
    Adelic number theory applied to price delivery.

    An adelic price coordinate x = (x_∞, x_2, x_3, x_5, x_7, ...) where:
      - x_∞  is the real (Archimedean) price
      - x_p  is the p-adic valuation component for prime p

    The p-adic valuation v_p(x) measures the "depth" of a price level
    in the p-adic metric: levels with high p-adic depth are
    institutionally significant (deep liquidity).

    Adelic tube T_ε(x₀) = { x : |x - x₀|_∞ < ε } ∩ { x : |x - x₀|_p ≤ 1 ∀p }
    defines the zone of adelic price confluence.
    """

    PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

    def __init__(self, price_scale: float = 1e4):
        self.price_scale = price_scale  # e.g. 10000 for EURUSD pips

    def p_adic_valuation(self, price: float, p: int) -> int:
        """
        Compute v_p(price_int) = largest k such that p^k | price_int.
        Higher valuation → price is divisible by high powers of p →
        strong institutional memory level.
        """
        x = int(round(abs(price) * self.price_scale))
        if x == 0:
            return 99  # zero has infinite valuation
        v = 0
        while x % p == 0:
            x //= p
            v += 1
        return v

    def adelic_norm(self, price: float) -> float:
        """
        Adelic product formula: ∏_p |x|_p · |x|_∞ = 1  (Artin product formula)
        Returns combined adelic significance score.
        """
        if price == 0:
            return 0.0
        x_int = int(round(abs(price) * self.price_scale))
        product = 1.0
        for p in self.PRIMES:
            v = self.p_adic_valuation(price, p)
            if v > 0:
                p_adic_abs = p ** (-v)
                product *= p_adic_abs
        # Adelic significance: inverse of product (high score = institutionally deep)
        return 1.0 / (product + 1e-12)

    def adelic_tube(self,
                    center: float,
                    prices: np.ndarray,
                    epsilon_real: float,
                    p_depth_min: int = 2) -> np.ndarray:
        """
        Adelic Tube Refinement:
        Returns mask of prices inside the adelic tube around `center`.

        T_ε(center) = prices within ε_real AND p-adic depth ≥ p_depth_min
        for at least one prime p.
        """
        real_mask = np.abs(prices - center) < epsilon_real
        p_adic_mask = np.zeros(len(prices), dtype=bool)
        for i, p_candidate in enumerate(prices):
            for prime in self.PRIMES[:5]:
                if self.p_adic_valuation(p_candidate, prime) >= p_depth_min:
                    p_adic_mask[i] = True
                    break
        return real_mask & p_adic_mask

    def institutional_levels(self,
                             prices: np.ndarray,
                             top_n: int = 10) -> np.ndarray:
        """
        Score each price by adelic significance.
        Returns indices of top_n institutionally significant levels.
        """
        scores = np.array([self.adelic_norm(p) for p in prices])
        return np.argsort(scores)[-top_n:][::-1]

    def tube_confluence_score(self,
                               price: float,
                               levels: np.ndarray,
                               epsilon: float) -> float:
        """
        How many adelic tubes from `levels` contain `price`?
        Returns normalized confluence score [0, 1].
        """
        count = sum(
            1 for lvl in levels
            if abs(price - lvl) < epsilon and
               any(self.p_adic_valuation(lvl, p) >= 2 for p in self.PRIMES[:5])
        )
        return min(count / max(len(levels), 1), 1.0)


# ─────────────────────────────────────────────────────────────────────────────
# II.  KOOPMAN OPERATOR THEORY
# ─────────────────────────────────────────────────────────────────────────────

class KoopmanOperator:
    """
    Koopman Linearization of Market Dynamics.

    The Koopman operator K acts on observable functions g: X → ℝ as:
        (Kg)(x) = g(F(x))
    where F: X → X is the (nonlinear) market state evolution map.

    Key insight: K is LINEAR and infinite-dimensional, even if F is nonlinear.
    We approximate K via EDMD (Extended Dynamic Mode Decomposition) using
    a dictionary of IPDA-relevant observables.

    Observable dictionary Ψ(x) includes:
      - Price deviations from IPDA levels
      - Adelic tube membership functions
      - Rolling statistical moments
      - Liquidity proxy functions
    """

    def __init__(self,
                 n_observables: int = 64,
                 n_modes: int = 32,
                 dt: float = 1.0):
        self.n_obs  = n_observables
        self.n_modes = n_modes
        self.dt      = dt
        self.K_matrix: Optional[np.ndarray] = None
        self.eigenvalues: Optional[np.ndarray] = None
        self.eigenvectors: Optional[np.ndarray] = None
        self.phi_x: Optional[np.ndarray] = None   # Koopman modes at current state
        self._fitted = False

    def _build_observable_dictionary(self,
                                      X: np.ndarray,
                                      ipda_levels: Optional[np.ndarray] = None) -> np.ndarray:
        """
        EDMD dictionary Ψ(x) ∈ ℝ^{n_obs}.
        Observables: polynomial, trigonometric, IPDA-distance functions.
        """
        n_samples, n_features = X.shape
        Psi = []

        # 1. Identity (linear observables)
        Psi.append(X)

        # 2. Polynomial observables (degree 2)
        for i in range(min(n_features, 8)):
            Psi.append((X[:, i:i+1] ** 2))
            if i + 1 < n_features:
                Psi.append((X[:, i:i+1] * X[:, i+1:i+2]))

        # 3. Trigonometric observables (Fourier basis)
        for k in range(1, 5):
            Psi.append(np.sin(k * np.pi * X[:, :min(n_features, 4)]))
            Psi.append(np.cos(k * np.pi * X[:, :min(n_features, 4)]))

        # 4. IPDA-level distance observables
        if ipda_levels is not None:
            for lvl in ipda_levels[:5]:
                dist = X[:, 0:1] - lvl   # distance from IPDA level
                Psi.append(np.exp(-0.5 * (dist / 0.001) ** 2))  # Gaussian kernel

        # 5. Rolling range position (discount/premium indicator)
        if n_features >= 3:
            rng = X[:, 1:2] - X[:, 2:3]  # high - low
            safe_rng = np.where(np.abs(rng) < 1e-10, 1e-10, rng)
            Psi.append((X[:, 0:1] - X[:, 2:3]) / safe_rng)

        Psi_matrix = np.hstack(Psi)

        # Trim or pad to n_obs
        if Psi_matrix.shape[1] > self.n_obs:
            Psi_matrix = Psi_matrix[:, :self.n_obs]
        elif Psi_matrix.shape[1] < self.n_obs:
            pad = np.zeros((n_samples, self.n_obs - Psi_matrix.shape[1]))
            Psi_matrix = np.hstack([Psi_matrix, pad])

        return Psi_matrix

    def fit(self,
            X: np.ndarray,
            ipda_levels: Optional[np.ndarray] = None) -> "KoopmanOperator":
        """
        EDMD: fit Koopman matrix K from snapshot pairs (X_t, X_{t+1}).
        K = Ψ(X_{t+1})^T · pinv(Ψ(X_t)^T)
        """
        assert len(X) > 1, "Need at least 2 time steps"

        X_now  = X[:-1]
        X_next = X[1:]

        Psi_now  = self._build_observable_dictionary(X_now,  ipda_levels)
        Psi_next = self._build_observable_dictionary(X_next, ipda_levels)

        # Least-squares fit: K @ Psi_now^T ≈ Psi_next^T
        # K = Psi_next^T @ pinv(Psi_now^T)
        self.K_matrix = Psi_next.T @ np.linalg.pinv(Psi_now.T)

        # Eigendecomposition
        eigvals, eigvecs = np.linalg.eig(self.K_matrix)
        # Sort by magnitude (dominant modes first)
        idx = np.argsort(np.abs(eigvals))[::-1]
        self.eigenvalues  = eigvals[idx[:self.n_modes]]
        self.eigenvectors = eigvecs[:, idx[:self.n_modes]]

        # Store current observable state
        self.phi_x = Psi_now[-1:]   # last snapshot

        self._fitted = True
        return self

    def predict_modes(self, steps: int = 5) -> np.ndarray:
        """
        Propagate Koopman modes forward `steps` time steps.
        z_{t+k} = K^k · z_t
        Returns array of shape (steps, n_modes) with mode amplitudes.
        """
        assert self._fitted, "Call .fit() first"
        K_pow = np.eye(self.K_matrix.shape[0], dtype=complex)
        amplitudes = []
        z = self.phi_x @ self.eigenvectors  # project onto eigenbasis
        for _ in range(steps):
            K_pow = K_pow @ self.K_matrix
            z_future = z @ np.linalg.matrix_power(
                np.diag(self.eigenvalues), 1
            )
            amplitudes.append(np.abs(z_future).real.flatten()[:self.n_modes])
            z = z_future
        return np.array(amplitudes)

    def dominant_frequency(self) -> float:
        """
        Extract dominant oscillation frequency from Koopman spectrum.
        ω = Im(log(λ)) / (2π·dt)
        """
        if not self._fitted:
            return 0.0
        log_eigs = np.log(self.eigenvalues + 1e-12)
        freqs = np.abs(log_eigs.imag) / (2 * np.pi * self.dt)
        dominant_idx = np.argmax(np.abs(self.eigenvalues))
        return float(freqs[dominant_idx])

    def instability_index(self) -> float:
        """
        Koopman spectral instability: fraction of eigenvalues |λ| > 1.
        Values > 0.3 indicate regime transition imminent.
        """
        if not self._fitted:
            return 0.0
        return float(np.mean(np.abs(self.eigenvalues) > 1.0))

    def lyapunov_exponent(self) -> float:
        """
        Approximate maximal Lyapunov exponent from dominant Koopman eigenvalue.
        λ_L = Re(log(λ_max)) / dt
        """
        if not self._fitted:
            return 0.0
        dominant_eig = self.eigenvalues[0]
        return float(np.log(np.abs(dominant_eig) + 1e-12) / self.dt)


# ─────────────────────────────────────────────────────────────────────────────
# III.  MANDRA JAX-XLA PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────

class MandraPrimitives:
    """
    Mandra JAX-XLA kernel wrappers.
    Provides hardware-accelerated (GPU/TPU via XLA when available, CPU fallback)
    implementations of the core IPDA signal computations.
    """

    @staticmethod
    @jit
    def ipda_range_scan(prices: np.ndarray, windows: np.ndarray) -> np.ndarray:
        """
        Vectorized IPDA 20/40/60-day range computation.
        Returns (n_windows, n_prices, 3) array of [high, low, position].
        """
        results = []
        for w in windows:
            w = int(w)
            highs = np.array([prices[max(0, i-w):i+1].max() for i in range(len(prices))])
            lows  = np.array([prices[max(0, i-w):i+1].min() for i in range(len(prices))])
            rng   = np.where(highs - lows < 1e-10, 1e-10, highs - lows)
            pos   = (prices - lows) / rng
            results.append(np.stack([highs, lows, pos], axis=-1))
        return np.stack(results, axis=0)

    @staticmethod
    @jit
    def koopman_spectral_score(eigenvalues: np.ndarray) -> float:
        """
        XLA-compiled spectral health score.
        Score ∈ [0, 1] where 1 = perfectly cyclic (pure imaginary eigenvalues).
        """
        mags = np.abs(eigenvalues)
        phases = np.angle(eigenvalues)
        cyclicity = np.mean(np.abs(np.sin(phases)))   # 1 if purely oscillatory
        stability = np.mean(mags <= 1.0).astype(float)
        return float(0.6 * cyclicity + 0.4 * stability)

    @staticmethod
    @jit
    def liquidity_sweep_detector(high: np.ndarray,
                                  low: np.ndarray,
                                  ipda_highs: np.ndarray,
                                  ipda_lows: np.ndarray,
                                  atr: np.ndarray) -> np.ndarray:
        """
        Vectorized stop-hunt / liquidity sweep detection across all IPDA windows.
        Returns sweep score per bar ∈ [0, 1].
        """
        n = len(high)
        scores = np.zeros(n)
        for i in range(n):
            sweep_score = 0.0
            if atr[i] < 1e-10:
                continue
            # Check breach of each IPDA level
            for j in range(len(ipda_highs)):
                if high[i] > ipda_highs[j]:
                    overshoot = (high[i] - ipda_highs[j]) / atr[i]
                    sweep_score += min(overshoot, 1.0)
                if low[i] < ipda_lows[j]:
                    overshoot = (ipda_lows[j] - low[i]) / atr[i]
                    sweep_score += min(overshoot, 1.0)
            scores[i] = min(sweep_score / max(len(ipda_highs) * 2, 1), 1.0)
        return scores

    @staticmethod
    @jit
    def delivery_signature_encoder(ohlcv_window: np.ndarray,
                                    ipda_features: np.ndarray,
                                    koopman_modes: np.ndarray) -> np.ndarray:
        """
        Encode a price delivery episode into a 384-dimensional vector
        for ChromaDB storage/retrieval.

        Segments:
          [0:64]   — OHLCV statistical moments (mean, std, skew, kurt per field)
          [64:192] — IPDA feature embedding (normalized)
          [192:320] — Koopman mode amplitudes
          [320:384] — Adelic significance fingerprint
        """
        sig = np.zeros(384)

        # Segment 1: OHLCV moments (64 dims)
        n_channels = min(ohlcv_window.shape[1] if ohlcv_window.ndim > 1 else 1, 5)
        for ch in range(n_channels):
            col = ohlcv_window[:, ch] if ohlcv_window.ndim > 1 else ohlcv_window
            if len(col) > 0:
                idx = ch * 4
                sig[idx]     = float(np.mean(col))
                sig[idx + 1] = float(np.std(col) + 1e-12)
                centered = col - np.mean(col)
                std = np.std(col) + 1e-12
                sig[idx + 2] = float(np.mean(centered**3) / std**3)   # skewness
                sig[idx + 3] = float(np.mean(centered**4) / std**4)   # kurtosis

        # Segment 2: IPDA features (128 dims)
        n_ipda = min(len(ipda_features), 128)
        sig[64:64 + n_ipda] = ipda_features[:n_ipda]

        # Segment 3: Koopman modes (128 dims)
        n_koop = min(len(koopman_modes), 128)
        sig[192:192 + n_koop] = koopman_modes[:n_koop]

        # Segment 4: Adelic fingerprint (64 dims) — high-freq p-adic pattern
        if ohlcv_window.ndim > 1:
            close_vals = ohlcv_window[:, 0]
        else:
            close_vals = ohlcv_window
        for i, val in enumerate(close_vals[:64]):
            sig[320 + i] = float(val * (i + 1) % 1.0)   # modular encoding

        # L2-normalize for cosine similarity in ChromaDB
        norm = np.linalg.norm(sig)
        return sig / (norm + 1e-12)


# ─────────────────────────────────────────────────────────────────────────────
# IV.  DELIVERY SIGNATURE MEMORY (ChromaDB Interface)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DeliverySignature:
    """A 384-dim encoded price delivery episode."""
    vector:    np.ndarray          # 384-dim embedding
    timestamp: str
    pair:      str
    regime:    str                 # "expansion" | "reversal" | "consolidation"
    outcome:   Optional[float]     # realized P&L / price move
    metadata:  Dict[str, Any] = field(default_factory=dict)


class DeliverySignatureMemory:
    """
    ChromaDB-backed semantic memory for delivery signatures.
    Falls back to in-memory numpy store if ChromaDB not available.
    """

    def __init__(self, collection_name: str = "ipda_signatures"):
        self.collection_name = collection_name
        self._memory: List[DeliverySignature] = []
        self._use_chroma = False

        try:
            import chromadb
            self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._use_chroma = True
        except ImportError:
            pass   # numpy fallback

    def store(self, sig: DeliverySignature, doc_id: str) -> None:
        """Store a delivery signature in memory."""
        if self._use_chroma:
            self._collection.add(
                ids=[doc_id],
                embeddings=[sig.vector.tolist()],
                metadatas=[{
                    "pair":    sig.pair,
                    "regime":  sig.regime,
                    "outcome": str(sig.outcome),
                    "ts":      sig.timestamp,
                }],
            )
        else:
            self._memory.append(sig)

    def query_similar(self,
                      query_vector: np.ndarray,
                      n_results: int = 5,
                      regime_filter: Optional[str] = None) -> List[DeliverySignature]:
        """Retrieve most similar historical delivery signatures."""
        if self._use_chroma:
            where = {"regime": regime_filter} if regime_filter else None
            results = self._collection.query(
                query_embeddings=[query_vector.tolist()],
                n_results=n_results,
                where=where,
            )
            return results
        else:
            if not self._memory:
                return []
            similarities = []
            for sig in self._memory:
                cos_sim = float(np.dot(query_vector, sig.vector) /
                                (np.linalg.norm(query_vector) * np.linalg.norm(sig.vector) + 1e-12))
                similarities.append((cos_sim, sig))
            similarities.sort(key=lambda x: x[0], reverse=True)
            filtered = [s for _, s in similarities
                        if regime_filter is None or s.regime == regime_filter]
            return filtered[:n_results]

    def __len__(self) -> int:
        if self._use_chroma:
            return self._collection.count()
        return len(self._memory)


# ─────────────────────────────────────────────────────────────────────────────
# V.   GLOBAL STATE & CIRCUIT BREAKERS (Redis Interface)
# ─────────────────────────────────────────────────────────────────────────────

class SentinelState:
    """
    Redis-backed global state manager with circuit breakers.
    Falls back to dict-based in-process state if Redis unavailable.
    """

    CIRCUIT_BREAKER_KEYS = [
        "adelic_confluence_breach",
        "koopman_instability_high",
        "liquidity_sweep_active",
        "quarterly_shift_window",
        "max_drawdown_breach",
        "volatility_regime_spike",
    ]

    def __init__(self):
        self._state: Dict[str, Any] = {}
        self._use_redis = False

        try:
            import redis
            self._redis = redis.Redis(host="localhost", port=6379, decode_responses=True)
            self._redis.ping()
            self._use_redis = True
        except Exception:
            pass  # dict fallback

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if self._use_redis:
            self._redis.set(key, str(value), ex=ttl)
        else:
            self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        if self._use_redis:
            val = self._redis.get(key)
            return val if val is not None else default
        return self._state.get(key, default)

    def trip_breaker(self, breaker: str, reason: str = "") -> None:
        self.set(f"cb:{breaker}", "TRIPPED")
        self.set(f"cb:{breaker}:reason", reason)

    def reset_breaker(self, breaker: str) -> None:
        self.set(f"cb:{breaker}", "CLEAR")

    def is_tripped(self, breaker: str) -> bool:
        return self.get(f"cb:{breaker}", "CLEAR") == "TRIPPED"

    def any_tripped(self) -> bool:
        return any(self.is_tripped(b) for b in self.CIRCUIT_BREAKER_KEYS)

    def status_report(self) -> Dict[str, str]:
        return {b: self.get(f"cb:{b}", "CLEAR") for b in self.CIRCUIT_BREAKER_KEYS}
