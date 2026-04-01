// utils/decay_matrix.rs
// Implements the Time-Decayed Memory Matrix for IPDA (Institutional Price Discovery Addresses).
// Computes rolling exponential-weighted price references over configurable windows.

// Core Formula:
// $$
// \text{IPDA}_k(t) = \sum_{i=t-L_k}^{t} P_i \cdot e^{-\lambda(t-i)}
// $$

use ndarray::{Array1, Array2, ArrayView1, Axis};
use ndarray::s;
use std::f64;

fn compute_decay_matrix(
    prices: &Array1<f64>,
    windows: Vec<usize>,
    decay_rate: f64,
) -> Array2<f64> {
    let n = prices.len();
    let k = windows.len();
    let mut result = Array2::<f64>::zeros((n, k));

    for (i, &l) in windows.iter().enumerate() {
        if l > n {
            continue;
        }

        // Weight vector: [exp(-lambda*(L-1)), ..., exp(0)]
        let weights: Array1<f64> = Array1::from_iter((0..l).rev().map(|x| (-decay_rate * x as f64).exp()));

        // Create overlapping windows
        let windows_view = prices.windows(l);

        // Vectorized dot product: each row dotted with decay weights
        for (j, window) in windows_view.enumerate() {
            result[(j + l - 1, i)] = window.dot(&weights);
        }
    }
    result
}

fn compute_ipda_extremums(
    ipda_matrix: &Array2<f64>,
    method: &str,
) -> Array2<f64> {
    let valid_rows = ipda_matrix.axis_iter(Axis(0)).map(|row| !row.iter().any(|&x| x.is_nan())).collect::<Vec<_>>();
    let supports = valid_rows.iter().enumerate().map(|(i, &valid)| {
        if valid {
            ipda_matrix.slice(s![i, 1..]).iter().cloned().fold(f64::INFINITY, f64::min)
        } else {
            f64::NAN
        }
    }).collect::<Array1<f64>>();

    let resistances = valid_rows.iter().enumerate().map(|(i, &valid)| {
        if valid {
            ipda_matrix.slice(s![i, 1..]).iter().cloned().fold(f64::NEG_INFINITY, f64::max)
        } else {
            f64::NAN
        }
    }).collect::<Array1<f64>>();

    Array2::from_shape_vec((supports.len(), 2), supports.iter().chain(resistances.iter()).cloned().collect()).unwrap()
}
