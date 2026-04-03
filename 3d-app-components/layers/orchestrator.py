import numpy as np
from sklearn.linear_model import LogisticRegression

class TradingModel:
    def __init__(self, weights):
        self.weights = weights
        self.model = LogisticRegression()

    def compute_rscore(self, sensor_outputs):
        rscore = np.dot(self.weights, sensor_outputs)
        return rscore

    def train_model(self, X, y):
        self.model.fit(X, y)

    def predict_reverse_period(self, sensor_outputs):
        rscore = self.compute_rscore(sensor_outputs)
        probability = self.model.predict_proba([sensor_outputs])[0][1]
        return rscore, probability

    def decision_rule(self, rscore, threshold=0.7):
        if rscore > threshold:
            return 0, 0  # Trading halt and phase reset
        return 1, 1  # Continue trading

# Example usage
weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])
model = TradingModel(weights)

# Simulated sensor outputs
sensor_outputs = np.array([0.8, 0.6, 0.9, 0.4, 0.5])
rscore = model.compute_rscore(sensor_outputs)
print("Rscore:", rscore)

# Assuming we have training data X and labels y
# model.train_model(X, y)

# Predicting reverse period
rscore, probability = model.predict_reverse_period(sensor_outputs)
print("Rscore:", rscore, "Probability of Reverse Period:", probability)

# Applying decision rule
trading_status, phase_status = model.decision_rule(rscore)
print("Trading Status:", trading_status, "Phase Status:", phase_status)
