// windowed_extremum_search.rs – Windowed Extremum Search

// Price is treated as a pointer into a time‑decayed memory address space.
// We slide a window of length `w` and record the max (or min) pointer value
// within that window – analogous to fetching the most “recently used”
// address.

/// Public API
/// Returns sliding-window max or min.
fn windowed_extremum(ptr: &Vec<f64>, window: usize, mode: &str) -> Vec<f64> {
    // Compute sliding window extremum.

    // Parameters
    // ----------
    // ptr : &Vec<f64>        Pointer series (e.g., output of explicit component).
    // window : usize
    //     Length of the sliding window (must be >=1).
    // mode : {"max", "min"}
    //     Which extremum to return.

    // Returns
    // -------
    // Vec<f64>
    //     Same shape as `ptr`; first `window-1` entries are NaN.

    if window < 1 {
        panic!("window must be >= 1");
    }
    if mode != "max" && mode != "min" {
        panic!("mode must be 'max' or 'min'");
    }

    // Use a sliding window approach
    let mut result = vec![f64::NAN; ptr.len()]; // Initialize result with NaN
    for i in 0..(ptr.len() - window + 1) {
        let window_slice = &ptr[i..(i + window)];
        result[i + window - 1] = if mode == "max" {
            *window_slice.iter().max_by(|a, b| a.partial_cmp(b).unwrap()).unwrap()
        } else {
            *window_slice.iter().min_by(|a, b| a.partial_cmp(b).unwrap()).unwrap()
        };
    }
    result
}
