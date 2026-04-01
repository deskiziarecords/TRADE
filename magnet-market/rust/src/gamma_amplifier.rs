// gamma_amplifier.rs – Γ : Second‑Order Feedback Loop

// Amplifies the curvature (second derivative) of the potential.
// If we treat the potential as Φ(x), the “gamma” term is γ * Φ''(x).
// For a quadratic Φ, Φ'' = k (constant), so gamma simply scales the stiffness.

// Public API
// ----------

fn gamma_stiffness(k: f64, gamma: f64) -> f64 {
    // Amplify the quadratic stiffness via a second‑order feedback factor.

    // Parameters
    // ----------
    // k : f64
    //     Base stiffness (from potential function).
    // gamma : f64
    //     Feedback gain; gamma=0 recovers the original stiffness.

    // Returns
    // -------
    // f64
    //     Effective stiffness after amplification.
    
    k * (1.0 + gamma)
}
