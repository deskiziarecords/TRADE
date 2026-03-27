//! Efficient projection onto probability simplex
//! Duchi et al. algorithm: O(n log n) or O(n) with select

use nalgebra::DVector;

/// Project vector onto unit simplex: {w | w_i >= 0, sum w_i = 1}
pub fn project_simplex(v: &DVector<f64>) -> DVector<f64> {
    let n = v.len();
    
    // Sort descending
    let mut u: Vec<f64> = v.iter().copied().collect();
    u.sort_by(|a, b| b.partial_cmp(a).unwrap());
    
    // Find rho: largest index where u[i] + (1 - sum(u[0..i]))/(i+1) > 0
    let mut cumsum = 0.0;
    let mut rho = 0;
    
    for (i, &val) in u.iter().enumerate() {
        cumsum += val;
        let threshold = (cumsum - 1.0) / (i as f64 + 1.0);
        
        if val > threshold {
            rho = i + 1;
        } else {
            break;
        }
    }
    
    // Compute lambda
    let lambda = if rho > 0 {
        (u.iter().take(rho).sum::<f64>() - 1.0) / rho as f64
    } else {
        0.0
    };
    
    // Project
    DVector::from_iterator(n, v.iter().map(|&vi| (vi - lambda).max(0.0)))
}

/// Weighted simplex with entropy regularization
/// For diversification preference
pub fn project_simplex_entropy(v: &DVector<f64>, gamma: f64) -> DVector<f64> {
    // Softmax-like with temperature
    let max_v = v.max();
    let exp_v: Vec<f64> = v.iter().map(|&vi| ((vi - max_v) / gamma).exp()).collect();
    let sum_exp: f64 = exp_v.iter().sum();
    
    DVector::from_iterator(v.len(), exp_v.iter().map(|&e| e / sum_exp))
}
