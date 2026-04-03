import jax.numpy as jnp
import pandas as pd
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

class OBNFE:
    def __init__(self, price_data):
        self.price_data = price_data
        self.atr_period = 20

    def calculate_atr(self):
        high_low = self.price_data['High'] - self.price_data['Low']
        high_close = jnp.abs(self.price_data['High'] - self.price_data['Close'].shift())
        low_close = jnp.abs(self.price_data['Low'] - self.price_data['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=self.atr_period).mean()
        return atr

    def lambda_sensor_1(self):
        self.price_data['σt'] = 2  # Assuming we are in a distribution phase
        self.price_data['τstay'] = (self.price_data['σt'] == 2).astype(int).cumsum()
        self.price_data['Vt'] = self.price_data['Close'].rolling(window=self.price_data['τstay']).std()
        self.price_data['ATR'] = self.calculate_atr()
        δ = 0.5  # Example threshold
        self.price_data['Phase_Entrapment'] = (self.price_data['τstay'] > 10) & (self.price_data['Vt'] / self.price_data['ATR'] < δ)

    def lambda_sensor_2(self):
        self.price_data['Killzone'] = ((self.price_data.index.hour == 8) | (self.price_data.index.hour == 9)).astype(int)
        self.price_data['Directional_Sum'] = self.price_data['Close'].diff().rolling(window=20).apply(lambda x: jnp.sign(x).sum())
        γ = 0.45  # Example threshold
        self.price_data['Temporal_Failure'] = (self.price_data['Killzone'] == 1) & (self.price_data['Directional_Sum'] < γ)

    def visualize(self):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(self.price_data.index, self.price_data['Close'], self.price_data['Phase_Entrapment'], c='r', marker='o')
        ax.set_xlabel('Time')
        ax.set_ylabel('Price')
        ax.set_zlabel('Phase Entrapment')
        plt.show()

# Example usage
price_data = pd.DataFrame({
    'High': jnp.random.rand(100) * 100,
    'Low': jnp.random.rand(100) * 100,
    'Close': jnp.random.rand(100) * 100
}, index=pd.date_range(start='2023-01-01', periods=100, freq='H'))

obnfe = OBNFE(price_data)
obnfe.lambda_sensor_1()
obnfe.lambda_sensor_2()
obnfe.visualize()
