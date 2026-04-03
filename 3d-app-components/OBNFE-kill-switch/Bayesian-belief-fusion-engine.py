import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

class BayesianFusionEngine:
    def __init__(self):
        self.signals = []
        self.severity_score = 0

    def add_signal(self, signal):
        self.signals.append(signal)

    def compute_severity_score(self):
        if not self.signals:
            return 0
        self.severity_score = np.mean(self.signals)
        return self.severity_score

    def reset_phase(self):
        if self.severity_score > 0.75:  # Threshold for phase reset
            print("Phase reset triggered!")
            self.signals.clear()

class MarketGeometry:
    def __init__(self):
        self.bayesian_engine = BayesianFusionEngine()

    def update_signals(self, structural_signal, geometric_signal, liquidity_signal, causal_signal):
        combined_signal = np.mean([structural_signal, geometric_signal, liquidity_signal, causal_signal])
        self.bayesian_engine.add_signal(combined_signal)

    def display_health_gauge(self):
        severity = self.bayesian_engine.compute_severity_score()
        plt.figure(figsize=(5, 2))
        plt.barh(['Market Health'], [severity], color='blue' if severity < 0.75 else 'red')
        plt.xlim(0, 1)
        plt.title('Market Health Gauge')
        plt.xlabel('Severity Score')
        plt.show()

# Example usage
market = MarketGeometry()
market.update_signals(0.6, 0.7, 0.8, 0.5)
market.display_health_gauge()
market.bayesian_engine.reset_phase()
