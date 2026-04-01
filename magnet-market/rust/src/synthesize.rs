// synthesize.rs – The “Synthesized” Reality

// Fuses explicit body signals with hidden engine forces to produce a
// tradeable forecast. Simple formulation: forecast = ptr + α·force,
// where α is a tuning gain.

pub fn synthesize(ptr: &Vec<f64>, force: &Vec<f64>, alpha: f64) -> Vec<f64> {
    // Combine body pointer and hidden engine force.

    // Parameters
    // ----------
    // ptr : &Vec<f64>
    //     Output from explicit component.
    // force : &Vec<f64>
    //     Output from hidden engine.
    // alpha : f64
    //     Gain that scales the force contribution.

    // Returns
    // -------
    // Vec<f64>
    //     Synthesized reality signal.

    ptr.iter()
        .zip(force.iter())
        .map(|(p, f)| p + alpha * f)
        .collect()
}
