import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pandas_ta as ta
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

# ================== CONFIG ==================
pair = "EURUSD=X"          # Change to your favorite pair
period = "6mo"
interval = "15m"

print(f"Building IPDA 3D Battlefield Phase 4 for {pair}...")

# ================== DATA & STATE VECTOR ==================
fx = yf.download(pair, period=period, interval=interval, progress=False).reset_index()
dxy = yf.download("DX-Y.NYB", period=period, interval=interval, progress=False)['Close'].reindex(fx['Datetime']).ffill()

fx['DXY'] = dxy.values
fx['ATR'] = ta.atr(fx['High'], fx['Low'], fx['Close'], length=14)
fx['RSI'] = ta.rsi(fx['Close'], length=14)
fx['Volume_MA'] = fx['Volume'].rolling(20).mean()
fx['Liq_Gradient'] = (fx['Volume'] / fx['Volume_MA']) * fx['ATR']
fx['Liq_Gradient'] = fx['Liq_Gradient'].fillna(fx['Liq_Gradient'].mean())

# Wick Sweeps
fx['Upper_Wick'] = fx['High'] - fx[['Open','Close']].max(axis=1)
fx['Lower_Wick'] = fx[['Open','Close']].min(axis=1) - fx['Low']
fx['Wick_Ratio'] = (fx['Upper_Wick'] + fx['Lower_Wick']) / fx['ATR'].replace(0, 1)
fx['Is_Sweep'] = fx['Wick_Ratio'] > 2.3

# FVG
fx['FVG_bull'] = (fx['Low'] > fx['High'].shift(2))
fx['FVG_bear'] = (fx['High'] < fx['Low'].shift(2))

# OBNFE Severity Score (Bayesian-inspired fusion)
fx['Severity'] = (
    0.35 * ((fx['RSI'] > 72) | (fx['RSI'] < 28)).astype(float) +
    0.30 * (fx['Wick_Ratio'] > 3.0).astype(float) +
    0.20 * (abs(fx['Close'].pct_change(8)) > 0.009).astype(float) +
    0.15 * (fx['Liq_Gradient'] > fx['Liq_Gradient'].rolling(30).quantile(0.85)).astype(float)
)
fx['Severity'] = fx['Severity'].rolling(10).mean().fillna(0.25).clip(0, 1)

# Kernel Panic Trigger
fx['Kernel_Panic'] = fx['Severity'] > 0.78

# ================== 3D BATTLEFIELD ==================
fig = go.Figure()

# 1. Main Price Path — colored by Severity (OBNFE)
colorscale = [[0, '#00ff00'], [0.5, '#ffff00'], [0.78, '#ff8800'], [1, '#ff0000']]
fig.add_trace(go.Scatter3d(
    x=fx.index,
    y=fx['Close'],
    z=fx['ATR'],
    mode='lines',
    line=dict(color=fx['Severity'], colorscale=colorscale, width=8),
    name='Price Path (OBNFE Severity)',
    hovertemplate='Bar: %{x}<br>Price: %{y:.5f}<br>Severity: %{customdata:.3f}<extra></extra>',
    customdata=fx['Severity']
))

# 2. Liquidity Potential Field (Surface)
x_grid = np.linspace(fx.index.min(), fx.index.max(), 45)
y_grid = np.linspace(fx['Close'].min()*0.994, fx['Close'].max()*1.006, 28)
X, Y = np.meshgrid(x_grid, y_grid)
Z = np.interp(x_grid, fx.index, fx['Liq_Gradient'].rolling(15).mean().fillna(0)) * 1.3
Z = Z[None, :] * np.ones_like(Y)

fig.add_trace(go.Surface(
    x=X, y=Y, z=Z,
    opacity=0.32,
    colorscale='Plasma',
    name='Liquidity Potential Field',
    showscale=False
))

# 3. Wick Sweeps (Liquidity Harvesting)
for i in fx[fx['Is_Sweep']].index:
    color = 'red' if fx['Upper_Wick'].iloc[i] > 0 else 'cyan'
    fig.add_trace(go.Scatter3d(
        x=[i, i],
        y=[fx['Close'].iloc[i], fx['Close'].iloc[i]],
        z=[0, fx['ATR'].iloc[i] * 5],
        mode='lines',
        line=dict(color=color, width=6),
        name='Liquidity Sweep'
    ))

# 4. Structural Magnets + Force Arrows
for days, col in zip([20, 40, 60], ['#00ff88', '#ffdd00', '#ff4444']):
    high_lvl = fx['High'].rolling(days*4).max().iloc[-1]
    low_lvl  = fx['Low'].rolling(days*4).min().iloc[-1]
    
    # Magnets
    fig.add_trace(go.Scatter3d(
        x=[len(fx)-12], y=[high_lvl], z=[fx['ATR'].max()*1.2],
        mode='markers+text',
        marker=dict(size=16, color=col, symbol='diamond'),
        text=[f'{days}D High'],
        name=f'{days}D High Magnet'
    ))
    fig.add_trace(go.Scatter3d(
        x=[len(fx)-12], y=[low_lvl], z=[fx['ATR'].max()*1.2],
        mode='markers+text',
        marker=dict(size=16, color=col, symbol='diamond'),
        text=[f'{days}D Low'],
        name=f'{days}D Low Magnet'
    ))
    
    # Force Arrows
    fig.add_trace(go.Cone(
        x=[len(fx)-35], y=[high_lvl], z=[fx['ATR'].max()*0.9],
        u=[0], v=[0], w=[-2],
        sizemode="absolute", sizeref=3, anchor="tail",
        colorscale=[[0, col]], showscale=False
    ))

# 5. FVG Boxes
for i in range(2, len(fx)):
    if fx['FVG_bull'].iloc[i]:
        fig.add_trace(go.Mesh3d(
            x=[i-7, i+7, i+7, i-7],
            y=[fx['Low'].iloc[i], fx['Low'].iloc[i], fx['High'].iloc[i-2], fx['High'].iloc[i-2]],
            z=[0, 6, 6, 0],
            opacity=0.55,
            color='purple',
            name='Bullish FVG'
        ))
    if fx['FVG_bear'].iloc[i]:
        fig.add_trace(go.Mesh3d(
            x=[i-7, i+7, i+7, i-7],
            y=[fx['Low'].iloc[i-2], fx['Low'].iloc[i-2], fx['High'].iloc[i], fx['High'].iloc[i]],
            z=[0, 6, 6, 0],
            opacity=0.55,
            color='magenta',
            name='Bearish FVG'
        ))

# 6. Killzone Planes
for name, color, pos_ratio in [("London Open", "cyan", 0.27), ("NY Open", "orange", 0.57)]:
    pos = int(len(fx) * pos_ratio)
    fig.add_trace(go.Mesh3d(
        x=[pos]*4,
        y=[fx['Close'].min()*0.994, fx['Close'].max()*1.006]*2,
        z=[0, 0, fx['ATR'].max()*2.2, fx['ATR'].max()*2.2],
        opacity=0.25,
        color=color,
        name=name
    ))

# 7. Kernel Panic Overlay (when Severity > 0.78)
panic_bars = fx[fx['Kernel_Panic']].index
if len(panic_bars) > 0:
    for bar in panic_bars:
        fig.add_trace(go.Scatter3d(
            x=[bar, bar],
            y=[fx['Close'].iloc[bar]-0.003, fx['Close'].iloc[bar]+0.003],
            z=[0, fx['ATR'].max()*3],
            mode='lines',
            line=dict(color='white', width=8, dash='dash'),
            name='KERNEL PANIC'
        ))

# ================== LAYOUT ==================
fig.update_layout(
    title=f"IPDA 3D Computational Battlefield Phase 4 — {pair} | OBNFE Active",
    scene=dict(
        xaxis_title="Time (Bar Index)",
        yaxis_title="Price",
        zaxis_title="Volatility + Liquidity Gradient",
        camera=dict(eye=dict(x=2.4, y=1.8, z=1.6)),
        aspectmode='manual',
        aspectratio=dict(x=2.3, y=1, z=0.9)
    ),
    template="plotly_dark",
    height=1000,
    showlegend=True,
    legend=dict(x=0.01, y=0.98, bgcolor="rgba(0,0,0,0.75)")
)

fig.show()

print("\nIPDA 3D Battlefield Phase 4 loaded.")
print("• Red path = High systemic stress (OBNFE Severity)")
print("• White dashed spikes = KERNEL PANIC zones")
print("• Purple/Magenta boxes = Fair Value Gaps")
print("• Surface = Liquidity Potential Field")
