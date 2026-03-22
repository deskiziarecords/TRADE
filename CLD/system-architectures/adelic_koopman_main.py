"""
╔══════════════════════════════════════════════════════════════════════════════╗
║    ADELIC-KOOPMAN IPDA — MAIN RUNNER & DEMO                                 ║
║    Generates synthetic EURUSD data and runs full Sentinel pipeline          ║
╚══════════════════════════════════════════════════════════════════════════════╝

PRODUCTION USAGE (with real data):
    import yfinance as yf
    df = yf.download("EURUSD=X", start="2020-01-01", interval="1d", auto_adjust=True)
    df.columns = [c.lower() for c in df.columns]

BACKTEST USAGE:
    python adelic_koopman_main.py --mode backtest --pair EURUSD --start 2020-01-01

LIVE SCAN:
    python adelic_koopman_main.py --mode live --pair EURUSD
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyArrowPatch
import matplotlib.dates as mdates
from datetime import datetime, timedelta

sys.path.insert(0, "/home/claude")
from adelic_koopman_core import (
    AdelicPriceGeometry, KoopmanOperator,
    MandraPrimitives, DeliverySignatureMemory,
)
from sos27x_sentinel import SOS27XSentinel, SentinelSignal, SignalDirection, MarketRegime


# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC DATA GENERATOR (realistic EURUSD simulation)
# ─────────────────────────────────────────────────────────────────────────────

def generate_synthetic_forex(
    n_bars: int = 500,
    pair: str = "EURUSD",
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic forex OHLCV with realistic properties:
      - Mean-reversion + trend regimes
      - Clustered volatility (GARCH-like)
      - IPDA-style liquidity sweeps
      - Intrabar high/low dynamics
    """
    np.random.seed(seed)
    dates = pd.bdate_range(end=datetime.today(), periods=n_bars + 2)[:n_bars]

    # Base price around EURUSD fair value
    base_price = 1.08500

    # Regime-switching drift
    prices = [base_price]
    volatility = 0.0035
    vol_series = [volatility]
    regime_counter = 0
    current_drift = 0.0001

    for i in range(1, n_bars):
        # Regime switch every 40–80 bars
        regime_counter += 1
        if regime_counter > np.random.randint(40, 80):
            current_drift = np.random.choice([-0.0003, 0.0, 0.0003, 0.0005, -0.0005])
            regime_counter = 0

        # GARCH-like volatility
        shock = np.random.randn()
        volatility = 0.7 * volatility + 0.3 * 0.0035 + 0.05 * abs(shock) * 0.0035
        volatility = np.clip(volatility, 0.0010, 0.0090)
        vol_series.append(volatility)

        # Price step
        ret    = current_drift + volatility * shock
        # Mean reversion toward base
        mean_rev = -0.02 * (prices[-1] - base_price)
        prices.append(prices[-1] * (1 + ret + mean_rev))

    prices = np.array(prices)
    vol_arr = np.array(vol_series)

    # Generate OHLCV from close prices
    highs  = prices * (1 + vol_arr * np.abs(np.random.randn(n_bars)) * 0.6)
    lows   = prices * (1 - vol_arr * np.abs(np.random.randn(n_bars)) * 0.6)
    opens  = np.roll(prices, 1); opens[0] = prices[0]

    # Inject IPDA-style liquidity sweeps at 20/40/60-day boundaries
    for i in range(60, n_bars):
        for w in [20, 40, 60]:
            if i % w == 0:
                sweep_dir = np.random.choice([-1, 1])
                highs[i] += sweep_dir * vol_arr[i] * 2.5 * (sweep_dir > 0)
                lows[i]  -= sweep_dir * vol_arr[i] * 2.5 * (sweep_dir < 0)

    volumes = np.random.lognormal(13, 0.5, n_bars).astype(int)

    df = pd.DataFrame({
        "open":   opens,
        "high":   np.maximum(highs, np.maximum(opens, prices)),
        "low":    np.minimum(lows,  np.minimum(opens, prices)),
        "close":  prices,
        "volume": volumes,
    }, index=dates)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# BACKTEST ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest(df: pd.DataFrame, pair: str = "EURUSD",
                 warmup: int = 80) -> pd.DataFrame:
    """
    Walk-forward backtest of SOS-27-X Sentinel.
    Processes each bar from `warmup` onward, collecting signals.
    """
    print(f"\n{'═'*65}")
    print(f"  ADELIC-KOOPMAN IPDA — WALK-FORWARD BACKTEST")
    print(f"  Pair: {pair}  |  Bars: {len(df)}  |  Warmup: {warmup}")
    print(f"{'═'*65}\n")

    sentinel = SOS27XSentinel(pair=pair, verbose=False)
    records  = []

    for i in range(warmup, len(df)):
        df_slice = df.iloc[:i+1]
        try:
            signal = sentinel.process(df_slice)
        except Exception as e:
            continue

        # Compute realized outcome (next 5-bar return)
        if i + 5 < len(df):
            fwd_ret = (df["close"].iloc[i+5] - df["close"].iloc[i]) / df["close"].iloc[i]
        else:
            fwd_ret = np.nan

        records.append({
            "date":          df.index[i],
            "close":         df["close"].iloc[i],
            "direction":     signal.direction.value,
            "reversal_prob": signal.reversal_prob,
            "confidence":    signal.confidence,
            "regime":        signal.regime.value,
            "adelic_score":  signal.adelic_score,
            "koopman_score": signal.koopman_score,
            "sweep_score":   signal.raw_state.sweep_score if signal.raw_state else 0.0,
            "instability":   signal.raw_state.koopman_instability if signal.raw_state else 0.0,
            "ipda_20d_pos":  (df["close"].iloc[i] - signal.raw_state.ipda_20d_low) /
                              max(signal.raw_state.ipda_20d_high - signal.raw_state.ipda_20d_low, 1e-10)
                              if signal.raw_state else 0.5,
            "n_breakers":    len(signal.raw_state.breakers_active) if signal.raw_state else 0,
            "fwd_5bar_ret":  fwd_ret,
        })

        if i % 50 == 0:
            print(f"  Bar {i}/{len(df)-1} | P(rev)={signal.reversal_prob:.2f} | "
                  f"Signal={signal.direction.value} | Regime={signal.regime.value}")

    results = pd.DataFrame(records)

    # Signal P&L attribution
    results["signal_ret"] = np.where(
        results["direction"] == "LONG",  results["fwd_5bar_ret"],
        np.where(results["direction"] == "SHORT", -results["fwd_5bar_ret"], 0.0)
    )
    results["cum_ret"] = results["signal_ret"].cumsum()

    print(f"\n{'─'*65}")
    print(f"  BACKTEST SUMMARY")
    print(f"{'─'*65}")
    print(f"  Total bars processed:   {len(results)}")
    active = results[results["direction"] != "NEUTRAL"]
    print(f"  Active signals:         {len(active)} ({len(active)/len(results)*100:.1f}%)")
    print(f"  HALT signals:           {(results['direction']=='HALT').sum()}")
    high_prob = results[results["reversal_prob"] >= 0.65]
    print(f"  High-prob signals (≥65%):{len(high_prob)}")
    if len(active) > 0 and not active["signal_ret"].isna().all():
        valid = active.dropna(subset=["signal_ret"])
        if len(valid) > 0:
            win_rate = (valid["signal_ret"] > 0).mean()
            avg_ret  = valid["signal_ret"].mean()
            print(f"  Win rate (active):      {win_rate*100:.1f}%")
            print(f"  Avg signal return:      {avg_ret*100:.3f}%")
    print(f"{'─'*65}\n")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# VISUALISATION
# ─────────────────────────────────────────────────────────────────────────────

def plot_system_analysis(df: pd.DataFrame,
                          results: pd.DataFrame,
                          signal_live: SentinelSignal,
                          pair: str = "EURUSD") -> None:

    # Dark institutional theme
    plt.style.use("dark_background")
    GOLD     = "#C9A84C"
    CYAN     = "#00E5FF"
    RED      = "#FF3D71"
    GREEN    = "#00E676"
    PURPLE   = "#CE93D8"
    ORANGE   = "#FF9800"
    BG       = "#0A0E1A"
    BG2      = "#0F1626"
    GRID_CLR = "#1A2640"

    fig = plt.figure(figsize=(22, 20), facecolor=BG)
    fig.suptitle(
        f"ADELIC-KOOPMAN IPDA  ·  SOS-27-X SENTINEL  ·  {pair}",
        fontsize=14, color=GOLD, fontweight="bold",
        fontfamily="monospace", y=0.98,
    )
    gs = gridspec.GridSpec(
        5, 3,
        figure=fig,
        hspace=0.45, wspace=0.35,
        top=0.95, bottom=0.04,
        left=0.06, right=0.97,
    )

    def style_ax(ax, title, ylabel=""):
        ax.set_facecolor(BG2)
        ax.set_title(title, color=GOLD, fontsize=8.5,
                     fontfamily="monospace", pad=6)
        ax.set_ylabel(ylabel, color="#6688AA", fontsize=7.5)
        ax.tick_params(colors="#445566", labelsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_CLR)
        ax.grid(True, color=GRID_CLR, linewidth=0.4, alpha=0.7)

    recent  = df.tail(200)
    r_slice = results.tail(200).copy()
    r_slice = r_slice[r_slice["date"] >= recent.index[0]]

    # ── Panel 1 (spans 2 cols): Price + IPDA Ranges ──────────────────────────
    ax1 = fig.add_subplot(gs[0, :2])
    style_ax(ax1, f"{pair}  |  IPDA 20/40/60d Ranges + Signals", "Price")
    ax1.plot(recent.index, recent["close"],
             color=CYAN, linewidth=1.1, zorder=5, label="Close")

    # IPDA range bands
    if len(r_slice) > 0:
        adelic_obj = AdelicPriceGeometry()
        colors_w = {20: GREEN, 40: ORANGE, 60: RED}
        for w in [20, 40, 60]:
            rh = recent["high"].rolling(w, min_periods=1).max()
            rl = recent["low"].rolling(w, min_periods=1).min()
            ax1.plot(recent.index, rh, "--", color=colors_w[w],
                     linewidth=0.7, alpha=0.8, label=f"{w}d H")
            ax1.plot(recent.index, rl, ":",  color=colors_w[w],
                     linewidth=0.7, alpha=0.8, label=f"{w}d L")
            ax1.fill_between(recent.index, rl, rh,
                             alpha=0.03, color=colors_w[w])

        # Signal overlays
        for _, row in r_slice.iterrows():
            if row["direction"] == "LONG" and row["reversal_prob"] >= 0.55:
                ax1.scatter(row["date"], row["close"] * 0.9997,
                            marker="^", color=GREEN, s=35, zorder=8, alpha=0.85)
            elif row["direction"] == "SHORT" and row["reversal_prob"] >= 0.55:
                ax1.scatter(row["date"], row["close"] * 1.0003,
                            marker="v", color=RED, s=35, zorder=8, alpha=0.85)

    ax1.legend(loc="upper left", fontsize=6.5, ncol=5,
               framealpha=0.2, facecolor=BG)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    # ── Panel 2 (spans 2 cols): Reversal Probability ─────────────────────────
    ax2 = fig.add_subplot(gs[1, :2])
    style_ax(ax2, "Reversal Probability  [Bayesian Fusion: Adelic + Koopman + Memory]",
             "P(Reversal)")
    if len(r_slice) > 0:
        ax2.fill_between(r_slice["date"], r_slice["reversal_prob"],
                         alpha=0.5, color=PURPLE)
        ax2.plot(r_slice["date"], r_slice["reversal_prob"],
                 color=PURPLE, linewidth=1.0)
    ax2.axhline(0.65, color=RED,   linestyle="--", linewidth=0.9,
                alpha=0.8, label="Signal threshold (0.65)")
    ax2.axhline(0.45, color=ORANGE, linestyle=":", linewidth=0.8,
                alpha=0.6, label="Caution zone (0.45)")
    ax2.set_ylim(0, 1)
    ax2.legend(fontsize=7, framealpha=0.2, facecolor=BG)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

    # ── Panel 3: Live Signal Card ─────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[0:2, 2])
    ax3.set_facecolor(BG2)
    for spine in ax3.spines.values():
        spine.set_edgecolor(GOLD)
        spine.set_linewidth(1.2)
    ax3.set_xticks([]); ax3.set_yticks([])

    dir_color = (GREEN if signal_live.direction == SignalDirection.LONG else
                 RED   if signal_live.direction == SignalDirection.SHORT else
                 ORANGE if signal_live.direction == SignalDirection.HALT else "#888")
    dir_sym   = ("▲ LONG" if signal_live.direction == SignalDirection.LONG else
                 "▼ SHORT" if signal_live.direction == SignalDirection.SHORT else
                 "⊘ HALT" if signal_live.direction == SignalDirection.HALT else "— NEUTRAL")

    lines = [
        ("SOS-27-X  LIVE SIGNAL", GOLD, 13),
        ("", None, 9),
        (f"{dir_sym}", dir_color, 18),
        ("", None, 6),
        (f"P(Reversal)   {signal_live.reversal_prob*100:.1f}%", CYAN, 11),
        (f"Confidence    {signal_live.confidence*100:.1f}%", CYAN, 11),
        (f"Regime        {signal_live.regime.value.upper()}", PURPLE, 11),
        ("", None, 6),
        (f"Adelic Score  {signal_live.adelic_score:.3f}", GREEN, 10),
        (f"Koopman Score {signal_live.koopman_score:.3f}", GREEN, 10),
        (f"Memory Score  {signal_live.memory_score:.3f}", GREEN, 10),
    ]
    if signal_live.raw_state:
        s = signal_live.raw_state
        lines += [
            ("", None, 6),
            (f"Sweep Score   {s.sweep_score:.3f}", ORANGE, 10),
            (f"Instability   {s.koopman_instability:.3f}", ORANGE, 10),
            (f"Lyapunov Exp  {s.lyapunov_exponent:.4f}", ORANGE, 10),
        ]
        if s.breakers_active:
            lines.append(("", None, 6))
            lines.append(("⚠  CIRCUIT BREAKERS:", RED, 10))
            for b in s.breakers_active:
                lines.append((f"   {b}", RED, 9))

    y_pos = 0.96
    for text, color, size in lines:
        if color is None:
            y_pos -= 0.02
            continue
        ax3.text(0.05, y_pos, text, transform=ax3.transAxes,
                 color=color, fontsize=size, fontfamily="monospace",
                 verticalalignment="top")
        y_pos -= (size * 0.013 + 0.015)

    # ── Panel 4: Adelic Score ─────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[2, 0])
    style_ax(ax4, "Adelic Confluence Score", "Score")
    if len(r_slice) > 0:
        ax4.fill_between(r_slice["date"], r_slice["adelic_score"],
                         alpha=0.6, color=GREEN)
        ax4.plot(r_slice["date"], r_slice["adelic_score"],
                 color=GREEN, linewidth=0.9)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    # ── Panel 5: Koopman Spectral Score ──────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 1])
    style_ax(ax5, "Koopman Spectral Score", "Score")
    if len(r_slice) > 0:
        ax5.fill_between(r_slice["date"], r_slice["koopman_score"],
                         alpha=0.6, color=CYAN)
        ax5.plot(r_slice["date"], r_slice["koopman_score"],
                 color=CYAN, linewidth=0.9)
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    # ── Panel 6: Sweep Score ──────────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[2, 2])
    style_ax(ax6, "Mandra Sweep Detector", "Score")
    if len(r_slice) > 0 and "sweep_score" in r_slice.columns:
        ax6.fill_between(r_slice["date"], r_slice["sweep_score"],
                         alpha=0.5, color=RED)
        ax6.plot(r_slice["date"], r_slice["sweep_score"],
                 color=RED, linewidth=0.9)
    ax6.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    # ── Panel 7: Koopman Instability ─────────────────────────────────────────
    ax7 = fig.add_subplot(gs[3, 0])
    style_ax(ax7, "Koopman Instability Index", "Index")
    if len(r_slice) > 0:
        ax7.plot(r_slice["date"], r_slice["instability"],
                 color=ORANGE, linewidth=1.0)
        ax7.axhline(0.4, color=RED, linestyle="--", linewidth=0.8, alpha=0.7,
                    label="Trip threshold (0.4)")
        ax7.legend(fontsize=6.5, framealpha=0.2, facecolor=BG)
    ax7.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    # ── Panel 8: Regime Distribution ─────────────────────────────────────────
    ax8 = fig.add_subplot(gs[3, 1])
    style_ax(ax8, "SOS-27 Regime Distribution", "")
    if len(r_slice) > 0:
        regime_counts = r_slice["regime"].value_counts()
        regime_colors = {
            "expansion":    GREEN,
            "reversal":     RED,
            "retracement":  ORANGE,
            "consolidation":CYAN,
            "accumulation": PURPLE,
            "distribution": GOLD,
            "unknown":      "#555",
        }
        colors = [regime_colors.get(r, "#888") for r in regime_counts.index]
        bars = ax8.barh(regime_counts.index, regime_counts.values, color=colors, alpha=0.8)
        ax8.tick_params(axis="y", labelsize=7.5)
        for bar, val in zip(bars, regime_counts.values):
            ax8.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                     str(val), va="center", color="#AAB", fontsize=7)

    # ── Panel 9: Cumulative P&L ───────────────────────────────────────────────
    ax9 = fig.add_subplot(gs[3, 2])
    style_ax(ax9, "Signal Attribution (Cumulative Ret)", "Cum Return")
    if len(r_slice) > 0 and "cum_ret" in results.columns:
        cum_col = results.set_index("date")["cum_ret"].reindex(r_slice["date"])
        color = GREEN if cum_col.iloc[-1] >= 0 else RED
        ax9.plot(r_slice["date"], cum_col.values, color=color, linewidth=1.1)
        ax9.axhline(0, color="#445566", linewidth=0.7)
        ax9.fill_between(r_slice["date"], cum_col.values, 0,
                         alpha=0.3, color=color)
    ax9.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    # ── Panel 10 (bottom row): Architecture diagram ───────────────────────────
    ax10 = fig.add_subplot(gs[4, :])
    ax10.set_facecolor(BG2)
    for spine in ax10.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax10.set_xticks([]); ax10.set_yticks([])
    ax10.set_xlim(0, 100); ax10.set_ylim(0, 10)

    nodes = [
        (5,  5, "OHLCV\nIngest",       CYAN),
        (19, 5, "Adelic\nTube",        GREEN),
        (33, 5, "Koopman\nOperator",   PURPLE),
        (47, 5, "Mandra\nPrimitive",   ORANGE),
        (61, 5, "ChromaDB\nMemory",    GOLD),
        (75, 5, "SOS-27\nState",       RED),
        (89, 5, "Signal\nEmitter",     CYAN),
    ]
    for x, y, label, color in nodes:
        circle = plt.Circle((x, y), 3.5, color=color, alpha=0.15, zorder=2)
        ax10.add_patch(circle)
        circle2 = plt.Circle((x, y), 3.5, fill=False,
                              edgecolor=color, linewidth=1.2, zorder=3)
        ax10.add_patch(circle2)
        ax10.text(x, y, label, ha="center", va="center",
                  color=color, fontsize=7.5, fontfamily="monospace",
                  fontweight="bold", zorder=4)

    for i in range(len(nodes) - 1):
        x1, _, _, c1 = nodes[i]
        x2, _, _, c2 = nodes[i+1]
        ax10.annotate("", xy=(x2-3.6, 5), xytext=(x1+3.6, 5),
                      arrowprops=dict(arrowstyle="->", color=GOLD,
                                      lw=1.2, alpha=0.7))

    ax10.text(50, 0.8, "PRODUCTION PIPELINE  ·  SOS-27-X SENTINEL",
              ha="center", color=GOLD, fontsize=8, fontfamily="monospace", alpha=0.6)

    plt.savefig("/mnt/user-data/outputs/adelic_koopman_analysis.png",
                dpi=150, bbox_inches="tight", facecolor=BG)
    print("  → Chart saved: adelic_koopman_analysis.png")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PAIR = "EURUSD"

    print("  Generating synthetic EURUSD data (500 bars)...")
    df = generate_synthetic_forex(n_bars=500, pair=PAIR)
    print(f"  Generated: {len(df)} bars from {df.index[0].date()} to {df.index[-1].date()}\n")

    # Walk-forward backtest
    results = run_backtest(df, pair=PAIR, warmup=80)

    # Live signal on full dataset
    print("  Running live signal on latest data...")
    sentinel_live = SOS27XSentinel(pair=PAIR, verbose=True)
    signal_live   = sentinel_live.process(df)
    sentinel_live.print_signal(signal_live)

    # Generate plots
    print("  Generating analysis charts...")
    plot_system_analysis(df, results, signal_live, pair=PAIR)

    # Export results to CSV
    results.to_csv("/mnt/user-data/outputs/adelic_koopman_backtest.csv", index=False)
    print("  → Results saved: adelic_koopman_backtest.csv")

    print("\n  ALL OUTPUTS GENERATED SUCCESSFULLY.")
    print(f"{'═'*65}")
