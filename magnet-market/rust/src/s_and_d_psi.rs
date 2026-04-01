// s_and_d_psi.rs – S&D ΨS&D​ : Heuristic Pattern Classifier (Garbage Collection)

// Interprets clusters of small‑size, high‑frequency trades as “unallocated RAM”
// that must be cleared. A simple density‑based heuristic flags regions where
// trade count per unit price exceeds a threshold.

// Public API----------
fn detect_liquidity_blobs(prices: &[f64],
                          volumes: &[f64],
                          price_bins: usize,
                          vol_threshold: f64) -> Vec<bool> {
    // Identify price bins where accumulated volume per bin exceeds `vol_threshold`
    // times the median volume per bin – interpreted as retail liquidity pools.

    // Parameters
    // ----------
    // prices : &[f64]
    //     Trade prices.
    // volumes : &[f64]
    //     Corresponding trade sizes.
    // price_bins : usize    Number of bins to discretize the price axis.
    // vol_threshold : f64
    //     Multiplicative factor over median volume to flag a blob.

    // Returns
    // -------
    // Vec<bool>        Boolean array same length as `prices`; true => garbage to be collected.

    // Bin prices
    let bin_idx: Vec<usize> = prices.iter()
        .map(|&price| {
            let bin = ((price - prices.iter().cloned().fold(f64::INFINITY, f64::min)) /
                        (prices.iter().cloned().fold(f64::NEG_INFINITY, f64::max) -
                         prices.iter().cloned().fold(f64::INFINITY, f64::min)) * price_bins as f64).round() as usize;
            bin.clamp(0, price_bins - 1)
        })
        .collect();

    // Sum volume per bin
    let mut bin_vol = vec![0.0; price_bins];
    for (i, &volume) in volumes.iter().enumerate() {
        bin_vol[bin_idx[i]] += volume;
    }

    let median_vol = {
        let mut non_zero_vol: Vec<f64> = bin_vol.iter().filter(|&&v| v > 0.0).cloned().collect();
        non_zero_vol.sort_by(|a, b| a.partial_cmp(b).unwrap());
        if !non_zero_vol.is_empty() {
            let mid = non_zero_vol.len() / 2;
            if non_zero_vol.len() % 2 == 0 {
                (non_zero_vol[mid - 1] + non_zero_vol[mid]) / 2.0
            } else {
                non_zero_vol[mid]
            }
        } else {
            0.0
        }
    };

    let threshold = median_vol * vol_threshold;

    // Map back to each trade
    bin_idx.iter().map(|&idx| bin_vol[idx] > threshold).collect()
}
