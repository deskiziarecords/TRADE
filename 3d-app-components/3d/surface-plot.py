import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Generate sample data for liquidity imbalances
x = np.linspace(-5, 5, 100)
y = np.linspace(-5, 5, 100)
x, y = np.meshgrid(x, y)
z = np.sin(np.sqrt(x**2 + y**2)) * np.exp(-0.1 * (x**2 + y**2))

# Create a 3D surface plot
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.plot_surface(x, y, z, cmap='viridis')

# Set labels
ax.set_xlabel('X-axis (Order Flow)')
ax.set_ylabel('Y-axis (Liquidity Imbalance)')
ax.set_zlabel('Z-axis (Value)')

# Show the plot
plt.title('3D Surface Plot of Liquidity Imbalance Field')
plt.show()
