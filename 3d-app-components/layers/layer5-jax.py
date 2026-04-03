import jax.numpy as jnp
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Parameters
time = jnp.linspace(0, 10, 100)
price = jnp.linspace(1, 100, 100)
P = jnp.random.rand(100) * 100  # Random price data
V = jnp.random.rand(100) * 10    # Random volume data

# Calculate Liquidity Potential
U = P * V

# Calculate gradients
dU = jnp.gradient(U)
dU_hist = jnp.gradient(jnp.roll(U, 1))  # Historical gradient

# Inversion Condition
inversion_condition = jnp.dot(dU, dU_hist) < 0

# 3D Visualization
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
X, Y = jnp.meshgrid(time, price)
Z = jnp.outer(U, jnp.ones(len(time)))

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
