// utils/fourier_ops.rs
// Implements Spectral Misalignment $M$ via Fourier Phase Analysis.
// Detects desynchronization between price momentum and volume participation.

// Core Formula:
// $$
// M(\omega) = \left| \angle \mathcal{F}\{V(t)\} - \angle \mathcal{F}\{P(t)\} \right|
// $$

use ndarray::{Array1, ArrayView1};
use ndarray::prelude::*;
use rustfft::{FftPlanner, num_complex::Complex};
use std::f64::consts::PI;

fn circular_diff(phi_a: &ArrayView1<f64>, phi_b: &ArrayView1<f64>) -> Array1<f64> {
    // Computes robust circular phase difference handling $(-\pi, \pi]$ wrap-around.
    let diff = phi_a - phi_b;
    diff.mapv(|x| (x + PI) % (2.0 * PI) - PI).abs()
}

fn compute_spectral_misalignment(
    prices: &ArrayView1<f64>,
    volume: &ArrayView1<f64>,
    fft_window: usize,
    overlap: f64,
    freq_band: (f64, f64),
    fs: f64,
) -> Array1<f64> {
    // Computes rolling spectral misalignment between price and volume.

    assert_eq!(prices.len(), volume.len(), "Price and volume arrays must match in length.");

    // Z-score normalization for stationary FFT input
    let p_mean = prices.mean().unwrap();
    let p_std = prices.std(0.0);
    let p_norm = (prices - p_mean) / (p_std + 1e-9);

    let v_mean = volume.mean().unwrap();
    let v_std = volume.std(0.0);
    let v_norm = (volume - v_mean) / (v_std + 1e-9);

    let step = (fft_window as f64 * (1.0 - overlap)).max(1.0).round() as usize;
    let mut segment_m = Vec::new();
    let mut segment_centers = Vec::new();

    let mut planner = FftPlanner::new();
    let fft = planner.plan_fft_forward(fft_window);
    let mut p_fft = vec![Complex::new(0.0, 0.0); fft_window];
    let mut v_fft = vec![Complex::new(0.0, 0.0); fft_window];

    let freqs: Vec<f64> = (0..fft_window)
        .map(|i| i as f64 * fs / fft_window as f64)
        .collect();

    // Frequency band mask (positive frequencies only, skip DC)
    let mask: Vec<bool> = freqs.iter()
        .map(|&f| f >= freq_band.0 && f <= freq_band.1)
        .collect();
    let half = fft_window / 2;
    let valid_freqs: Vec<bool> = mask[1..half].to_vec();

    for start in (0..prices.len() - fft_window + 1).step_by(step) {
        let p_seg = p_norm.slice(s![start..start + fft_window]);
        let v_seg = v_norm.slice(s![start..start + fft_window]);

        // FFT & Phase Extraction
        p_fft.iter_mut().zip(p_seg.iter()).for_each(|(fft_val, &seg_val)| {
            *fft_val = Complex::new(seg_val, 0.0);
        });
        fft.process(&mut p_fft);

        v_fft.iter_mut().zip(v_seg.iter()).for_each(|(fft_val, &seg_val)| {
            *fft_val = Complex::new(seg_val, 0.0);
        });
        fft.process(&mut v_fft);

        let phase_p: Array1<f64> = Array1::from_vec(p_fft.iter().map(|c| c.arg()).collect());
        let phase_v: Array1<f64> = Array1::from_vec(v_fft.iter().map(|c| c.arg()).collect());

        // Circular phase difference in target band
        let diff = circular_diff(&phase_p, &phase_v);
        let M_val = diff.iter()
            .enumerate()
            .filter(|(i, _)| valid_freqs[*i])
            .map(|(_, &val)| val)
            .sum::<f64>() / valid_freqs.iter().filter(|&&x| x).count() as f64;

        segment_m.push(M_val);
        segment_centers.push(start + fft_window / 2);
    }

    // Interpolate to original timeline for pipeline alignment
    if segment_m.len() < 2 {
        return Array1::from_elem(prices.len(), f64::NAN);
    }

    let mut result = Array1::zeros(prices.len());
    for (i, &center) in segment_centers.iter().enumerate() {
        result[center] = segment_m[i];
    }

    // Linear interpolation
    for i in 1..result.len() {
        if result[i].is_nan() {
            result[i] = result[i - 1];
        }
    }

    result
}
