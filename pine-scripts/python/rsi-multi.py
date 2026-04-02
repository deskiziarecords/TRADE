# @version=6
# indicator("RSI Multi-View: Candles, HA & Line", shorttitle="RSI Multi", overlay=false)

# 1. --- Inputs & Enums ---
# enum ChartType
#     candles = "Standard RSI Candles"
#     ha      = "Heikin Ashi RSI"
#     line    = "Standard RSI Line"

chartMode = input.enum(ChartType.candles, "Display Mode", group="Visuals")
rsiLen    = input.int(14, "RSI Length", minval=1, group="Settings")
upColor   = input.color(color.teal, "Bullish Color", group="Colors")
downColor = input.color(color.maroon, "Bearish Color", group="Colors")

# 2. --- RSI OHLC Calculations ---
# We calculate RSI for each component of a price bar
rO = ta.rsi(open, rsiLen)
rH = ta.rsi(high, rsiLen)
rL = ta.rsi(low, rsiLen)
rC = ta.rsi(close, rsiLen)

# 3. --- Heikin Ashi RSI Calculations ---
haO = None
haC = (rO + rH + rL + rC) / 4
# HA Open = (Previous HA Open + Previous HA Close) / 2
haO = (haO + haC) / 2 if haO is not None else (rO + rC) / 2
haH = max(rH, haO, haC)
haL = min(rL, haO, haC)

# 4. --- Selection Logic ---
isLine = chartMode == ChartType.line
isHA   = chartMode == ChartType.ha

# Use HA values if selected, otherwise Standard RSI Candle values
plotO = haO if isHA else rO
plotH = haH if isHA else rH
plotL = haL if isHA else rL
plotC = haC if isHA else rC

# Determine Candle Color
barColor = upColor if plotC >= plotO else downColor

# 5. --- Plotting ---
# plotcandle() returns 'na' if isLine is true, hiding the candles
plotcandle(None if isLine else plotO, plotH, plotL, plotC, "RSI Candles", color=barColor, wickcolor=barColor, bordercolor=barColor)

# Plot a standard line if Line mode is selected
plot(rC if isLine else None, "RSI Line", color=color.gray, linewidth=2)

# Reference Levels update
hline(70, "Overbought", color=color.new(color.red, 60), linestyle=hline.style_dashed)
hline(50, "Mean", color=color.new(color.gray, 60), linestyle=hline.style_dotted)
hline(30, "Oversold", color=color.new(color.green, 60), linestyle=hline.style_dashed)
