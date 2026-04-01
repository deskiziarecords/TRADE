"""
core/psi_sd_classifier.py
Hidden Engine: Heuristic Pattern Classifier & Liquidity Garbage Collection.

Classifies Supply & Demand imbalances and flags retail liquidity zones for clearance.
Treats choppy/inefficient price action as unallocated memory requiring deallocation.

Mathematical Foundation:
$$
\Psi_{\text{S&D}}(t) = \arg\max_{c} \left[ \frac{1}{|D|} \sum_{d \in D_t} \mathbb{I}(f_{\text{heur}}(d) = c) \right]
$$
$$
\text{Efficiency} = \frac{\|\Delta P\|}{\sum \|\Delta P_i\|} \quad \text{(Fractal Dimension Proxy)}
$$
"""

import numpy as np
from typing import Tuple, Dict

class PSDClassifier:
    def __init__(self, sweep_threshold: float = 1.5, efficiency_floor: float = 0.35):
        self.sweep_thresh = sweep_threshold
        self.eff_floor = efficiency_floor

    def _compute_efficiency(self, prices: np.ndarray, window: int = 20) -> np.ndarray:
        """Rolling price path efficiency (0 = noise, 1 = straight trend)."""
        delta = np.diff(prices, prepend=prices[0])
        net_move = np.abs(np.convolve(delta, np.ones(window), mode='valid'))
        gross_move = np.convolve(np.abs(delta), np.ones(window), mode='valid')
        eff = np.where(gross_move > 0, net_move / gross_move, 0.0)
        return np.concatenate([np.full(window - 1, np.nan), eff])

    def classify_regime(self, prices: np.ndarray, volume: np.ndarray, ipda_spread: np.ndarray) -> Dict[str, np.ndarray]:
        """Returns regime codes: 0=Neutral, 1=Sweep/GC, 2=Expansion, 3=Exhaustion"""
        eff = self._compute_efficiency(prices)
        
        vol_norm = volume / (np.nanmax(volume) + 1e-9)
        spread_norm = ipda_spread / (np.nanmax(ipda_spread) + 1e-9)
        
        regimes = np.zeros_like(prices, dtype=int)
        
        # Heuristic thresholds
        sweep = (spread_norm > self.sweep_thresh) & (eff < self.eff_floor) & (vol_norm > 0.6)
        expansion = (eff > 0.65) & (vol_norm > np.nanpercentile(vol_norm, 75))
        exhaustion = (eff < 0.3) & (vol_norm < 0.4) & (spread_norm > self.sweep_thresh * 0.8)
        
        regimes[sweep] = 1
        regimes[expansion] = 2
        regimes[exhaustion] = 3
        
        return {
            "regime_code": regimes,
            "efficiency": eff,
            "sweep_probability": sweep.astype(float),
            "gc_active": regimes == 1
        }
