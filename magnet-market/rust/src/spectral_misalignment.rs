// spectral_misalignment.rs – M : Fourier Phase Analysis

// Computes the phase spectrum of a signal and flags bins where the phase
// deviates sharply from a locally smoothed version – analogous to hearing a
// “knock” before a piston breaks.

// Public API
// ----------
// fn spectral_misalignment(signal: &Vec<f64>,
//                           fs: f64,
//                           smoothing_window: usize,
//                           threshold: f64) -> Vec<bool> {
//     Returns boolean mask where phase misalignment exceeds threshold.
// }

use ndarray::Array1;
use ndarray::ArrayView1;
use ndarray::Axis;
use std::f64::consts::PI;

fn spectral_misalignment(signal: &Vec<f64>,
                         fs: f64,
                         smoothing_window: usize,
                         threshold: f64) -> Vec<bool> {
    // Detect spectral phase misalignment.

    // Parameters
    // ----------
    // signal : Vec<f64>
    //     Real‑valued time series (e.g., price returns).
    // fs : f64        Sampling frequency (Hz). Default 1.0 assumes unit spacing.
    // smoothing_window : usize        Length of moving average applied to unwrapped phase for baseline.
    // threshold : f64
    //     Absolute radian deviation above which a bin is flagged.

    // Returns
    // -------
    // Vec<bool>
    //     Boolean mask same length as `signal` (true => misaligned).

    // Compute FFT
    let n = signal.len();
    let freq = (0..n).map(|k| k as f64 / fs).collect::<Vec<f64>>();
    let fft_vals = rustfft::FFTplanner::new(false).plan_fft(n).process(signal);
    let phase: Vec<f64> = fft_vals.iter().map(|c| c.arg()).collect();

    // Unwrap to avoid 2π jumps
    let phase_unwrapped = unwrap_phase(&phase);

    // Smooth the unwrapped phase (simple moving average)
    let smoothed = if smoothing_window < 3 {
        phase_unwrapped.clone()
    } else {
        let kernel = vec![1.0 / smoothing_window as f64; smoothing_window];
        convolve(&phase_unwrapped, &kernel)
    };

    // Deviation
    let deviation: Vec<f64> = phase_unwrapped.iter()
        .zip(smoothed.iter())
        .map(|(u, s)| (u - s).abs())
        .collect();

    // Map back to time domain via inverse FFT of a mask:
    // For simplicity, we just upsample the boolean mask using linear interp.
    // In practice, you’d apply an IFFT to a masked spectrum; here we approximate.
    let rep_factor = (n as f64 / deviation.len() as f64).ceil() as usize;
    let mask_freq: Vec<bool> = deviation.iter().map(|&d| d > threshold).collect();
    let mut mask_time = Vec::with_capacity(n);
    for &flag in &mask_freq {
        for _ in 0..rep_factor {
            mask_time.push(flag);
        }
    }
    mask_time.truncate(n);
    mask_time
}

// Helper functions would be defined here (unwrap_phase, convolve, etc.)
