import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Parameters
x = np.linspace(-10, 10, 100)
y = np.linspace(-10, 10, 100)
X, Y = np.meshgrid(x, y)

# Magnet potential function with exponential decay
def magnet_potential(X, Y, decay_rate=0.1):
    return np.exp(-decay_rate * (np.sqrt(X**2 + Y**2)))

# Calculate Z values for the magnet potential
Z = magnet_potential(X, Y)

# Create a 3D plot
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Plot the surface
ax.plot_surface(X, Y, Z, cmap='viridis', edgecolor='none')

# Add vector arrows to indicate direction towards high-potential zones
U, V = np.gradient(Z)
ax.quiver(X, Y, Z, U, V, np.zeros_like(Z), length=0.5, color='r')

# Labels and title
ax.set_xlabel('X-axis')
ax.set_ylabel('Y-axis')
ax.set_zlabel('Magnet Potential (Φ_mag)')
ax.set_title('3D Visualization of Magnet Potential with Exponential Decay')

plt.show()
