"""
core/gamma_amplifier.py
Hidden Engine: Second-Order Feedback Loop & Overclocking Detection.

Tracks acceleration curvature and positive feedback cycles. Flags exponential 
run-ups and impending structural breakdowns ("System Crash").

Mathematical Foundation:
$$
\Gamma(t) = \frac{d^2P}{dt^2} + \beta \left(\frac{dP}{dt}\right)^2
$$
$$
\text{CrashRisk} = \mathbb{I}\left(\Gamma > \theta_{\text{crash}} \land \frac{d\Gamma}{dt} < 0\right)
$$
"""

import numpy as np
from typing import Dict, Tuple

class GammaAmplifier:
    def __init__(self, beta: float = 0.45, crash_threshold: float = 3.2, smoothing: int = 5):
        self.beta = beta
        self.theta_crash = crash_threshold
        self.smooth = smoothing

    def _smooth(self, arr: np.ndarray, w: int) -> np.ndarray:
        kernel = np.ones(w) / w
        return np.convolve(arr, kernel, mode='same')

    def compute_feedback(self, prices: np.ndarray) -> Dict[str, np.ndarray]:
        dpdt = np.gradient(prices)
        d2pdt2 = np.gradient(dpdt)
        
        gamma = d2pdt2 + self.beta * (dpdt ** 2)
        gamma_smooth = self._smooth(gamma, self.smooth)
        
        # Normalized acceleration
        gamma_norm = gamma_smooth / (np.nanstd(gamma_smooth) + 1e-9)
        
        # Crash risk: high positive feedback followed by negative curvature change
        dgamma = np.gradient(gamma_norm)
        crash_risk = (gamma_norm > self.theta_crash) & (dgamma < -0.15)
        
        # State encoding: 0=Linear, 1=Accelerating, 2=Overclock, 3=Crash
        state = np.zeros_like(prices, dtype=int)
        state[(gamma_norm > 0.8) & (gamma_norm <= self.theta_crash)] = 1
        state[gamma_norm > self.theta_crash] = 2
        state[crash_risk] = 3
        
        return {
            "gamma_accel": gamma_norm,
            "feedback_state": state,
            "curvature_change": dgamma,
            "crash_flag": crash_risk
        }
