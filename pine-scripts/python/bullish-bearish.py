# import necessary libraries
import pandas as pd
import numpy as np

# User inputs
fast_ma = 9  # Fast MA
slow_ma = 21  # Slow MA
show_labels = True  # Show Signal Labels

# Assuming 'data' is a DataFrame containing 'close' and 'open' prices
data['ma_fast'] = data['close'].rolling(window=fast_ma).mean()  # Moving Average Fast
data['ma_slow'] = data['close'].rolling(window=slow_ma).mean()  # Moving Average Slow

# Bullish and Bearish Conditions
data['bullish'] = (data['ma_fast'] > data['ma_slow']) & (data['close'] > data['open'])  # Bullish Condition
data['bearish'] = (data['ma_fast'] < data['ma_slow']) & (data['close'] < data['open'])  # Bearish Condition

# Plot signals as triangles (this part would typically be done using a plotting library)
# For example, using matplotlib or similar to visualize the signals
# plt.scatter(data.index[data['bullish']], data['low'][data['bullish']], marker='^', color='green', s=10)  # Bullish Signal
# plt.scatter(data.index[data['bearish']], data['high'][data['bearish']], marker='v', color='red', s=10)  # Bearish Signal

# Optional labels
if show_labels:
    for index, row in data.iterrows():
        if row['bullish']:
            # plt.text(index, row['low'], 'BUY', color='green', fontsize=8)  # Label for BUY
            pass  # Replace with actual plotting code
        if row['bearish']:
            # plt.text(index, row['high'], 'SELL', color='red', fontsize=8)  # Label for SELL
            pass  # Replace with actual plotting code
