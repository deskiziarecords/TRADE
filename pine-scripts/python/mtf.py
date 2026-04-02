# MTF - Stoch in Python

# === Inputs ===
period = 10  # Period, minimum value is 1

# === First Stochastic Calculation (p1) ===
maxHigh = max(high[-period:])  # Highest high over the period
minLow = min(low[-period:])     # Lowest low over the period
r = maxHigh - minLow

if r == 0:
    p1 = 50 if bar_index == 0 else p1_prev  # Previous value of p1
else:
    p1 = min(100, max(0, 100 * (close - minLow) / r))

# === EMA of p1 (p2) ===
p2 = ema(p1, 3)  # Exponential Moving Average of p1

# === Second Stochastic Calculation (p3) ===
maxP2 = max(p2[-period:])  # Highest p2 over the period
minP2 = min(p2[-period:])  # Lowest p2 over the period
s = maxP2 - minP2

if s == 0:
    p3 = 50 if bar_index == 0 else p3_prev  # Previous value of p3
else:
    p3 = min(100, max(0, 100 * (p2 - minP2) / s))

# === Final Output (K) ===
K = ema(p3, 3)  # Exponential Moving Average of p3

# === Plots ===
plot(K, title="K", color='yellow', linewidth=1)
hline(90, "Upper", linestyle='dotted')
hline(10, "Lower", linestyle='dotted')

# === Signal Conditions ===
bullBreak = crossover(K, 10)  # Bullish crossover condition
bearBreak = crossunder(K, 90)  # Bearish crossunder condition

# === Arrows ===
plotshape(bullBreak, style='triangleup', location='absolute', color='green', size='tiny')
plotshape(bearBreak, style='triangledown', location='absolute', color='red', size='tiny')

# === Background Highlight ===
bgcolor(bullBreak, color='green', alpha=85)  # Highlight background for bullish break
bgcolor(bearBreak, color='red', alpha=85)     # Highlight background for bearish break
