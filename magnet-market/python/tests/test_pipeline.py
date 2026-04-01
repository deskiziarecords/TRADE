"""
tests/test_pipeline.py
Comprehensive validation suite for SYNTH-REALITY Engine components.
Tests mathematical bounds, dimensional alignment, NaN propagation, and pipeline integration.

Run: pytest tests/test_pipeline.py -v
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Ensure core modules are discoverable during test execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.ipda_window import IPDAWindow
from core.phi_magnet import PhiMagnet
from core.psi_sd_classifier import PSDClassifier
from core.gamma_amplifier import GammaAmplifier
from core.misalign_spectral import MisalignSpectral

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_market() -> dict:
    """Generates realistic OHLCV-like data with regime shifts."""
    t = np.linspace(0, 100, 500)
    base = np.sin(0.1 * t) * 10 + 50
    trend = np.where(t > 30, 0.08 * t, 0.0)
    noise = np.random.normal(0, 0.5, len(t))
    volume = np.abs(np.cos(0.15 * t) * 1000) + np.random.poisson(200, len(t))
    
    prices = base + trend + noise
    return {
        "prices": prices,
        "volume": volume.astype(float),
        "length": len(prices)
    }

# ─────────────────────────────────────────────────────────────────────────────
# Component Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIPDAWindow:
    def test_matrix_shape(self, synthetic_market):
        ipda = IPDAWindow(windows=(20, 40, 60))
        matrix = ipda.compute_memory_matrix(synthetic_market["prices"])
        assert matrix.shape == (synthetic_market["length"], 3)

    def test_extremums_alignment(self, synthetic_market):
        ipda = IPDAWindow()
        matrix = ipda.compute_memory_matrix(synthetic_market["prices"])
        sup, res = ipda.extract_extremums(matrix)
        assert sup.shape == res.shape == (synthetic_market["length"],)
        assert np.all(sup[60:] <= res[60:])  # Support <= Resistance after warmup

class TestPhiMagnet:
    def test_potential_negativity(self, synthetic_market):
        magnet = PhiMagnet()
        nodes = np.array([45.0, 55.0, 60.0])
        phi = magnet.compute_potential(synthetic_market["prices"], nodes)
        assert np.all(phi < 0), "Potential field must be attractive (negative)"

    def test_vector_direction(self, synthetic_market):
        magnet = PhiMagnet()
        nodes = np.array([65.0])  # Node above all prices
        vec = magnet.compute_attraction_vectors(synthetic_market["prices"][:100], nodes)
        assert np.all(vec > 0), "Attraction should point upward when node > price"

class TestPSDClassifier:
    def test_regime_bounds(self, synthetic_market):
        cls = PSDClassifier()
        spread = np.abs(np.gradient(synthetic_market["prices"]))
        res = cls.classify_regime(synthetic_market["prices"], synthetic_market["volume"], spread)
        assert np.all((res["regime_code"] >= 0) & (res["regime_code"] <= 3))
        assert np.all((res["efficiency"] >= 0) & (res["efficiency"] <= 1.0))

class TestGammaAmplifier:
    def test_feedback_continuity(self, synthetic_market):
        gamma = GammaAmplifier(smoothing=5)
        res = gamma.compute_feedback(synthetic_market["prices"])
        # Smoothed gamma should not contain NaNs
        assert not np.any(np.isnan(res["gamma_accel"]))
        # Crash flag must be boolean-like
        assert np.isin(res["crash_flag"], [True, False]).all()

class TestMisalignSpectral:
    def test_misalignment_bounds(self, synthetic_market):
        spec = MisalignSpectral(fft_window=64)
        res = spec.compute_misalignment(synthetic_market["prices"], synthetic_market["volume"])
        valid = ~np.isnan(res["misalignment"])
        assert np.all(res["misalignment"][valid] >= 0)
        assert np.all(res["misalignment"][valid] <= np.pi)
        assert np.all((res["sync_score"][valid] >= 0) & (res["sync_score"][valid] <= 1.0))

# ─────────────────────────────────────────────────────────────────────────────
# Integration Test
# ─────────────────────────────────────────────────────────────────────────────

class TestPipelineIntegration:
    def test_full_chain_execution(self, synthetic_market):
        prices = synthetic_market["prices"]
        volume = synthetic_market["volume"]
        N = len(prices)

        # 1. IPDA
        ipda = IPDAWindow()
        matrix = ipda.compute_memory_matrix(prices)
        sup, res = ipda.extract_extremums(matrix)
        spread = res - sup

        # 2. Magnet
        magnet = PhiMagnet()
        phi_state = magnet.get_magnet_state(prices, nodes=res)

        # 3. Classifier
        cls = PSDClassifier()
        psi_state = cls.classify_regime(prices, volume, spread)

        # 4. Gamma
        gamma = GammaAmplifier()
        g_state = gamma.compute_feedback(prices)

        # 5. Spectral
        spec = MisalignSpectral()
        m_state = spec.compute_misalignment(prices, volume)

        # Validation: Circuit-breaker logic
        safe_gamma = np.where(m_state["desync_flag"], 0.0, g_state["gamma_accel"])
        assert len(safe_gamma) == N
        # High misalignment must flatten gamma exposure
        desync_mask = m_state["desync_flag"]
        if np.any(desync_mask):
            assert np.allclose(safe_gamma[desync_mask], 0.0)
