"""
core/misalign_spectral.py
Hidden Engine: Fourier Phase Analysis & Desynchronization Detection.

Monitors phase coherence between price momentum and volume participation.
Acts as an early-warning "knock sensor" for regime breakdowns.

Mathematical Foundation:
$$
M(\omega) = \left| \angle \mathcal{F}\{V(t)\} - \angle \mathcal{F}\{P(t)\} \right|
$$
$$
\text{SyncScore} = 1 - \frac{M_{\text{avg}}}{\pi}
$$
"""

import numpy as np
from scipy.fft import fft, fftfreq
from scipy.signal import windows
from typing import Tuple, Dict

class MisalignSpectral:
    def __init__(self, fft_window: int = 128, overlap: float = 0.5, freq_band: Tuple[float, float] = (0.02, 0.18)):
        self.L = fft_window
        self.step = max(1, int(self.L * (1 - overlap)))
        self.freq_band = freq_band
        self._win = windows.hann(self.L, sym=False)
        self._freqs = fftfreq(self.L, d=1.0)

    @staticmethod
    def _circular_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return np.abs(np.angle(np.exp(1j * (a - b))))

    def compute_misalignment(self, prices: np.ndarray, volume: np.ndarray) -> Dict[str, np.ndarray]:
        p = (prices - np.nanmean(prices)) / (np.nanstd(prices) + 1e-9)
        v = (volume - np.nanmean(volume)) / (np.nanstd(volume) + 1e-9)
        
        mask = (np.abs(self._freqs) >= self.freq_band[0]) & (np.abs(self._freqs) <= self.freq_band[1])
        half = self.L // 2
        valid = mask[1:half]
        
        centers = []
        metrics = []
        
        for start in range(0, len(p) - self.L + 1, self.step):
            P_fft = np.angle(fft(p[start:start+self.L] * self._win))
            V_fft = np.angle(fft(v[start:start+self.L] * self._win))
            
            diff = self._circular_diff(P_fft, V_fft)
            M = np.mean(diff[1:half][valid])
            metrics.append(M)
            centers.append(start + self.L // 2)
            
        if len(metrics) < 2:
            return {"misalignment": np.full_like(prices, np.nan), "sync_score": np.full_like(prices, np.nan)}
        
        M_interp = np.interp(np.arange(len(prices)), centers, metrics)
        sync = 1.0 - (M_interp / np.pi)
        
        return {
            "misalignment": M_interp,
            "sync_score": sync,
            "desync_flag": M_interp > np.nanpercentile(M_interp, 85)
        }
