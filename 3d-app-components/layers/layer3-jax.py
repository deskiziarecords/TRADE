import jax.numpy as jnp
import jax.scipy.fft as jfft
import matplotlib.pyplot as plt

# Function to compute FFT and detect phase inversion
def spectral_phase_inversion(prices, window_size=64):
    fft_results = []
    phase_inversions = []
    
    for i in range(len(prices) - window_size):
        window = prices[i:i + window_size]
        fft_result = jfft.fft(window)
        dominant_freq = jfft.fftfreq(len(window), d=1)[:len(window)//2]
        dominant_amplitude = jnp.abs(fft_result)[:len(window)//2]
        
        # Detect dominant frequency
        f_star = dominant_freq[jnp.argmax(dominant_amplitude)]
        phase_angle = jnp.angle(fft_result[jnp.argmax(dominant_amplitude)])
        
        # Check for phase inversion condition
        if abs(phase_angle) > jnp.pi / 2:
            phase_inversions.append(i + window_size // 2)
        
        fft_results.append((f_star, phase_angle))
    
    return fft_results, phase_inversions

# Sample price data (replace with actual price data)
prices = jnp.random.rand(1000)  # Simulated price data

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
