import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Parameters
time = np.linspace(0, 10, 100)
price = np.linspace(1, 100, 100)
P = np.random.rand(100) * 100  # Random price data
V = np.random.rand(100) * 10    # Random volume data

# Calculate Liquidity Potential
U = P * V

# Calculate gradients
dU = np.gradient(U)
dU_hist = np.gradient(np.roll(U, 1))  # Historical gradient

# Inversion Condition
inversion_condition = np.dot(dU, dU_hist) < 0

# 3D Visualization
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
X, Y = np.meshgrid(time, price)
Z = np.outer(U, np.ones(len(time)))

# Plotting the surface
ax.plot_surface(X, Y, Z, alpha=0.5, cmap='viridis')

# Highlight inversions
for i in range(len(inversion_condition)):
    if inversion_condition[i]:
        ax.quiver(time[i], price[i], U[i], 0, 0, -10, color='red', arrow_length_ratio=0.1)

ax.set_xlabel('Time')
ax.set_ylabel('Price')
ax.set_zlabel('Liquidity Potential (U)')
plt.title('Liquidity Field Inversion Visualization')
plt.show()
