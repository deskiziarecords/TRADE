import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class LiquidityFieldModel:
    def __init__(self, market_data):
        self.market_data = market_data
        self.liquidity_field = self.calculate_liquidity_field()

    def calculate_liquidity_field(self):
        # Placeholder for liquidity field calculation
        return np.random.rand(len(self.market_data))

    def detect_wick_patterns(self):
        wicks = []
        for i in range(1, len(self.market_data) - 1):
            if (self.market_data[i] > self.market_data[i - 1] and 
                self.market_data[i] > self.market_data[i + 1]):
                wicks.append((i, self.market_data[i]))
            elif (self.market_data[i] < self.market_data[i - 1] and 
                  self.market_data[i] < self.market_data[i + 1]):
                wicks.append((i, self.market_data[i]))
        return wicks

    def animate_wicks(self, wicks):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        x = np.arange(len(self.market_data))
        y = self.market_data
        z = self.liquidity_field

        ax.plot(x, y, z, label='Market Data')
        for wick in wicks:
            ax.scatter(wick[0], wick[1], self.calculate_liquidity_field()[wick[0]], color='r', s=100)

        ax.set_xlabel('Time')
        ax.set_ylabel('Price')
        ax.set_zlabel('Liquidity Field')
        plt.title('3D Liquidity Field with Wick Patterns')
        plt.legend()
        plt.show()

# Example usage
market_data = np.random.rand(100) * 100  # Simulated market data
model = LiquidityFieldModel(market_data)
wicks = model.detect_wick_patterns()
model.animate_wicks(wicks)
