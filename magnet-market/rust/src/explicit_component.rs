// explicit_component.rs – The Body

// Treats the raw price series as a pointer into a time‑decayed memory address space.
// Each price point is considered a “memory cell” whose relevance decays exponentially
// with age: weight(t) = exp(-λ·age).

// Public API
// ----------

fn body_signal(prices: &[f64], lam: f64) -> Vec<f64> {
//     Compute a decay‑weighted pointer to the price series.

//     Parameters
//     ----------
//     prices : &[f64]
//         1‑D array of mid‑prices (or any observable).
//     lam : f64
//         Decay rate (λ). Larger λ → faster forgetting.

//     Returns
//     -------
//     Vec<f64>
//         Same shape as `prices`; each entry = price * exp(-λ·age).
    let age: Vec<usize> = (0..prices.len()).rev().collect(); // newest = 0 age
    let weights: Vec<f64> = age.iter().map(|&a| (-lam * a as f64).exp()).collect();
    prices.iter().zip(weights.iter()).map(|(&price, &weight)| price * weight).collect()
}
