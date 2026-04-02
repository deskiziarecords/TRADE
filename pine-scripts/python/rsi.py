# @version=6
# indicator("RSI Reversal PRO+ │ Soon_Dubu", overlay = true)

# ═══════════════════════════════════════════════════════════
#  ① RSI CORE
# ═══════════════════════════════════════════════════════════
rsiLen       = 14  # input.int(14, "RSI Length", minval = 2)
overbought   = 70  # input.int(70, "Overbought", minval = 51)
oversold     = 30  # input.int(30, "Oversold", maxval = 49)
cooldownBars = 8   # input.int(8,  "Cooldown Bars", minval = 1)

# ═══════════════════════════════════════════════════════════
#  ② FILTERS
# ═══════════════════════════════════════════════════════════
useVol    = True  # input.bool(true,  "Volume Filter")
volLen    = 20    # input.int(20,     "Volume SMA")
volMult   = 1.2   # input.float(1.2,  "Volume ×", step = 0.1)

useCandle = True  # input.bool(true,  "Candle Direction")

useDepth  = True  # input.bool(true,  "RSI Zone Depth")
depthBars = 2     # input.int(2,      "Min Bars in Zone", minval = 1, maxval = 10)

useATR    = True  # input.bool(true,  "ATR Volatility")
atrLen    = 14    # input.int(14,     "ATR Length")

# ═══════════════════════════════════════════════════════════
#  RSI
# ═══════════════════════════════════════════════════════════
rsi          = ta.rsi(close, rsiLen)
isOversold   = rsi < oversold
isOverbought = rsi > overbought
bullRev      = isOversold[1]   and ta.crossover(rsi, oversold)
bearRev      = isOverbought[1] and ta.crossunder(rsi, overbought)

# ═══════════════════════════════════════════════════════════
#  FILTERS
# ═══════════════════════════════════════════════════════════

# Volume
volSMA = ta.sma(volume, volLen)
fVol   = not useVol or (volume > volSMA * volMult)

# Candle
fCandleBuy  = not useCandle or (close > open)
fCandleSell = not useCandle or (close < open)

# RSI Depth
depthOS = 0
depthOB = 0
for i in range(1, depthBars + 1):
    depthOS += (rsi[i] < oversold   ? 1 : 0)
    depthOB += (rsi[i] > overbought ? 1 : 0)

fDepthBuy  = not useDepth or (depthOS >= depthBars)
fDepthSell = not useDepth or (depthOB >= depthBars)

# ATR
atr    = ta.atr(atrLen)
atrAvg = ta.sma(atr, 50)
fATR   = not useATR or (atr > atrAvg)

# ═══════════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════════
lastSignal = 0  # var int lastSignal = 0
lastBar    = None  # var int lastBar = na

cooldownOK = lastBar is None or (bar_index - lastBar > cooldownBars)

# ═══════════════════════════════════════════════════════════
#  FINAL SIGNALS
# ═══════════════════════════════════════════════════════════
buySignal  = bullRev and cooldownOK and lastSignal != 1 and fVol and fCandleBuy and fDepthBuy and fATR
sellSignal = bearRev and cooldownOK and lastSignal != -1 and fVol and fCandleSell and fDepthSell and fATR

if buySignal:
    lastSignal = 1
    lastBar    = bar_index

if sellSignal:
    lastSignal = -1
    lastBar    = bar_index

# ═══════════════════════════════════════════════════════════
#  PLOTS
# ═══════════════════════════════════════════════════════════
# plotshape(buySignal, location = location.belowbar,
#      style = shape.labelup, text = "▲ BUY",
#      color = color.lime, textcolor = color.white, size = size.small)

# plotshape(sellSignal, location = location.abovebar,
#      style = shape.labeldown, text = "▼ SELL",
#      color = color.red, textcolor = color.white, size = size.small)

# ═══════════════════════════════════════════════════════════
#  ALERTS
# ═══════════════════════════════════════════════════════════
# alertcondition(buySignal,  title = "BUY Signal",
#      message = "RSI PRO+ BUY │ {{ticker}} │ {{close}}")

# alertcondition(sellSignal, title = "SELL Signal",
#      message = "RSI PRO+ SELL │ {{ticker}} │ {{close}}")
