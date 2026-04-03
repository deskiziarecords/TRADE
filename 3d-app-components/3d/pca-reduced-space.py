import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from sklearn.decomposition import PCA

# Generate synthetic data for the state space
np.random.seed(42)
data = np.random.rand(100, 5)  # 100 samples in 5 dimensions

# Apply PCA to reduce dimensions to 3
pca = PCA(n_components=3)
reduced_data = pca.fit_transform(data)

# Create a 3D plot
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

# Scatter plot of the PCA-reduced data
ax.scatter(reduced_data[:, 0], reduced_data[:, 1], reduced_data[:, 2], c='b', marker='o')

# Simulate fracture markers
fracture_indices = np.random.choice(range(100), size=10, replace=False)
for index in fracture_indices:
    ax.plot([reduced_data[index, 0]], [reduced_data[index, 1]], [reduced_data[index, 2]], 
            marker='o', markersize=10, color='r', label='Fracture' if index == fracture_indices[0] else "")

# Set labels
ax.set_xlabel('PCA Component 1')
ax.set_ylabel('PCA Component 2')
ax.set_zlabel('PCA Component 3')
ax.set_title('PCA-Reduced State Space with Fracture Markers')

# Show plot
plt.legend()
plt.show()
