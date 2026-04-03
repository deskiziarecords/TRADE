#
#λ1: Phase Entrapment (State Persistence Failure)
#What it detects:

#Price is "stuck" in a Distribution phase (σt=2) without meaningful directional movement, suggesting a breakdown in trend continuity.
#Mathematical Conditions:

#Phase Requirement: σt = 2 (Distribution phase, e.g., range-bound or consolidation).
#Time Parameter: τstay(t) > τmax (price spends too long in this phase).

#Volatility Parameter: Vt / ATR20 < δ (price variation is abnormally low relative to ATR).
#Forex Relevance:

#Detects liquidity traps or institutional accumulation/distribution zones (e.g., before a breakout).
#Useful for mean reversion or breakout strategies.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Parameters
σt = 2  # Distribution phase
τmax = 10  # Maximum time in phase
δ = 0.5  # Volatility threshold
ATR_period = 20  # ATR calculation period

# Sample price data
np.random.seed(0)
price_data = np.random.normal(loc=100, scale=1, size=100)
price_series = pd.Series(price_data)

# Calculate ATR
def calculate_atr(prices, period):
    high = prices.rolling(window=period).max()
    low = prices.rolling(window=period).min()
    tr = high - low
    atr = tr.rolling(window=period).mean()
    return atr

ATR = calculate_atr(price_series, ATR_period)

# Phase detection
def detect_phase(prices):
    phase = []
    for i in range(len(prices)):
        if i < 1:
            phase.append(0)
        else:
            if prices[i] == prices[i-1]:
                phase.append(σt)
            else:
                phase.append(0)
    return phase

phase_series = detect_phase(price_series)

# Calculate τstay(t)
def calculate_tau_stay(phase_series):
    tau_stay = 0
    for phase in phase_series:
        if phase == σt:
            tau_stay += 1
        else:
            tau_stay = 0
    return tau_stay

τstay = calculate_tau_stay(phase_series)

# Calculate Vt
def calculate_volatility(prices, τstay):
    if τstay > 0:
        return np.std(prices[-τstay:])
    return 0

Vt = calculate_volatility(price_series, τstay)

# Visualization
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

x = np.arange(len(price_series))
y = price_series
z = np.zeros(len(price_series))

# Create a box around the price
if τstay > τmax and Vt / ATR.iloc[-1] < δ:
    ax.bar(x, y, z, zs=0, zdir='y', alpha=0.5, color='red')
else:
    ax.bar(x, y, z, zs=0, zdir='y', alpha=0.5, color='green')

ax.set_xlabel('Time')
ax.set_ylabel('Price')
ax.set_zlabel('Volume')

plt.show()

