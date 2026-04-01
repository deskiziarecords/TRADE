# @version=5
# indicator("Pro Scalper: Breakout & Trend v13 (No SL)", overlay=true, max_labels_count=500, max_lines_count=500)

# ============================================================================ 
# INPUT PARAMETERS 
# ============================================================================ 
grp_trend = "1. Trend & Macro Engine" 
atrPeriod = 7  # Trend ATR Length 
factor = 2.5  # Trend Multiplier 
emaLength = 200  # Macro Trend EMA 

grp_mom = "2. Momentum Fuel" 
adxLength = 14  # ADX Length 
adxThreshold = 20  # ADX Threshold 
macdFast = 12  # MACD Fast 
macdSlow = 26  # MACD Slow 
macdSignal = 9  # MACD Signal 

grp_chop = "3. Sideways Market Filter" 
chopLength = 14  # Choppiness Index Length 
chopThreshold = 61.8  # Max Choppiness (Avoid Sideways) 

grp_brk = "4. Breakout Strategy" 
breakoutLen = 15  # Breakout Lookback Length 

grp_risk = "5. Reward Management (No SL)" 
minBarsHold = 1  # Min Candles Before TP 
tpAtrLen = 14  # Target ATR Length 
tpMult = 2.0  # Base TP Multiplier (Distant) 

# ============================================================================ 
# CORE CALCULATIONS 
# ============================================================================ 
# Macro Trend 
macroEma = ta.ema(close, emaLength) 
isMacroBull = close > macroEma 
isMacroBear = close < macroEma 

# Supertrend 
supertrend, direction = ta.supertrend(factor, atrPeriod) 
isUptrend = direction < 0 
isDowntrend = direction > 0 

# Momentum Acceleration 
diplus, diminus, adx = ta.dmi(adxLength, adxLength) 
macdLine, sigLine, histLine = ta.macd(close, macdFast, macdSlow, macdSignal) 
bullishFuel = (adx > adxThreshold) and (adx > adx[1]) and (histLine > 0) and (histLine > histLine[1]) 
bearishFuel = (adx > adxThreshold) and (adx > adx[1]) and (histLine < 0) and (histLine < histLine[1]) 

# Choppiness Index (Zero-Division Safeguard) 
atrSum = math.sum(ta.atr(1), chopLength) 
highestHigh = ta.highest(high, chopLength) 
lowestLow = ta.lowest(low, chopLength) 
hlRange = highestHigh - lowestLow 
hlRange = hlRange if hlRange != 0 else syminfo.mintick 
chop = 100 * math.log10(atrSum / hlRange) / math.log10(chopLength) 
isChoppy = chop > chopThreshold 

# Breakout Levels & Candle Anatomy 
recentHigh = ta.highest(high[1], breakoutLen) 
recentLow = ta.lowest(low[1], breakoutLen) 
atrVal = ta.atr(tpAtrLen) 
isGreen = close > open 
isRed = close < open 

# ============================================================================ 
# STATE VARIABLES 
# ============================================================================ 
tradeDir = 0  # 1 = Long, -1 = Short, 0 = Flat 
entryPrice = None 
entryBar = None 
tp1Target = None 
tp2Target = None 
tp3Target = None 
tpState = 0 

# Visual Line Variables 
entryLine = None 
tpLine = None 

# ============================================================================ 
# STRICT ENTRY LOGIC (Macro Aligned) 
# ============================================================================ 
longCond = isUptrend and isMacroBull and bullishFuel and (close > recentHigh) and not isChoppy and isGreen 
shortCond = isDowntrend and isMacroBear and bearishFuel and (close < recentLow) and not isChoppy and isRed 

isNewLong = False 
isNewShort = False 

# Execute Long 
if longCond and tradeDir != 1: 
    tradeDir = 1 
    entryPrice = close 
    entryBar = bar_index 
    tp1Target = entryPrice + (atrVal * tpMult) 
    tp2Target = entryPrice + (atrVal * tpMult * 2.0) 
    tp3Target = entryPrice + (atrVal * tpMult * 3.0) 
    tpState = 0 
    isNewLong = True 

# Execute Short 
if shortCond and tradeDir != -1: 
    tradeDir = -1 
    entryPrice = close 
    entryBar = bar_index 
    tp1Target = entryPrice - (atrVal * tpMult) 
    tp2Target = entryPrice - (atrVal * tpMult * 2.0) 
    tp3Target = entryPrice - (atrVal * tpMult * 3.0) 
    tpState = 0 
    isNewShort = True 

# ============================================================================ 
# EXIT LOGIC (Take Profit & Structural Reversal) 
# ============================================================================ 
barsHeld = bar_index - entryBar 
canTakeProfit = barsHeld >= minBarsHold 

hitTp1 = False 
hitTp2 = False 
hitTp3 = False 
structuralExit = False 

if tradeDir == 1: 
    if tpState == 0 and high >= tp1Target and canTakeProfit: 
        hitTp1 = True 
        tpState = 1 
    if tpState == 1 and high >= tp2Target and canTakeProfit: 
        hitTp2 = True 
        tpState = 2 
    if tpState == 2 and high >= tp3Target and canTakeProfit: 
        hitTp3 = True 
        tradeDir = 0 

    # Structural Reversal Exit (Safety Net) 
    if ta.change(direction) > 0: 
        tradeDir = 0 
        structuralExit = True 

if tradeDir == -1: 
    if tpState == 0 and low <= tp1Target and canTakeProfit: 
        hitTp1 = True 
        tpState = 1 
    if tpState == 1 and low <= tp2Target and canTakeProfit: 
        hitTp2 = True 
        tpState = 2 
    if tpState == 2 and low <= tp3Target and canTakeProfit: 
        hitTp3 = True 
        tradeDir = 0 

    # Structural Reversal Exit (Safety Net) 
    if ta.change(direction) < 0: 
        tradeDir = 0 
        structuralExit = True 

# ============================================================================ 
# PROFESSIONAL VISUALS 
# ============================================================================ 
# Plot Macro Trend 
# plot(macroEma, color=isMacroBull ? color.new(color.blue, 50) : color.new(color.red, 50), linewidth=2, title="200 EMA") 

# Signals 
# plotshape(isNewLong, title="Buy Signal", text="BUY", style=shape.labelup, location=location.belowbar, color=color.rgb(0, 179, 0), textcolor=color.white, size=size.small) 
# plotshape(isNewShort, title="Sell Signal", text="SELL", style=shape.labeldown, location=location.abovebar, color=color.rgb(255, 51, 51), textcolor=color.white, size=size.small) 

# Labels for Exits 
# if hitTp1: 
#     label.new(bar_index, tradeDir[1] == 1 ? high : low, "TP1", color=color.rgb(0, 179, 0), style=tradeDir[1] == 1 ? label.style_label_down : label.style_label_up, textcolor=color.white, size=size.tiny) 
# if hitTp2: 
#     label.new(bar_index, tradeDir[1] == 1 ? high : low, "TP2", color=color.rgb(0, 179, 0), style=tradeDir[1] == 1 ? label.style_label_down : label.style_label_up, textcolor=color.white, size=size.tiny) 
# if hitTp3: 
#     label.new(bar_index, tradeDir[1] == 1 ? high : low, "TP3", color=color.rgb(0, 179, 0), style=tradeDir[1] == 1 ? label.style_label_down : label.style_label_up, textcolor=color.white, size=size.tiny) 
# if structuralExit: 
#     label.new(bar_index, tradeDir[1] == 1 ? low : high, "EXIT", color=color.rgb(120, 120, 120), style=tradeDir[1] == 1 ? label.style_label_up : label.style_label_down, textcolor=color.white, size=size.tiny) 

# Dynamic Trade Lines (Updates in Real-Time) 
# if tradeDir != 0: 
#     currentTarget = tpState == 0 ? tp1Target : (tpState == 1 ? tp2Target : tp3Target) 
#     if barstate.isrealtime or barstate.islast: 
#         line.delete(entryLine[1]) 
#         line.delete(tpLine[1]) 
#         entryLine = line.new(entryBar, entryPrice, bar_index, entryPrice, color=color.gray, style=line.style_dotted) 
#         tpLine = line.new(entryBar, currentTarget, bar_index, currentTarget, color=color.rgb(0, 179, 0), style=line.style_dashed) 
