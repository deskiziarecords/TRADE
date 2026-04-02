import pandas as pd
import numpy as np
import plotly.graph_objects as go
import pandas_ta_openbb as ta
import yfinance as yf
from datetime import datetime, timedelta

# ================== CONFIG ==================
pair = "EURUSD=X"          # Change to GBPUSD=X, USDJPY=X, etc.
period = "6mo"             # 3mo, 6mo, 1y
interval = "15m"           # 5m, 15m, 30m, 1h

# ================== LOAD DATA ==================
print(f"Downloading {pair}...")
df = yf.download(pair, period=period, interval=interval, progress=False)
df = df.reset_index()

# Add necessary indicators
df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
df['RSI'] = ta.rsi(df['Close'], length=14)

# Simple FVG detection (Bullish & Bearish)
df['FVG_bull'] = (df['Low'] > df['High'].shift(2)) 
df['FVG_bear'] = (df['High'] < df['Low'].shift(2))

# ================== 3D FIGURE ==================
fig = go.Figure()

# 1. Main Price Path in 3D (X=Time, Y=Price, Z=ATR/Volatility)
fig.add_trace(go.Scatter3d(
    x=df.index,
    y=df['Close'],
    z=df['ATR'],
    mode='lines',
    line=dict(
        color=df['RSI'],
        colorscale='RdYlBu_r',
        width=5
    ),
    name='Price Path',
    hovertemplate='<b>Bar:</b> %{x}<br><b>Price:</b> %{y:.5f}<br><b>ATR:</b> %{z:.4f}<br><b>RSI:</b> %{customdata:.1f}',
    customdata=df['RSI']
))

# 2. Structural Boxes (20/40/60 day High/Low)
colors = {20: 'lime', 40: 'yellow', 60: 'red'}
for days in [20, 40, 60]:
    roll_high = df['High'].rolling(window=days*4).max()   # approx bars
    roll_low  = df['Low'].rolling(window=days*4).min()
    
    # Current structural levels
    curr_high = roll_high.iloc[-1]
    curr_low  = roll_low.iloc[-1]
    
    # Create 3D box (slightly transparent)
    fig.add_trace(go.Mesh3d(
        x=[df.index.min(), df.index.max(), df.index.max(), df.index.min()],
        y=[curr_high, curr_high, curr_low, curr_low],
        z=[0, df['ATR'].max()*1.2, df['ATR'].max()*1.2, 0],
        opacity=0.18,
        color=colors[days],
        name=f'{days}D Structure',
        hoverinfo='name'
    ))

# 3. Fair Value Gaps (FVG) as 3D Boxes
for i in range(2, len(df)):
    if df['FVG_bull'].iloc[i]:
        gap_top = df['High'].iloc[i-2]
        gap_bot = df['Low'].iloc[i]
        fig.add_trace(go.Mesh3d(
            x=[i-8, i+8, i+8, i-8],
            y=[gap_bot, gap_bot, gap_top, gap_top],
            z=[0, 4, 4, 0],
            opacity=0.45,
            color='purple',
            name='Bullish FVG',
            hovertemplate=f'Bullish FVG at bar {i}<br>Gap: {gap_bot:.5f} - {gap_top:.5f}'
        ))
    
    if df['FVG_bear'].iloc[i]:
        gap_top = df['High'].iloc[i]
        gap_bot = df['Low'].iloc[i-2]
        fig.add_trace(go.Mesh3d(
            x=[i-8, i+8, i+8, i-8],
            y=[gap_bot, gap_bot, gap_top, gap_top],
            z=[0, 4, 4, 0],
            opacity=0.45,
            color='magenta',
            name='Bearish FVG'
        ))

# 4. Killzone Planes (London & NY Open)
# Approximate session times (adjust if needed)
killzones = [
    {"name": "London Open", "color": "cyan", "start": 0.15},   # rough index position
    {"name": "NY Open",     "color": "orange", "start": 0.45}
]

for kz in killzones:
    x_pos = int(len(df) * kz["start"])
    fig.add_trace(go.Mesh3d(
        x=[x_pos, x_pos, x_pos, x_pos],
        y=[df['Close'].min()*0.995, df['Close'].max()*1.005, df['Close'].max()*1.005, df['Close'].min()*0.995],
        z=[0, 0, df['ATR'].max()*1.5, df['ATR'].max()*1.5],
        opacity=0.25,
        color=kz["color"],
        name=kz["name"],
        hoverinfo='name'
    ))

# ================== LAYOUT ==================
fig.update_layout(
    title=f"IPDA 3D Battlefield — {pair} (Phase 1)",
    scene=dict(
        xaxis_title="Time (Bar Index)",
        yaxis_title="Price",
        zaxis_title="Volatility (ATR)",
        camera=dict(eye=dict(x=1.8, y=1.8, z=1.3)),
        aspectmode='cube'
    ),
    template="plotly_dark",
    height=900,
    showlegend=True,
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
)

fig.show()
