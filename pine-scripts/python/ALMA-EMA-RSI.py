# Converted from Pine Script to Python

# Import necessary libraries
import pandas as pd
import numpy as np

# ALMA/EMA Strategy
initial_capital = 1000
pyramiding = 0
default_qty_value = 1000

# Source Selection & ALMA Variables
dsource = close  # Assuming 'close' is a pandas Series of closing prices
dperiod = 130
doffset = 0.775
dsigma = 4.5

# ALMA Calculation
def alma(series, period, offset, sigma):
    m = (period - 1) / 2.0
    s = sigma * (period - 1) / 6.0
    weights = np.exp(-0.5 * ((np.arange(period) - m) / s) ** 2)
    weights /= weights.sum()
    return np.convolve(series, weights, mode='valid')

dalma = alma(dsource, dperiod, doffset, dsigma)

# Color determination
dalma_up_color = '#66bb6a'
dalma_down_color = '#ef5350'
dcolor = np.where(close.shift(1) > dalma, dalma_up_color, dalma_down_color)

# Strategy Inputs
cheatcode = True
inp1 = 49  # Slow Ema Length
inp2 = 9   # Fast Ema Length
inp3 = 200  # Long MA Length

# EMA and SMA Calculations
sma1 = close.rolling(window=inp3).mean()
ema1 = close.ewm(span=inp1, adjust=False).mean()
ema2 = close.ewm(span=inp2, adjust=False).mean()

# Crossover detection
cross1 = (ema1 > ema2) & (ema1.shift(1) <= ema2.shift(1))
cross2 = (ema1 < ema2) & (ema1.shift(1) >= ema2.shift(1))

# Entry conditions
long_entry = cross1 & (close.shift(2) > dalma.shift(2)) & (close.shift(1) > dalma.shift(1))
short_entry = cross2 & (close.shift(2) < dalma.shift(2)) & (close.shift(1) < dalma.shift(1))

# Stochastic RSI
smoothK = 3
smoothD = 15
lengthRSI = 14
lengthStoch = 8
rsi1 = close.rolling(window=lengthRSI).apply(lambda x: (x - x.mean()) / x.std(), raw=False)
k = rsi1.rolling(window=lengthStoch).mean().rolling(window=smoothK).mean()
d = k.rolling(window=smoothD).mean()

# Cancellations
long_cancel = k > 75
short_cancel = k < 25

# Closures
long_close = (k.shift(1) > d.shift(1)) & (k > 92)
short_close = (k.shift(1) < d.shift(1)) & (k < 8)

# Exit Percentages
takeP = 0.03  # 3%
stopL = 0.0549  # 5.49%

# Pre Directionality
Stop_L = position_avg_price * (1 - stopL)
Stop_S = position_avg_price * (1 + stopL)
Take_S = position_avg_price * (1 - takeP)
Take_L = position_avg_price * (1 + takeP)

# Post Execution
if position_size > 0:
    exit("Flat", limit=Take_L, stop=Stop_L)

if position_size < 0:
    exit("Flat", limit=Take_S, stop=Stop_S)
