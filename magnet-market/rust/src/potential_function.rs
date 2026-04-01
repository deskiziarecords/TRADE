// potential_function.rs – Φmag​ : Euclidean Vector Attraction

// Defines a quadratic potential Φ(x) = 0.5 * k * ||x - x0||^2.
// The force (negative gradient) is F = -k * (x - x0).

pub fn potential(x: &Vec<f64>, x0: f64, k: f64) -> f64 {
    // Quadratic potential centered at x0 with stiffness k.
    let sum: f64 = x.iter().map(|&xi| (xi - x0).powi(2)).sum();
    0.5 * k * sum
}

pub fn force(x: &Vec<f64>, x0: f64, k: f64) -> Vec<f64> {
    // Negative gradient of the potential → Hooke‑law style attraction.
    x.iter().map(|&xi| -k * (xi - x0)).collect()
}
