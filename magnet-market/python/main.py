"""
main.py
SYNTH-REALITY Engine Orchestration Script.
Executes the full pipeline: IPDA Memory → Potential Field → S&D Garbage Collection 
→ Gamma Feedback → Spectral Misalignment → Signal Router.

Usage:
    python main.py --data data/sample_ohlcv.csv --config config/engine.yaml
"""

import argparse
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional

# Internal imports matching repo structure
from utils.decay_matrix import compute_decay_matrix, compute_ipda_extremums
from utils.fourier_ops import compute_spectral_misalignment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Component Stubs (Would normally live in core/phi_magnet.py, etc.)
# Implemented here for self-contained execution demonstration.
# ─────────────────────────────────────────────────────────────────────────────

def compute_potential_field(
    prices: np.ndarray,
    ipda_refs: np.ndarray,
    gravity: float = 0.72,
    exponent: float = 1.8
) -> np.ndarray:
    """$\Phi_{\text{mag}}$ computation: Euclidean vector attraction toward decayed memory."""
    # Simplified 1D attraction scalar field
    dists = np.abs(prices[:, None] - ipda_refs[None, :])
    # Avoid division by zero
    dists = np.where(dists < 1e-9, 1e-9, dists)
    pull = gravity / (dists ** exponent)
    return np.mean(pull, axis=1)


def compute_gamma_amplifier(
    prices: np.ndarray,
    beta: float = 0.45
) -> np.ndarray:
    """$\Gamma$ second-order feedback loop: $\frac{d^2P}{dt^2} + \beta (\frac{dP}{dt})^2$"""
    dpdt = np.gradient(prices)
    d2pdt2 = np.gradient(dpdt)
    return d2pdt2 + beta * (dpdt ** 2)


def classify_sd_regime(
    ipda_spread: np.ndarray,
    gamma: np.ndarray,
    threshold: float = 1.5
) -> np.ndarray:
    """$\Psi_{\text{S&D}}$ Heuristic Garbage Classifier. Returns regime codes: 0=Neutral, 1=Sweep, 2=Trend"""
    regime = np.zeros_like(gamma)
    sweep_mask = (ipda_spread > threshold) & (np.abs(gamma) < 0.5 * np.std(gamma))
    trend_mask = np.abs(gamma) > np.percentile(np.abs(gamma), 85)
    regime[sweep_mask] = 1  # Liquidity clearing / RAM deallocation
    regime[trend_mask] = 2  # Momentum expansion
    return regime


# ─────────────────────────────────────────────────────────────────────────────
# Main Orchestration
# ─────────────────────────────────────────────────────────────────────────────

def load_data(path: str) -> pd.DataFrame:
    """Loads OHLCV data and validates schema."""
    df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns.str.lower()):
        raise ValueError(f"Missing required columns. Found: {df.columns.tolist()}")
    df.columns = df.columns.str.lower()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values("timestamp").reset_index(drop=True)


def run_engine(df: pd.DataFrame, cfg: Dict[str, Any]) -> pd.DataFrame:
    """Executes the SYNTH-REALITY pipeline and attaches signal states."""
    prices = df["close"].values
    volume = df["volume"].values
    N = len(prices)

    logging.info("[1/5] Computing IPDA Time-Decayed Memory Matrix...")
    ipda_matrix = compute_decay_matrix(
        prices, windows=cfg["ipda"]["windows"], decay_rate=cfg["ipda"]["decay_rate"]
    )
    extremums = compute_ipda_extremums(ipda_matrix)
    ipda_spread = extremums[:, 1] - extremums[:, 0]

    logging.info("[2/5] Mapping Potential Field $\Phi_{\text{mag}}$...")
    phi_mag = compute_potential_field(
        prices, ipda_matrix, 
        gravity=cfg["magnet"]["institutional_gravity"],
        exponent=cfg["magnet"]["attraction_exponent"]
    )

    logging.info("[3/5] Running S&D Garbage Classifier $\Psi_{\text{S&D}}$...")
    # Placeholder gamma computation for classifier input
    gamma_temp = np.gradient(prices)
    regime = classify_sd_regime(ipda_spread, gamma_temp, threshold=cfg["sd"]["sweep_threshold"])

    logging.info("[4/5] Activating Gamma Amplifier $\Gamma$...")
    gamma = compute_gamma_amplifier(prices, beta=cfg["gamma"]["feedback_beta"])

    logging.info("[5/5] Detecting Spectral Misalignment $M$...")
    misalign = compute_spectral_misalignment(
        prices, volume,
        fft_window=cfg["spectral"]["fft_window"],
        freq_band=tuple(cfg["spectral"]["freq_band"])
    )

    # ── Signal Routing Logic ────────────────────────────────────────────────
    signals = []
    for i in range(N):
        if np.isnan(gamma[i]) or np.isnan(misalign[i]):
            signals.append("HOLD")
            continue
            
        # Gate: High misalignment = desynchronization risk (avoid gamma traps)
        if misalign[i] > cfg["spectral"]["misalign_alert"]:
            sig = "EXIT" if gamma[i] > 0 else "FLATTEN"
        elif regime[i] == 1:
            sig = "SWEEP_PREP"
        elif regime[i] == 2:
            sig = "LONG" if gamma[i] > 0 else "SHORT"
        else:
            sig = "NEUTRAL"
        signals.append(sig)

    # Attach to DataFrame
    out = df.copy()
    out["gamma_accel"] = gamma
    out["misalignment_M"] = misalign
    out["phi_attraction"] = phi_mag
    out["regime_code"] = regime
    out["synth_signal"] = signals
    return out


def main():
    parser = argparse.ArgumentParser(description="SYNTH-REALITY Engine v1.0")
    parser.add_argument("--data", type=str, required=True, help="Path to OHLCV CSV/Parquet")
    parser.add_argument("--output", type=str, default="output/synth_signals.csv", help="Signal export path")
    args = parser.parse_args()

    # Default configuration (would typically load from config/engine.yaml)
    config = {
        "ipda": {"windows": [20, 40, 60], "decay_rate": 0.15},
        "magnet": {"attraction_exponent": 1.8, "institutional_gravity": 0.72},
        "sd": {"sweep_threshold": 1.5},
        "gamma": {"feedback_beta": 0.45},
        "spectral": {"fft_window": 128, "freq_band": [0.02, 0.18], "misalign_alert": 0.35}
    }

    logging.info("Initializing SYNTH-REALITY Engine...")
    df = load_data(args.data)
    results = run_engine(df, config)
    
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    logging.info(f"Pipeline complete. Signals saved to {args.output}")


if __name__ == "__main__":
    main()
