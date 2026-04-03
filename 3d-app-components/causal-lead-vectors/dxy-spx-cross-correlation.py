import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import pearsonr
from mpl_toolkits.mplot3d import Axes3D

# Load forex and market data
forex_data = pd.read_csv('forex_data.csv')
dxy_data = pd.read_csv('dxy_data.csv')
spx_data = pd.read_csv('spx_data.csv')
bonds_data = pd.read_csv('bonds_data.csv')

# Function to calculate cross-correlation
def cross_correlation(forex_series, market_series, lag=0):
    return pearsonr(forex_series[:-lag], market_series[lag:])[0]

# Calculate lead-lag relationships
lags = range(-10, 11)
results = {lag: [] for lag in lags}

for lag in lags:
    results[lag].append(cross_correlation(forex_data['Forex_Pair'], dxy_data['DXY'], lag))
    results[lag].append(cross_correlation(forex_data['Forex_Pair'], spx_data['SPX'], lag))
    results[lag].append(cross_correlation(forex_data['Forex_Pair'], bonds_data['Bonds'], lag))

# Prepare data for 3D plotting
x = np.array(list(results.keys()))
y = np.array([result[0] for result in results.values()])
z = np.array([result[1] for result in results.values()])

# 3D Plotting
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.quiver(x, y, z, np.zeros_like(x), np.zeros_like(y), np.zeros_like(z), length=0.1)

ax.set_xlabel('Lag')
ax.set_ylabel('DXY Correlation')
ax.set_zlabel('SPX Correlation')
plt.title('Lead-Lag Relationships in Forex and Market Assets')
plt.show()
