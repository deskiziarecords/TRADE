import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Generate synthetic price data
np.random.seed(42)
days = 100
price_data = np.cumsum(np.random.randn(days)) + 100

# Create a DataFrame
df = pd.DataFrame(price_data, columns=['Price'])
df['Date'] = pd.date_range(start='2023-01-01', periods=days)

# Function to create structural boxes
def create_boxes(df, window):
    boxes = []
    for i in range(len(df) - window):
        box = df['Price'][i:i + window].min(), df['Price'][i:i + window].max()
        boxes.append((df['Date'][i], box))
    return boxes

# Create boxes for 20, 40, and 60 days
boxes_20 = create_boxes(df, 20)
boxes_40 = create_boxes(df, 40)
boxes_60 = create_boxes(df, 60)

# 3D Visualization
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Function to plot boxes
def plot_boxes(ax, boxes, color):
    for date, (min_price, max_price) in boxes:
        ax.bar(date, max_price - min_price, zs=min_price, zdir='y', alpha=0.5, color=color)

# Plotting the boxes
plot_boxes(ax, boxes_20, 'blue')
plot_boxes(ax, boxes_40, 'green')
plot_boxes(ax, boxes_60, 'red')

ax.set_xlabel('Date')
ax.set_ylabel('Price')
ax.set_zlabel('Volume')
plt.title('3D Structural Boxes for Trading Model')
plt.show()
