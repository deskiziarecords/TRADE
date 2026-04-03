import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

class TradingModel:
    def __init__(self):
        self.severity_score = 0.0
        self.market_geometry = np.random.rand(3)
    
    def calculate_severity(self, signals):
        self.severity_score = np.mean(signals)
        return self.severity_score
    
    def phase_reset(self):
        if self.severity_score >= 0.7:
            self.reset_system()
    
    def reset_system(self):
        print("Phase reset triggered! Recalibrating system...")
        self.market_geometry = np.random.rand(3)
        self.severity_score = 0.0
        self.animate_reset()
    
    def animate_reset(self):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        x = np.linspace(-1, 1, 100)
        y = np.linspace(-1, 1, 100)
        X, Y = np.meshgrid(x, y)
        Z = np.sin(np.sqrt(X**2 + Y**2))
        
        ax.plot_surface(X, Y, Z, cmap='viridis', alpha=0.5)
        ax.set_title('System-wide Pulse Effect')
        plt.show()

# Example usage
model = TradingModel()
signals = np.random.rand(10)  # Simulated signals
severity = model.calculate_severity(signals)
model.phase_reset()
