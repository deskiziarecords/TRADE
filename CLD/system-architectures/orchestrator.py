"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   MULTI-ASSET ADELIC-KOOPMAN + CAUSAL TRANSMISSION ORCHESTRATOR             ║
║   Module: multi_asset_orchestrator.py                                       ║
║                                                                              ║
║   This module fuses:                                                         ║
║     1. Per-asset SOS-27-X Sentinel reversal probabilities                   ║
║     2. Cross-asset causal transmission signals                               ║
║     3. Causal graph topology to amplify or suppress per-asset signals       ║
║                                                                              ║
║   Key upgrade over single-asset system:                                     ║
║     If BTC just reversed AND BTC→ETH edge strength = 0.7,                  ║
║     ETH's reversal P is amplified by the causal prior.                      ║
║                                                                              ║
║   Asset Universes Supported:                                                 ║
║     CRYPTO:  BTC, ETH, SOL, BNB                                             ║
║     INDICES: ES (S&P500), NQ (Nasdaq), YM (Dow), RTY (Russell)             ║
║     MACRO:   DXY, GOLD, OIL, TLT (bonds)                                   ║
║     FOREX:   EURUSD, GBPUSD, USDJPY, AUDUSD                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.colors import Normalize
import matplotlib.cm as cm
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import sys, os, warnings
warnings.filterwarnings("ignore")

sys.path.insert(0, "/home/claude")
from causal_transmission import (
    CausalTransmissionGraph, CausalEdge,
    GrangerCausality, TransferEntropy, CrossCorrelationMap,
)


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC MULTI-ASSET DATA WITH REALISTIC CAUSAL STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

def generate_causally_linked_universe(
    n_bars:   int = 400,
    universe: str = "macro",
    seed:     int = 42,
) -> Dict[str, np.ndarray]:
    """
    Generate synthetic price series with embedded causal structure
    reflecting known real-world market linkages.

    Causal structure injected:
      MACRO:  DXY → GOLD (inverse, lag 1-2)
              DXY → EURUSD (inverse, lag 1)
              GOLD → SPX (neg correlation in risk-off)
              TLT  → SPX (flight-to-quality)
      CRYPTO: BTC → ETH (lag 1-2, beta ~0.8)
              BTC → SOL (lag 1-3, beta ~1.2)
      INDICES:ES → NQ (same-day, high correlation)
              ES → YM (lag 0-1)
    """
    np.random.seed(seed)
    dates = pd.bdate_range(end=datetime.today(), periods=n_bars + 2)[:n_bars]

    if universe == "macro":
        assets = ["DXY", "GOLD", "SPX", "TLT", "EURUSD", "OIL"]
        base_prices = {
            "DXY":    103.5,
            "GOLD":  1950.0,
            "SPX":   4500.0,
            "TLT":     95.0,
            "EURUSD":   1.085,
            "OIL":     80.0,
        }
        vols = {"DXY": 0.003, "GOLD": 0.008, "SPX": 0.010,
                "TLT": 0.005, "EURUSD": 0.004, "OIL": 0.015}
    elif universe == "crypto":
        assets = ["BTC", "ETH", "SOL", "BNB"]
        base_prices = {"BTC": 42000, "ETH": 2500, "SOL": 95, "BNB": 310}
        vols = {"BTC": 0.025, "ETH": 0.030, "SOL": 0.040, "BNB": 0.022}
    elif universe == "indices":
        assets = ["ES", "NQ", "YM", "RTY"]
        base_prices = {"ES": 4500, "NQ": 15800, "YM": 35000, "RTY": 1900}
        vols = {"ES": 0.010, "NQ": 0.012, "YM": 0.010, "RTY": 0.013}
    else:
        raise ValueError(f"Unknown universe: {universe}")

    # Generate base (driver) returns with regime switching
    n_assets = len(assets)
    returns  = {a: np.zeros(n_bars) for a in assets}

    # Regime-switching drift
    regime   = 0
    reg_counter = 0
    drift    = {a: 0.0 for a in assets}

    # Idiosyncratic shocks
    idio = {a: np.random.randn(n_bars) * vols[a] for a in assets}

    # Systematic factor (common market)
    sys_factor = np.random.randn(n_bars) * 0.008

    for t in range(1, n_bars):
        reg_counter += 1
        if reg_counter > np.random.randint(30, 70):
            regime = np.random.randint(0, 3)
            reg_counter = 0
            for a in assets:
                drift[a] = np.random.choice([-1, 0, 1]) * vols[a] * 0.3

        for a in assets:
            returns[a][t] = drift[a] + idio[a][t]

        # Inject causal structure
        if universe == "macro":
            # DXY → GOLD (inverse, lag 1)
            if t >= 1:
                returns["GOLD"][t] += -0.6 * returns["DXY"][t-1] + sys_factor[t]
                returns["EURUSD"][t] += -0.75 * returns["DXY"][t-1]
                returns["SPX"][t]  += 0.3 * sys_factor[t] - 0.2 * returns["TLT"][t-1]
                returns["OIL"][t]  += -0.3 * returns["DXY"][t-1] + 0.4 * sys_factor[t]

        elif universe == "crypto":
            # BTC → ETH (lag 1, beta ~0.85)
            if t >= 1:
                returns["ETH"][t] += 0.85 * returns["BTC"][t-1]
                returns["SOL"][t] += 1.20 * returns["BTC"][t-1]
                returns["BNB"][t] += 0.65 * returns["BTC"][t-1]
            # ETH → SOL (lag 1, smaller)
            if t >= 2:
                returns["SOL"][t] += 0.40 * returns["ETH"][t-1]

        elif universe == "indices":
            # ES → NQ (same bar, high beta)
            returns["NQ"][t] += 1.15 * returns["ES"][t] + sys_factor[t] * 0.5
            returns["YM"][t] += 0.90 * returns["ES"][t] + sys_factor[t] * 0.4
            if t >= 1:
                returns["RTY"][t] += 0.80 * returns["ES"][t-1] + sys_factor[t] * 0.6

    # Build price series from returns
    prices = {}
    for a in assets:
        p = np.exp(np.cumsum(returns[a])) * base_prices[a]
        prices[a] = p

    return prices, dates


# ─────────────────────────────────────────────────────────────────────────────
# REVERSAL DETECTOR (simplified, standalone — no yfinance needed)
# ─────────────────────────────────────────────────────────────────────────────

def compute_reversal_probabilities(
    prices: Dict[str, np.ndarray],
    lookback: int = 60,
) -> Dict[str, float]:
    """
    Compute a reversal probability for each asset using IPDA-inspired signals:
      - 20/40/60d range position (premium/discount)
      - RSI(14)
      - ATR-normalized price momentum
      - 5-bar trend reversal signal
    Returns P(reversal) ∈ [0, 1] for the most recent bar.
    """
    results = {}
    for asset, price_arr in prices.items():
        if len(price_arr) < lookback:
            results[asset] = 0.3
            continue

        p = price_arr[-lookback:]
        close = p

        # IPDA range positions
        h20 = close[-20:].max(); l20 = close[-20:].min()
        h40 = close[-40:].max(); l40 = close[-40:].min()
        h60 = close.max();       l60 = close.min()
        cur = close[-1]

        def pos(h, l):
            r = h - l
            return (cur - l) / r if r > 1e-10 else 0.5

        pos20 = pos(h20, l20)
        pos40 = pos(h40, l40)
        pos60 = pos(h60, l60)

        # RSI(14)
        delta = np.diff(close)
        gain  = np.where(delta > 0, delta, 0)
        loss  = np.where(delta < 0, -delta, 0)
        avg_g = np.convolve(gain, np.ones(14)/14, mode='valid')[-1]
        avg_l = np.convolve(loss, np.ones(14)/14, mode='valid')[-1]
        rsi   = 100 - 100 / (1 + avg_g / (avg_l + 1e-12))

        # ATR
        tr  = np.abs(np.diff(close))
        atr = tr[-14:].mean() if len(tr) >= 14 else tr.mean()

        # Momentum (5-bar)
        mom5 = (close[-1] - close[-6]) / (close[-6] + 1e-10)

        # Score components
        # Premium zone (pos > 0.7) → bearish reversal likely
        # Discount zone (pos < 0.3) → bullish reversal likely
        range_score = max(abs(pos20 - 0.5), abs(pos40 - 0.5), abs(pos60 - 0.5)) * 2

        rsi_extreme = max(0, (rsi - 70) / 30) + max(0, (30 - rsi) / 30)

        # Momentum reversal: strong recent move → mean reversion pressure
        mom_score = min(abs(mom5) / (atr / (close[-1] + 1e-10) * 5 + 1e-10), 1.0)

        prob = 0.40 * range_score + 0.35 * rsi_extreme + 0.25 * mom_score
        results[asset] = float(np.clip(prob, 0.01, 0.99))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# CAUSAL AMPLIFICATION FUSION
# ─────────────────────────────────────────────────────────────────────────────

def fuse_causal_amplification(
    reversal_probs: Dict[str, float],
    graph: CausalTransmissionGraph,
    current_regime: str = "mid_vol",
    causal_weight: float = 0.40,
) -> Dict[str, dict]:
    """
    For each asset, amplify reversal probability based on causal predecessors.

    If asset X has high P(reversal) and X strongly Granger-causes asset Y,
    then Y's reversal probability is amplified:

    P_fused(Y) = (1 - w) * P_ipda(Y) + w * max_predecessor(P(X) * strength(X→Y))

    Returns enriched dict with base_prob, causal_prior, fused_prob, causal_source.
    """
    results = {}
    for target in graph.assets:
        base_p = reversal_probs.get(target, 0.3)

        # Collect all causal predecessors
        causal_priors = []
        for (source, tgt), edge in graph.edges.items():
            if tgt != target or not edge.is_significant:
                continue
            src_p = reversal_probs.get(source, 0.0)
            # Transmission: P(target reverses) += P(source reverses) × transmission_prob
            beta = edge.regime_betas.get(current_regime,
                   edge.regime_betas.get("mid_vol", 1.0))
            lag_discount = np.exp(-0.08 * edge.optimal_lag)
            causal_signal = src_p * edge.transmission_prob * lag_discount
            causal_priors.append({
                "source":     source,
                "signal":     float(causal_signal),
                "edge_strength": edge.composite_strength,
                "lag":        edge.optimal_lag,
                "trans_prob": edge.transmission_prob,
            })

        if causal_priors:
            # Take strongest causal prior
            best = max(causal_priors, key=lambda x: x["signal"])
            causal_prior = best["signal"]
            fused = (1 - causal_weight) * base_p + causal_weight * causal_prior
        else:
            best = None
            causal_prior = 0.0
            fused = base_p

        results[target] = {
            "base_prob":    round(base_p, 3),
            "causal_prior": round(causal_prior, 3),
            "fused_prob":   round(float(np.clip(fused, 0.01, 0.99)), 3),
            "causal_source": best["source"] if best else None,
            "causal_lag":    best["lag"]    if best else 0,
            "all_predecessors": sorted(causal_priors,
                                       key=lambda x: x["signal"], reverse=True),
        }

    return results


# ─────────────────────────────────────────────────────────────────────────────
# VISUALISATION
# ─────────────────────────────────────────────────────────────────────────────

def plot_full_analysis(
    prices:        Dict[str, np.ndarray],
    dates,
    graph:         CausalTransmissionGraph,
    reversal_probs: Dict[str, float],
    fused_results: Dict[str, dict],
    universe:      str = "macro",
) -> None:

    plt.style.use("dark_background")
    BG    = "#060C18"
    BG2   = "#0B1220"
    GOLD  = "#D4A847"
    CYAN  = "#00D4FF"
    RED   = "#FF4060"
    GREEN = "#00E676"
    PURPLE= "#B388FF"
    ORANGE= "#FF9800"
    GRID  = "#141E30"
    WHITE = "#C8D8E8"

    n_assets = len(graph.assets)
    fig = plt.figure(figsize=(24, 22), facecolor=BG)
    fig.suptitle(
        f"CROSS-ASSET CAUSAL TRANSMISSION ENGINE  ·  {universe.upper()} UNIVERSE",
        fontsize=15, color=GOLD, fontweight="bold",
        fontfamily="monospace", y=0.985,
    )

    gs = gridspec.GridSpec(
        4, 3, figure=fig,
        hspace=0.50, wspace=0.30,
        top=0.96, bottom=0.03,
        left=0.05, right=0.97,
    )

    def ax_style(ax, title):
        ax.set_facecolor(BG2)
        ax.set_title(title, color=GOLD, fontsize=9, fontfamily="monospace", pad=7)
        ax.tick_params(colors="#445566", labelsize=7.5)
        for sp in ax.spines.values():
            sp.set_edgecolor(GRID)
        ax.grid(True, color=GRID, linewidth=0.35, alpha=0.8)

    # ── Panel 1: Causal Graph Network (circular layout) ─────────────────────
    ax_net = fig.add_subplot(gs[0:2, 0:2])
    ax_net.set_facecolor(BG2)
    ax_net.set_title("CAUSAL TRANSMISSION GRAPH  ·  Node size = causal hub strength",
                     color=GOLD, fontsize=9.5, fontfamily="monospace", pad=8)
    for sp in ax_net.spines.values():
        sp.set_edgecolor(GRID)
    ax_net.set_xticks([]); ax_net.set_yticks([])

    assets = graph.assets
    na     = len(assets)
    # Circular layout
    angles = np.linspace(0, 2 * np.pi, na, endpoint=False)
    radius = 0.38
    cx, cy = 0.5, 0.5
    pos = {a: (cx + radius * np.cos(float(a_ang)), cy + radius * np.sin(float(a_ang)))
           for a, a_ang in zip(assets, angles)}

    A_mat, _ = graph.adjacency_matrix()
    hub_scores = dict(graph.hub_assets())

    # Draw edges
    for (source, target), edge in graph.edges.items():
        if not edge.is_significant:
            continue
        xs, ys = pos[source]
        xt, yt = pos[target]
        strength = edge.composite_strength
        alpha = 0.3 + 0.6 * strength
        width = 0.5 + 2.5 * strength
        color = CYAN if edge.peak_xcorr > 0 else ORANGE

        # Direction arrow
        dx = xt - xs
        dy = yt - ys
        # Offset to node border
        norm = np.sqrt(dx**2 + dy**2) + 1e-10
        offset = 0.04
        xs2 = xs + dx/norm * offset
        ys2 = ys + dy/norm * offset
        xt2 = xt - dx/norm * offset
        yt2 = yt - dy/norm * offset

        ax_net.annotate(
            "", xy=(xt2, yt2), xytext=(xs2, ys2),
            xycoords="axes fraction", textcoords="axes fraction",
            arrowprops=dict(
                arrowstyle=f"-|>, head_width={0.015 + 0.02*strength}, head_length=0.015",
                color=color, lw=width * 0.6, alpha=alpha,
                connectionstyle="arc3,rad=0.1",
            ),
        )

        # Label edge with lag
        mx = (xs + xt) / 2 + np.random.uniform(-0.02, 0.02)
        my = (ys + yt) / 2 + np.random.uniform(-0.02, 0.02)
        ax_net.text(mx, my, f"τ={edge.optimal_lag}",
                    transform=ax_net.transAxes,
                    color=color, fontsize=6.5, alpha=0.8,
                    fontfamily="monospace", ha="center")

    # Draw nodes
    for asset in assets:
        x, y = pos[asset]
        hub_s = hub_scores.get(asset, 0.0)
        fused = fused_results.get(asset, {})
        fused_p = fused.get("fused_prob", 0.3)

        # Node color based on reversal probability
        if fused_p >= 0.65:
            node_color = RED
        elif fused_p >= 0.45:
            node_color = ORANGE
        else:
            node_color = GREEN

        node_size = 0.025 + 0.040 * hub_s
        circle = plt.Circle((x, y), node_size, color=node_color,
                             alpha=0.25, transform=ax_net.transAxes,
                             zorder=4)
        ax_net.add_patch(circle)
        circle2 = plt.Circle((x, y), node_size, fill=False,
                              edgecolor=node_color, linewidth=1.8,
                              transform=ax_net.transAxes, zorder=5)
        ax_net.add_patch(circle2)
        ax_net.text(x, y + 0.002, asset,
                    transform=ax_net.transAxes,
                    color=WHITE, fontsize=10, fontweight="bold",
                    fontfamily="monospace", ha="center", va="center", zorder=6)
        ax_net.text(x, y - node_size - 0.022,
                    f"P={fused_p:.0%}",
                    transform=ax_net.transAxes,
                    color=node_color, fontsize=7.5, fontfamily="monospace",
                    ha="center", va="top", zorder=6)

    # Legend
    for label, color in [("Positive coupling (→)", CYAN),
                          ("Negative coupling (→)", ORANGE),
                          ("High P(reversal)", RED),
                          ("Med P(reversal)", ORANGE),
                          ("Low P(reversal)", GREEN)]:
        ax_net.plot([], [], color=color, linewidth=2, label=label)
    ax_net.legend(loc="lower right", fontsize=7, framealpha=0.2,
                  facecolor=BG, labelcolor=WHITE)

    # ── Panel 2: Reversal Probabilities — Base vs Causal-Fused ──────────────
    ax_prob = fig.add_subplot(gs[0, 2])
    ax_style(ax_prob, "Reversal P: Base vs Causal-Fused")
    x_pos  = np.arange(n_assets)
    base_v = [reversal_probs.get(a, 0.3) for a in assets]
    fuse_v = [fused_results.get(a, {}).get("fused_prob", 0.3) for a in assets]
    w = 0.35
    bars1 = ax_prob.bar(x_pos - w/2, base_v,  w, color=CYAN,   alpha=0.7, label="Base (IPDA)")
    bars2 = ax_prob.bar(x_pos + w/2, fuse_v,  w, color=PURPLE, alpha=0.7, label="Fused (Causal)")
    ax_prob.axhline(0.65, color=RED,    linestyle="--", linewidth=0.9, alpha=0.7)
    ax_prob.axhline(0.45, color=ORANGE, linestyle=":",  linewidth=0.8, alpha=0.6)
    ax_prob.set_xticks(x_pos); ax_prob.set_xticklabels(assets, fontsize=8)
    ax_prob.set_ylim(0, 1)
    ax_prob.legend(fontsize=7, framealpha=0.2, facecolor=BG)

    # ── Panel 3: Causal Hub Ranking ──────────────────────────────────────────
    ax_hub = fig.add_subplot(gs[1, 2])
    ax_style(ax_hub, "Causal Hub Strength (Out-degree)")
    hubs = graph.hub_assets()
    h_assets = [h[0] for h in hubs]
    h_scores = [h[1] for h in hubs]
    colors_h = [GOLD if s == max(h_scores) else CYAN for s in h_scores]
    ax_hub.barh(h_assets, h_scores, color=colors_h, alpha=0.8)
    for i, (a, s) in enumerate(zip(h_assets, h_scores)):
        ax_hub.text(s + 0.005, i, f"{s:.3f}", va="center",
                    color=WHITE, fontsize=7.5)
    ax_hub.set_xlabel("Composite Out-strength", color="#6688AA", fontsize=7.5)

    # ── Panel 4–6: Price + causal arrows for each asset pair ────────────────
    ax_prices = fig.add_subplot(gs[2, :])
    ax_style(ax_prices, "Normalised Price Series  ·  Vertical lines = IPDA 20/40/60d boundaries")
    colors_assets = [CYAN, GREEN, ORANGE, RED, PURPLE, GOLD,
                     "#FF6B9D", "#40C4FF"]
    recent = min(200, len(dates))
    for i, (asset, color) in enumerate(zip(assets, colors_assets)):
        p = prices[asset][-recent:]
        p_norm = (p - p.min()) / (p.max() - p.min() + 1e-10)
        label_str = asset
        fused = fused_results.get(asset, {})
        if fused.get("causal_source"):
            label_str += f" ← {fused['causal_source']} (τ={fused['causal_lag']})"
        ax_prices.plot(dates[-recent:], p_norm + i * 0.15,
                       color=color, linewidth=1.0, alpha=0.9, label=label_str)
        # IPDA boundaries
        for w in [20, 40, 60]:
            if len(p) >= w:
                ax_prices.axvline(dates[-w], color=color,
                                  linewidth=0.5, linestyle=":", alpha=0.3)
    ax_prices.legend(loc="lower left", fontsize=6.5, ncol=3,
                     framealpha=0.2, facecolor=BG)
    import matplotlib.dates as mdates
    ax_prices.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    # ── Panel 7: Transfer Entropy Matrix ────────────────────────────────────
    ax_te = fig.add_subplot(gs[3, 0])
    ax_style(ax_te, "Transfer Entropy Matrix  T(row → col)")
    na = len(assets)
    TE_mat = np.zeros((na, na))
    asset_idx = {a: i for i, a in enumerate(assets)}
    for (s, t), edge in graph.edges.items():
        TE_mat[asset_idx[s], asset_idx[t]] = edge.transfer_entropy
    im = ax_te.imshow(TE_mat, cmap="inferno", aspect="auto", vmin=0)
    ax_te.set_xticks(range(na)); ax_te.set_yticks(range(na))
    ax_te.set_xticklabels(assets, rotation=45, fontsize=7.5)
    ax_te.set_yticklabels(assets, fontsize=7.5)
    for i in range(na):
        for j in range(na):
            v = TE_mat[i, j]
            if v > 0.01:
                ax_te.text(j, i, f"{v:.3f}", ha="center", va="center",
                           fontsize=6.5, color="white" if v < TE_mat.max()*0.6 else "black")
    plt.colorbar(im, ax=ax_te, fraction=0.04, pad=0.02).ax.tick_params(labelsize=6)

    # ── Panel 8: Optimal Lag Matrix ──────────────────────────────────────────
    ax_lag = fig.add_subplot(gs[3, 1])
    ax_style(ax_lag, "Optimal Lead-Lag Matrix  (bars; row leads col)")
    lag_mat = np.full((na, na), np.nan)
    for (s, t), edge in graph.edges.items():
        if edge.is_significant:
            lag_mat[asset_idx[s], asset_idx[t]] = edge.optimal_lag
    masked = np.ma.masked_invalid(lag_mat)
    cmap = cm.plasma.copy(); cmap.set_bad(color=BG2)
    im2 = ax_lag.imshow(masked, cmap=cmap, aspect="auto", vmin=0, vmax=10)
    ax_lag.set_xticks(range(na)); ax_lag.set_yticks(range(na))
    ax_lag.set_xticklabels(assets, rotation=45, fontsize=7.5)
    ax_lag.set_yticklabels(assets, fontsize=7.5)
    for i in range(na):
        for j in range(na):
            if not np.isnan(lag_mat[i, j]):
                ax_lag.text(j, i, f"{int(lag_mat[i,j])}",
                            ha="center", va="center", fontsize=8,
                            color="white", fontweight="bold")
    plt.colorbar(im2, ax=ax_lag, fraction=0.04, pad=0.02).ax.tick_params(labelsize=6)

    # ── Panel 9: Propagation Signal Card ────────────────────────────────────
    ax_card = fig.add_subplot(gs[3, 2])
    ax_card.set_facecolor(BG2)
    for sp in ax_card.spines.values():
        sp.set_edgecolor(GOLD); sp.set_linewidth(1.2)
    ax_card.set_xticks([]); ax_card.set_yticks([])

    # Find highest-fused-probability asset as origin
    origin = max(fused_results, key=lambda x: fused_results[x]["fused_prob"])
    origin_dir = "DOWN" if fused_results[origin]["fused_prob"] > 0.5 else "UP"
    propagation = graph.propagate(origin, origin_dir)

    lines = [
        ("PROPAGATION SIGNAL", GOLD, 12),
        ("", None, 5),
        (f"Origin: {origin}  {('▼' if origin_dir=='DOWN' else '▲')} {origin_dir}", RED, 12),
        (f"P(reversal) = {fused_results[origin]['fused_prob']:.0%}", RED, 10),
        ("", None, 5),
        ("Downstream Targets:", WHITE, 9),
        ("", None, 3),
    ]
    for prop in propagation[:5]:
        sym  = "▼" if prop["direction"] == "DOWN" else "▲"
        prob_bar = "█" * int(prop["probability"] * 12)
        lines.append((f"  {prop['target']:8s} {sym} τ={prop['lag_bars']}d  "
                       f"P={prop['probability']:.0%}",
                       GREEN if prop["probability"] > 0.4 else ORANGE, 9))

    if not propagation:
        lines.append(("  No significant edges from origin", "#666", 9))

    y = 0.96
    for text, color, size in lines:
        if color is None:
            y -= 0.03; continue
        ax_card.text(0.05, y, text, transform=ax_card.transAxes,
                     color=color, fontsize=size, fontfamily="monospace",
                     va="top")
        y -= size * 0.013 + 0.018

    plt.savefig("/mnt/user-data/outputs/cross_asset_causal_analysis.png",
                dpi=150, bbox_inches="tight", facecolor=BG)
    print("  → Chart saved: cross_asset_causal_analysis.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN — run all three universes
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    for universe in ["macro", "crypto", "indices"]:
        print(f"\n{'═'*65}")
        print(f"  UNIVERSE: {universe.upper()}")
        print(f"{'═'*65}")

        prices, dates = generate_causally_linked_universe(
            n_bars=400, universe=universe, seed=42
        )

        # Build causal graph
        graph = CausalTransmissionGraph(max_lags=8, min_bars=50, verbose=True)
        graph.build({a: p for a, p in prices.items()})
        graph.print_report()

        # Per-asset IPDA reversal probabilities
        rev_probs = compute_reversal_probabilities(prices, lookback=60)
        print(f"\n  Per-asset IPDA reversal probabilities:")
        for asset, p in rev_probs.items():
            bar = "█" * int(p * 20)
            print(f"    {asset:10s}  {p:.1%}  |{bar:<20}|")

        # Causal amplification
        fused = fuse_causal_amplification(rev_probs, graph, current_regime="mid_vol")
        print(f"\n  Causal-fused reversal probabilities:")
        for asset, res in fused.items():
            delta = res["fused_prob"] - res["base_prob"]
            sign  = "+" if delta >= 0 else ""
            print(f"    {asset:10s}  base={res['base_prob']:.1%}  "
                  f"fused={res['fused_prob']:.1%}  "
                  f"Δ={sign}{delta:.1%}  "
                  f"{'← ' + res['causal_source'] if res['causal_source'] else ''}")

        # Strongest causal paths
        assets = graph.assets
        print(f"\n  Strongest causal paths:")
        for s in assets[:2]:
            for t in assets:
                if s == t: continue
                path = graph.strongest_path(s, t)
                if len(path) >= 2:
                    print(f"    {' → '.join(path)}")

        # Visualise (use last universe = indices for clean chart)
        if universe == "macro":
            print(f"\n  Generating full analysis chart...")
            plot_full_analysis(prices, dates, graph, rev_probs, fused, universe)

    print(f"\n{'═'*65}")
    print("  ALL UNIVERSES PROCESSED.")
    print(f"{'═'*65}\n")
