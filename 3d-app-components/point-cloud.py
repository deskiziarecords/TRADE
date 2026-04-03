import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import pandas as pd

class TradingModel:
    def __init__(self, data, window_size):
        self.data = data
        self.window_size = window_size
        self.point_cloud = []

    def update_point_cloud(self):
        for i in range(len(self.data) - self.window_size):
            window = self.data[i:i + self.window_size]
            time = np.arange(self.window_size)
            price = window['price'].values
            volume = window['volume'].values
            self.point_cloud.append(np.column_stack((time, price, volume)))

    def plot_point_cloud(self):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        for cloud in self.point_cloud:
            ax.scatter(cloud[:, 0], cloud[:, 1], cloud[:, 2], alpha=0.5)
        ax.set_xlabel('Time')
        ax.set_ylabel('Price')
        ax.set_zlabel('Volume')
        plt.show()

# Example usage
data = pd.DataFrame({
    'price': np.random.rand(100),
    'volume': np.random.rand(100)
})

model = TradingModel(data, window_size=10)
model.update_point_cloud()
model.plot_point_cloud()
