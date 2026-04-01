// hidden_engine.rs – The Soul

// Implements a latent “magnet” field that pulls price toward an equilibrium
// via a gravitational‑like constant G. The force is proportional to the
// negative gradient of a quadratic potential.

// Public API
fn soul_force(ptr: &ndarray::Array1<f64>, eq: f64, G: f64) -> ndarray::Array1<f64> {
    // Compute the attractive force of the hidden engine.

    // The potential is Φ(x) = 0.5 * G * (x - eq)^2,
    // thus F = -∇Φ = -G * (x - eq).

    // Parameters
    // ----------
    // ptr : &ndarray::Array1<f64>
    //     Pointer values (output of :func:`explicit_component.body_signal`).
    // eq : f64
    //     Equilibrium price level the engine seeks.
    // G : f64
    //     Gravitational constant (strength of the hidden engine).

    // Returns
    // -------
    // ndarray::Array1<f64>
    //     Force array, same shape as `ptr`.
    return -G * (ptr - eq);
}
