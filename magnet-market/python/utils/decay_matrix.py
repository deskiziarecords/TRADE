"""
utils/decay_matrix.py
Implements the Time-Decayed Memory Matrix for IPDA (Institutional Price Discovery Addresses).
Computes rolling exponential-weighted price references over configurable windows.

Core Formula:
$$
\text{IPDA}_k(t) = \sum_{i=t-L_k}^{t} P_i \cdot e^{-\lambda(t-i)}
$$
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from typing import List, Optional
import pandas as pd


def compute_decay_matrix(
    prices: np.ndarray,
    windows: List[int] = [20, 40, 60],
    decay_rate: float = 0.15
) -> np.ndarray:
    """
    Computes the decayed memory matrix for specified lookback windows.
    
    Parameters
    ----------
    prices : np.ndarray
        1D array of closing prices or OHLCV median.
    windows : List[int]
        List of IPDA memory depths $L_k$ (e.g., [20, 40, 60]).
    decay_rate : float
        Lambda $\\lambda$ controlling time-decay speed. Higher values forget older memory faster.
        
    Returns
    -------
    np.ndarray
        Matrix of shape (N, K) where N = len(prices), K = len(windows).
        Columns correspond to each window in `windows`. Initial NaNs pad incomplete windows.
    """
    prices = np.asarray(prices, dtype=np.float64)
    N = len(prices)
    K = len(windows)
    result = np.full((N, K), np.nan)

    for k, L in enumerate(windows):
        if L > N:
            continue
            
        # Weight vector: [exp(-lambda*(L-1)), ..., exp(0)]
        # Oldest bar gets strongest decay, current bar gets weight = 1
        weights = np.exp(-decay_rate * np.arange(L)[::-1])
        
        # Create overlapping windows without copying memory
        windows_view = sliding_window_view(prices, L)
        
        # Vectorized dot product: each row dotted with decay weights
        result[L-1:, k] = np.dot(windows_view, weights)
        
    return result


def compute_ipda_extremums(
    ipda_matrix: np.ndarray,
    method: str = "local"
) -> np.ndarray:
    """
    Identifies windowed extremum references from the decayed IPDA matrix.
    
    Parameters
    ----------
    ipda_matrix : np.ndarray
        Output from compute_decay_matrix.
    method : str
        'local' for immediate memory peaks, 'global' for session-wide bounds.
        
    Returns
    -------
    np.ndarray
        2D array of (support, resistance) levels per timestep.
    """
    # Ignore NaN rows
    valid_rows = ~np.isnan(ipda_matrix).any(axis=1)
    supports = np.where(valid_rows, np.min(ipda_matrix[:, 1:], axis=1), np.nan)
    resistances = np.where(valid_rows, np.max(ipda_matrix[:, 1:], axis=1), np.nan)
    return np.column_stack((supports, resistances))
