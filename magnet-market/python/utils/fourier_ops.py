"""
utils/fourier_ops.py
Implements Spectral Misalignment $M$ via Fourier Phase Analysis.
Detects desynchronization between price momentum and volume participation.

Core Formula:
$$
M(\omega) = \left| \angle \mathcal{F}\{V(t)\} - \angle \mathcal{F}\{P(t)\} \right|
$$
"""

import numpy as np
from scipy.fft import fft, fftfreq
from scipy.signal import windows
from typing import Tuple, Optional


def _circular_diff(phi_a: np.ndarray, phi_b: np.ndarray) -> np.ndarray:
    """Computes robust circular phase difference handling $(-\pi, \pi]$ wrap-around."""
    return np.abs(np.angle(np.exp(1j * (phi_a - phi_b))))


def compute_spectral_misalignment(
    prices: np.ndarray,
    volume: np.ndarray,
    fft_window: int = 128,
    overlap: float = 0.5,
    freq_band: Tuple[float, float] = (0.02, 0.18),
    fs: float = 1.0
) -> np.ndarray:
    """
    Computes rolling spectral misalignment between price and volume.
    
    Parameters
    ----------
    prices : np.ndarray
        1D price series.
    volume : np.ndarray
        1D volume series (must match length of prices).
    fft_window : int
        FFT segment length $L_{\text{fft}}$. Power of 2 recommended.
    overlap : float
        Segment overlap ratio $[0.0, 1.0)$.
    freq_band : Tuple[float, float]
        Normalized frequency band $[\omega_{\min}, \omega_{\max}]$ for misalignment averaging.
    fs : float
        Sampling frequency (e.g., 1.0 for bar-based data).
        
    Returns
    -------
    np.ndarray
        1D array of misalignment values $M(t)$, interpolated to original length.
        High values indicate "engine knock" (phase divergence before structural break).
    """
    assert len(prices) == len(volume), "Price and volume arrays must match in length."
    
    # Z-score normalization for stationary FFT input
    p_norm = (prices - np.mean(prices)) / (np.std(prices) + 1e-9)
    v_norm = (volume - np.mean(volume)) / (np.std(volume) + 1e-9)
    
    step = max(1, int(fft_window * (1 - overlap)))
    segment_m = []
    segment_centers = []
    
    win_func = windows.hann(fft_window, sym=False)
    freqs = fftfreq(fft_window, d=1.0/fs)
    
    # Frequency band mask (positive frequencies only, skip DC)
    mask = (np.abs(freqs) >= freq_band[0]) & (np.abs(freqs) <= freq_band[1])
    half = fft_window // 2
    valid_freqs = mask[1:half]
    
    for start in range(0, len(p_norm) - fft_window + 1, step):
        p_seg = p_norm[start:start+fft_window] * win_func
        v_seg = v_norm[start:start+fft_window] * win_func
        
        # FFT & Phase Extraction
        P_fft = fft(p_seg)
        V_fft = fft(v_seg)
        
        phase_p = np.angle(P_fft)
        phase_v = np.angle(V_fft)
        
        # Circular phase difference in target band
        diff = _circular_diff(phase_p, phase_v)
        M_val = np.mean(diff[1:half][valid_freqs])
        
        segment_m.append(M_val)
        segment_centers.append(start + fft_window // 2)
        
    # Interpolate to original timeline for pipeline alignment
    if len(segment_m) < 2:
        return np.full_like(prices, np.nan)
        
    return np.interp(np.arange(len(prices)), segment_centers, segment_m)
