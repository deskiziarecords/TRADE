import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Function to compute FFT and detect phase inversion
def spectral_phase_inversion(prices, window_size=64):
    fft_results = []
    phase_inversions = []
    
    for i in range(len(prices) - window_size):
        window = prices[i:i + window_size]
        fft_result = np.fft.fft(window)
        dominant_freq = np.fft.fftfreq(len(window), d=1)[:len(window)//2]
        dominant_amplitude = np.abs(fft_result)[:len(window)//2]
        
        # Detect dominant frequency
        f_star = dominant_freq[np.argmax(dominant_amplitude)]
        phase_angle = np.angle(fft_result[np.argmax(dominant_amplitude)])
        
        # Check for phase inversion condition
        if abs(phase_angle) > np.pi / 2:
            phase_inversions.append(i + window_size // 2)
        
        fft_results.append((f_star, phase_angle))
    
    return fft_results, phase_inversions

# Sample price data (replace with actual price data)
prices = np.random.rand(1000)  # Simulated price data

# Run the spectral phase inversion detection
fft_results, phase_inversions = spectral_phase_inversion(prices)

# Visualization
plt.figure(figsize=(14, 7))
plt.plot(prices, label='Price Data')
plt.title('Price Data with Spectral Phase Inversion Detection')
plt.xlabel('Time')
plt.ylabel('Price')
plt.axvline(x=phase_inversions[0], color='red', linestyle='--', label='Phase Inversion')
for inversion in phase_inversions:
    plt.axvline(x=inversion, color='red', linestyle='--')
plt.legend()
plt.show()
