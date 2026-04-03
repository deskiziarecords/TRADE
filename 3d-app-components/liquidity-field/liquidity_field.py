import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata

class LiquidityFieldModel:
    def __init__(self, num_points=100):
        self.num_points = num_points
        self.hidden_energy = self.generate_hidden_energy()

    def generate_hidden_energy(self):
        x = np.random.uniform(0, 1, self.num_points)
        y = np.random.uniform(0, 1, self.num_points)
        energy = np.random.normal(loc=0, scale=1, size=self.num_points)
        return x, y, energy

    def calculate_price_movement(self):
        x, y, energy = self.hidden_energy
        price_movement = np.sum(energy) / self.num_points
        return price_movement

    def visualize_liquidity_field(self):
        x, y, energy = self.hidden_energy
        grid_x, grid_y = np.mgrid[0:1:100j, 0:1:100j]
        grid_energy = griddata((x, y), energy, (grid_x, grid_y), method='cubic')

        plt.figure(figsize=(10, 8))
        plt.imshow(grid_energy.T, extent=(0, 1, 0, 1), origin='lower', cmap='hot')
        plt.colorbar(label='Hidden Energy')
        plt.title('Liquidity Field Visualization')
        plt.xlabel('Market Dimension X')
        plt.ylabel('Market Dimension Y')
        plt.show()

if __name__ == "__main__":
    model = LiquidityFieldModel()
    price_movement = model.calculate_price_movement()
    print(f"Calculated Price Movement: {price_movement}")
    model.visualize_liquidity_field()
