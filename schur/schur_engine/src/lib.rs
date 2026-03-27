//! Schur Engine: Sub-microsecond routing optimization
//! 
//! Usage:
//! ```rust
//! use schur_engine::{SchurRouter, RoutingParams, Venue};
//! 
//! let venues = vec![
//!     Venue { id: 0, liquidity: 0.1, latency_ms: 20, fees: 0.0001 },
//!     Venue { id: 1, liquidity: 0.05, latency_ms: 50, fees: 0.0002 },
//!     Venue { id: 2, liquidity: 0.08, latency_ms: 15, fees: 0.00015 },
//! ];
//! 
//! let params = RoutingParams {
//!     slippage_gamma: vec![0.1, 0.05, 0.08],
//!     slippage_delta: vec![1.5, 1.5, 1.5],
//!     correlation_decay: 0.01,
//!     adelic_alpha: 1.5,
//!     adelic_rho: 3.5,
//!     adelic_max_nonzero: 3,
//!     blowup_kappa: 3.0,
//! };
//! 
//! let mut router = SchurRouter::new(venues, params);
//! 
//! let result = router.optimize(
//!     q_total: 52100.0,
//!     ofi_matrix: &ofi_data,
//!     prev_weights: &prev_w,
//! );
//! 
//! println!("Weights: {:?}", result.weights);
//! println!("Expected cost: {}", result.cost_estimate);
//! ```

pub mod schur;
pub mod adelic;
pub mod simplex;
pub mod io_uring;

use nalgebra::{DMatrix, DVector};
use std::time::Instant;

/// Venue characteristics
#[derive(Debug, Clone, Copy)]
pub struct Venue {
    pub id: u32,
    pub liquidity: f64,      // γ: slippage coefficient
    pub latency_ms: f64,     // For distance calculation
    pub fees: f64,           // Fixed cost component
}

/// Routing parameters
#[derive(Debug, Clone)]
pub struct RoutingParams {
    pub slippage_gamma: Vec<f64>,
    pub slippage_delta: Vec<f64>,      // Convexity, typically 1.5
    pub correlation_decay: f64,         // λ_dist
    pub adelic_alpha: f64,             // α for |λ^α|
    pub adelic_rho: f64,               // ρ_limit
    pub adelic_max_nonzero: usize,      // Max nonzero p-adic vals
    pub blowup_kappa: f64,             // ATR multiplier for blow-up
}

/// Optimization result
#[derive(Debug)]
pub struct RoutingResult {
    pub weights: Vec<f64>,
    pub quantities: Vec<f64>,
    pub eigenvalues: Vec<f64>,
    pub lambda_min: f64,
    pub adelic_valid: bool,
    pub blowup_detected: bool,
    pub cost_estimate: f64,
    pub execution_entropy: f64,
    pub concentration: f64,            // max(w_i)
    pub elapsed_us: f64,               // Optimization time
}

/// Main router struct
pub struct SchurRouter {
    venues: Vec<Venue>,
    params: RoutingParams,
    n: usize,
}

impl SchurRouter {
    pub fn new(venues: Vec<Venue>, params: RoutingParams) -> Self {
        let n = venues.len();
        assert_eq!(params.slippage_gamma.len(), n);
        assert_eq!(params.slippage_delta.len(), n);
        
        Self { venues, params, n }
    }
    
    /// Core optimization: Schur + Adelic + Simplex
    pub fn optimize(
        &self,
        q_total: f64,
        ofi_matrix: &DMatrix<f64>,
        prev_weights: &DVector<f64>,
    ) -> RoutingResult {
        let start = Instant::now();
        
        // 1. Build cost matrix
        let c = self.build_cost_matrix(q_total, ofi_matrix, prev_weights);
        
        // 2. Schur decomposition (symmetric: eigen-decomposition)
        let schur = schur::schur_symmetric(&c);
        
        // 3. Adelic validation
        let eigenvals: Vec<f64> = schur.eigenvalues.iter().copied().collect();
        let adelic_checks = adelic::adelic_spectrum_check(
            &eigenvals,
            self.params.adelic_alpha,
            self.params.adelic_rho,
            self.params.adelic_max_nonzero,
        );
        
        let adelic_valid = adelic_checks.iter().all(|&x| x);
        
        // 4. Blow-up detection
        let atr_proxy = self.venues.iter().map(|v| v.fees).sum::<f64>() / self.n as f64;
        let blowup_threshold = atr_proxy * self.params.blowup_kappa;
        let blowup_detected = schur.eigenvalues[0] > blowup_threshold; // λ_max > threshold
        
        // 5. Select minimum eigenvalue direction (stablest)
        let k_star = if adelic_valid && !blowup_detected {
            // Find minimum valid eigenvalue
            eigenvals.iter()
                .enumerate()
                .filter(|(i, _)| adelic_checks[*i])
                .min_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap())
                .map(|(i, _)| i)
                .unwrap_or(0)
        } else {
            0 // Fallback to first
        };
        
        let lambda_min = eigenvals[k_star];
        
        // 6. Extract eigenvector and project to simplex
        let v_opt = schur.eigenvectors.column(k_star).into_owned();
        let w_raw = simplex::project_simplex(&v_opt);
        
        // 7. Apply constraints and renormalize
        let valid = adelic_valid && !blowup_detected && lambda_min < 0.0;
        
        let weights: Vec<f64> = if valid {
            w_raw.iter().copied().collect()
        } else {
            // Revert to previous or uniform
            prev_weights.iter().copied().collect()
        };
        
        // Renormalize
        let w_sum: f64 = weights.iter().sum();
        let weights: Vec<f64> = weights.iter().map(|&w| w / w_sum).collect();
        
        let quantities: Vec<f64> = weights.iter().map(|&w| w * q_total).collect();
        
        // 8. Diagnostics
        let w_vec = DVector::from_vec(weights.clone());
        let cost_estimate = (&w_vec).dot(&(&c * &w_vec));
        let entropy = -weights.iter().map(|&w| {
            if w > 0.0 { w * w.ln() } else { 0.0 }
        }).sum::<f64>();
        let concentration = *weights.iter().max_by(|a, b| a.partial_cmp(b).unwrap()).unwrap();
        
        let elapsed = start.elapsed().as_secs_f64() * 1e6; // microseconds
        
        RoutingResult {
            weights,
            quantities,
            eigenvalues: eigenvals,
            lambda_min,
            adelic_valid,
            blowup_detected,
            cost_estimate,
            execution_entropy: entropy,
            concentration,
            elapsed_us: elapsed,
        }
    }
    
    fn build_cost_matrix(
        &self,
        q_total: f64,
        ofi_matrix: &DMatrix<f64>,
        prev_weights: &DVector<f64>,
    ) -> DMatrix<f64> {
        let n = self.n;
        let mut c = DMatrix::zeros(n, n);
        
        // Diagonal: slippage
        for i in 0..n {
            let q_i = q_total * prev_weights[i];
            let s_i = self.params.slippage_gamma[i] 
                * q_i.powf(self.params.slippage_delta[i]);
            c[(i, i)] = s_i;
        }
        
        // Off-diagonal: correlated impact
        for i in 0..n {
            for j in (i+1)..n {
                let d_ij = (self.venues[i].latency_ms - self.venues[j].latency_ms).abs();
                let rho_ij = (-self.params.correlation_decay * d_ij).exp();
                
                let c_ij = rho_ij * ofi_matrix[(i, j)] * q_total;
                c[(i, j)] = c_ij;
                c[(j, i)] = c_ij; // Symmetric
            }
        }
        
        c
    }
}
