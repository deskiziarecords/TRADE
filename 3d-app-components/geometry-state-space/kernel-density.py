import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn.neighbors import KernelDensity

# Generate synthetic market data
np.random.seed(42)
n_samples = 1000
X = np.random.normal(loc=0, scale=1, size=(n_samples, 2))

# Apply Kernel Density Estimation
kde = KernelDensity(kernel='gaussian', bandwidth=0.2).fit(X)
x_d = np.linspace(-3, 3, 100)
y_d = np.linspace(-3, 3, 100)
X_grid, Y_grid = np.meshgrid(x_d, y_d)
grid_points = np.vstack([X_grid.ravel(), Y_grid.ravel()]).T
log_density = kde.score_samples(grid_points)
density = np.exp(log_density).reshape(X_grid.shape)

# Define safety zone threshold
safety_threshold = np.percentile(density, 75)
safe_zone = density >= safety_threshold

# 3D Visualization
fig = plt.figure(figsize=(10, 7))
ax = fig.add_subplot(111, projection='3d')
ax.plot_surface(X_grid, Y_grid, density, facecolors=plt.cm.viridis(density / density.max()), alpha=0.7)
ax.contour(X_grid, Y_grid, density, zdir='z', offset=0, levels=10, cmap='viridis', alpha=0.5)

# Highlight safe zone
ax.scatter(X_grid[safe_zone], Y_grid[safe_zone], density[safe_zone], color='red', s=5, label='Safe Zone', alpha=0.5)

ax.set_title('Adelic Manifold Safety Zone via KDE')
ax.set_xlabel('Market Dimension 1')
ax.set_ylabel('Market Dimension 2')
ax.set_zlabel('Density')
ax.legend()
plt.show()
