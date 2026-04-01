# @version=5
# indicator("Filtered Swing Trend Signals v3", overlay=true, max_labels_count=500)

# --- Inputs ---
# Core Trend Parameters
atrPeriod = 10  # Trend ATR Length
factor = 3.0    # Trend Multiplier

# Momentum & Fuel Filters
adxLength = 14  # ADX Length
adxThreshold = 20  # ADX Threshold
macdFast = 12   # MACD Fast
macdSlow = 26   # MACD Slow
macdSignal = 9  # MACD Signal

# Dynamic Exit Parameters
exitEmaLength = 13  # Exit EMA Length (Waning Momentum)
minBarsHold = 5     # Minimum Bars to Hold Before TP

# --- Calculations ---
# 1. Core Trend
supertrend, direction = ta.supertrend(factor, atrPeriod)
isUptrend = direction < 0
isDowntrend = direction > 0

# 2. Momentum Fuel Filters
diplus, diminus, adx = ta.dmi(adxLength, adxLength)
macdLine, sigLine, histLine = ta.macd(close, macdFast, macdSlow, macdSignal)

bullishFuel = (adx > adxThreshold) and (histLine > 0)
bearishFuel = (adx > adxThreshold) and (histLine < 0)

# 3. Fast Momentum EMA (Used for Exits AND Re-entries)
exitEma = ta.ema(close, exitEmaLength)

# --- State Variables ---
inLong = False
inShort = False
entryBar = None
entryPrice = None

# --- Entry Logic (Updated for Re-entries) ---
# Trigger 1: The initial Supertrend flip
longStart = ta.change(direction) < 0
shortStart = ta.change(direction) > 0

# Trigger 2: Continuation / Re-entry (Trend is intact, price surges back over the fast EMA after a pullback)
longContinuation = isUptrend and ta.crossover(close, exitEma)
shortContinuation = isDowntrend and ta.crossunder(close, exitEma)

# Combine triggers with Fuel
longCond = (longStart or longContinuation) and bullishFuel
shortCond = (shortStart or shortContinuation) and bearishFuel

# Ensure we only trigger if we aren't already actively in a trade
longSignal = longCond and not inLong
shortSignal = shortCond and not inShort

if longSignal:
    inLong = True
    inShort = False
    entryBar = bar_index
    entryPrice = close

if shortSignal:
    inShort = True
    inLong = False
    entryBar = bar_index
    entryPrice = close

# --- Exit / Take Profit Logic ---
barsHeld = bar_index - entryBar

# Waning momentum is detected when price crosses back over the short-term EMA
longWaning = ta.crossunder(close, exitEma)
shortWaning = ta.crossover(close, exitEma)

# TP Criteria: Held for X bars, Currently in Profit, and Momentum is Waning
longTP = inLong and (barsHeld >= minBarsHold) and (close > entryPrice) and longWaning
shortTP = inShort and (barsHeld >= minBarsHold) and (close < entryPrice) and shortWaning

# Stop Loss / Hard Reset Criteria (If trend fully reverses without hitting TP rules)
longSL = inLong and ta.change(direction) > 0
shortSL = inShort and ta.change(direction) < 0

# Reset states on exit so the script can look for a re-entry
if longTP or longSL:
    inLong = False
if shortTP or shortSL:
    inShort = False

# --- Visuals ---
# Plot Signals
plotshape(longSignal, title="Buy Signal", text="BUY", style=shape.labelup, location=location.belowbar, color=color.new(#00b300, 0), textcolor=color.white, size=size.normal)
plotshape(shortSignal, title="Sell Signal", text="SELL", style=shape.labeldown, location=location.abovebar, color=color.new(#ff0000, 0), textcolor=color.white, size=size.normal)

# Plot Take Profits
plotshape(longTP, title="TP Long", text="TP", style=shape.xcross, location=location.abovebar, color=color.new(#00b300, 0), textcolor=color.white, size=size.small)
plotshape(shortTP, title="TP Short", text="TP", style=shape.xcross, location=location.belowbar, color=color.new(#ff0000, 0), textcolor=color.white, size=size.small)
