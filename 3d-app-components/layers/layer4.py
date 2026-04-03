import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class TradingModel:
    def __init__(self, confidence_scores, returns):
        self.confidence_scores = confidence_scores
        self.returns = returns

    def detect_confluence_collapse(self):
        high_confidence = self.confidence_scores > 0.6
        negative_expectancy = np.mean(self.returns[high_confidence]) < 0
        return high_confidence, negative_expectancy

    def visualize_confluence_zones(self):
        high_confidence, negative_expectancy = self.detect_confluence_collapse()
        x = np.linspace(-5, 5, 100)
        y = np.linspace(-5, 5, 100)
        X, Y = np.meshgrid(x, y)
        Z = np.exp(-0.1 * (X**2 + Y**2))

        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_surface(X, Y, Z, cmap='viridis' if not negative_expectancy else 'plasma')

        if negative_expectancy:
            ax.set_title('Confluence Collapse Detected: Inverted Polarity')
            ax.text2D(0.05, 0.95, "Warning: Expectancy Inversion", transform=ax.transAxes, fontsize=12, color='red')
        else:
            ax.set_title('Confluence Zones')

        plt.show()

# Example usage
confidence_scores = np.random.rand(100)  # Simulated confidence scores
returns = np.random.randn(100)  # Simulated returns
model = TradingModel(confidence_scores, returns)
model.visualize_confluence_zones()
