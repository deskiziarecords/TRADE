import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class FairValueGapDetector:
    def __init__(self, price_data):
        self.price_data = price_data
        self.fvg_list = []

    def detect_fvg(self):
        for i in range(1, len(self.price_data) - 1):
            if self.price_data[i] < self.price_data[i - 1] and self.price_data[i] < self.price_data[i + 1]:
                self.fvg_list.append((i, self.price_data[i]))

    def render_fvg(self):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        x = np.arange(len(self.price_data))
        y = np.zeros_like(x)
        z = self.price_data

        ax.plot(x, y, z, label='Price Data')
        for fvg in self.fvg_list:
            ax.scatter(fvg[0], 0, fvg[1], color='r', s=100, label='FVG')

        ax.set_xlabel('Time')
        ax.set_ylabel('Liquidity Field')
        ax.set_zlabel('Price')
        ax.set_title('Fair Value Gap Detection')
        plt.legend()
        plt.show()

# Example usage
price_data = np.random.normal(100, 1, 100).tolist()  # Simulated price data
fvg_detector = FairValueGapDetector(price_data)
fvg_detector.detect_fvg()
fvg_detector.render_fvg()
