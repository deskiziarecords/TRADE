"""
core/ipda_window.py
Explicit Component: Time-Decayed Memory & Windowed Extremum Search.

Computes Institutional Price Discovery Addresses (IPDA) across configurable lookbacks.
Maps price to time-decayed memory addresses and extracts rolling support/resistance bounds.

Mathematical Foundation:
$$
\text{IPDA}_k(t) = \sum_{i=t-L_k}^{t} P_i \cdot e^{-\lambda(t-i)}
$$
$$
\text{MemoryAddress}_k(t) = \arg\min_{j} \left| P_t - \text{IPDA}_k(j) \right|
$$
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from typing import Tuple, Dict, Optional

class IPDAWindow:
    def __init__(self, windows: Tuple[int, ...] = (20, 40, 60), decay_rate: float = 0.15):
        self.windows = np.array(windows, dtype=int)
        self.lambda_ = decay_rate
        self._weights_cache: Dict[int, np.ndarray] = {}

    def _get_weights(self, L: int) -> np.ndarray:
        if L not in self._weights_cache:
            self._weights_cache[L] = np.exp(-self.lambda_ * np.arange(L)[::-1])
        return self._weights_cache[L]

    def compute_memory_matrix(self, prices: np.ndarray) -> np.ndarray:
        """Returns shape (N, K) decayed memory values for each window."""
        prices = np.asarray(prices, dtype=np.float64)
        N = len(prices)
        K = len(self.windows)
        matrix = np.full((N, K), np.nan)

        for k, L in enumerate(self.windows):
            if L > N:
                continue
            win_view = sliding_window_view(prices, L)
            matrix[L-1:, k] = win_view @ self._get_weights(L)
        return matrix

    def extract_extremums(self, ipda_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (support, resistance) arrays aligned to price timeline."""
        valid = ~np.isnan(ipda_matrix).all(axis=1)
        sup = np.where(valid, np.min(ipda_matrix[:, 1:], axis=1), np.nan)
        res = np.where(valid, np.max(ipda_matrix[:, 1:], axis=1), np.nan)
        return sup, res

    def map_memory_addresses(self, prices: np.ndarray, ipda_matrix: np.ndarray) -> np.ndarray:
        """Returns nearest historical memory address index for each bar."""
        addresses = np.full(len(prices), -1, dtype=int)
        for k in range(1, ipda_matrix.shape[1]):
            col = ipda_matrix[:, k]
            valid = ~np.isnan(col)
            if not valid.any():
                continue
            # Vectorized nearest-neighbor search (approximate for speed)
            diffs = np.abs(prices[:, None] - col[None, :])
            diffs[:, ~valid] = np.inf
            addresses = np.minimum(addresses, np.argmin(diffs, axis=1), out=addresses, where=valid.any(axis=0))
        return addresses
