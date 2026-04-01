// utils/math_helpers.rs – Small reusable math utilities.

// Contains helpers for norms, exponential decay, and fast FFT wrappers.

use ndarray::Array1;

pub fn l2_norm(x: &Array1<f64>) -> f64 {
    x.norm_l2()
}

pub fn exponential_decay(t: &Array1<f64>, lam: f64) -> Array1<f64> {
    // Return exp(-λ·t) element‑wise.
    t.mapv(|val| (-lam * val).exp())
}

pub fn next_pow2(x: usize) -> usize {
    // Return the smallest power of two >= x.
    1 << (x - 1).next_power_of_two().trailing_zeros()
}
