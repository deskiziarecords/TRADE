// ipda_l20_40_60.rs – IPDA L20,40,60​
//
// Implied Probability Distribution Approximation at the 20th, 40th and 60th
// percentiles. Uses a simple histogram‑based CDF estimate; suitable for
// high‑frequency streaming where a full KDE would be too costly.
//
// Public API
// ----------
// fn ipda_quantiles(values: &[f64], bins: usize) -> (f64, f64, f64) {
//     Returns (q20, q40, q60).
// }

fn ipda_quantiles(values: &[f64], bins: usize) -> (f64, f64, f64) {
    // Approximate the 20%, 40% and 60% quantiles of `values`.

    // Parameters
    // ----------
    // values : &[f64]
    //     Sample of returns, prices, or any metric.
    // bins : usize
    //     Number of histogram bins (controls resolution).

    // Returns
    // -------
    // (f64, f64, f64)
    //     (q20, q40, q60) as floats.

    let mut hist = vec![0.0; bins];
    let min_value = *values.iter().min_by(|a, b| a.partial_cmp(b).unwrap()).unwrap();
    let max_value = *values.iter().max_by(|a, b| a.partial_cmp(b).unwrap()).unwrap();
    let bin_width = (max_value - min_value) / bins as f64;

    // Create histogram
    for &value in values {
        let bin_index = ((value - min_value) / bin_width).floor() as usize;
        if bin_index < bins {
            hist[bin_index] += 1.0;
        }
    }

    // Normalize histogram to get density
    let total_count = values.len() as f64;
    for h in &mut hist {
        *h /= total_count;
    }

    // Calculate CDF
    let mut cdf = vec![0.0; bins];
    cdf[0] = hist[0];
    for i in 1..bins {
        cdf[i] = cdf[i - 1] + hist[i];
    }

    // Find quantiles
    let quantile = |target: f64| {
        let idx = cdf.iter().position(|&x| x >= target).unwrap();
        let lo = min_value + (bin_width * idx as f64);
        let hi = min_value + (bin_width * (idx + 1) as f64);
        let cdf_lo = if idx > 0 { cdf[idx - 1] } else { 0.0 };
        let cdf_hi = cdf[idx];
        lo + (hi - lo) * (target - cdf_lo) / (cdf_hi - cdf_lo)
    };

    (quantile(0.20), quantile(0.40), quantile(0.60))
}
