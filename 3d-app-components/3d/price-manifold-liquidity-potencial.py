import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Parameters
time = np.linspace(0, 10, 100)
price = np.sin(time) * np.exp(-time / 3)
liquidity = np.cos(time) * np.exp(-time / 5)

# Create a meshgrid for the price manifold
T, P = np.meshgrid(time, price)
L = np.meshgrid(time, liquidity)[1]

# Create a 3D plot
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Plot the price manifold with liquidity potential
ax.plot_surface(T, P, L, cmap='viridis')

# Labels
ax.set_xlabel('Time')
ax.set_ylabel('Price')
ax.set_zlabel('Liquidity')

# Show the plot
plt.show()
