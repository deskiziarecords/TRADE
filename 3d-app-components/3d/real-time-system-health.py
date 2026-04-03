# Physics-Inspired Trading Model

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class TradingModel:
    def __init__(self):
        self.severity_score = 0
        self.kill_switch = False

    def update_severity_score(self, new_score):
        self.severity_score = new_score
        if self.severity_score > 75:
            self.kill_switch = True

    def display_dashboard(self):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        
        # Sample data for the 3D environment
        x = np.random.rand(100)
        y = np.random.rand(100)
        z = np.random.rand(100)
        
        ax.scatter(x, y, z, c='r', marker='o')
        ax.set_xlabel('X Label')
        ax.set_ylabel('Y Label')
        ax.set_zlabel('Z Label')
        
        # Displaying the severity score and kill switch status
        plt.text2D(0.05, 0.95, f'Severity Score: {self.severity_score}', transform=ax.transAxes)
        plt.text2D(0.05, 0.90, f'Kill Switch: {"ON" if self.kill_switch else "OFF"}', transform=ax.transAxes)
        
        plt.show()

# Example usage
model = TradingModel()
model.update_severity_score(80)
model.display_dashboard()
