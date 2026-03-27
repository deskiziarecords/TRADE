// Cargo.toml
// ------------------------------------------------------------
// [package]
// name = "schur_routing"
// version = "0.1.0"
// edition = "2021"
//
// [dependencies]
// nalgebra = "0.32"
// rand = "0.8"
// ------------------------------------------------------------

use nalgebra::{DMatrix, DVector, Scalar, RealField, Norm, eigen};
use std::f64;

/// Venue‑specific liquidity parameters.
#[derive(Debug, Clone)]
struct Venue {
    /// γᵢ – liquidity coefficient (higher ⇒ more liquid)
    gamma: f64,
    /// δᵢ ∈ [1,2] – convexity of slippage
    delta: f64,
}

/// Slippage at venue i for a notional q.
fn slippage(venue: &Venue, q: f64) -> f64 {
    // sᵢ(q) = γᵢ · q^{δᵢ}
    venue.gamma * q.powf(venue.delta)
}

/// Build the instantaneous cost matrix C ∈ ℝ^{m×m}
///   C_{ij} = s_i(Q·w_i) + s_j(Q·w_j) + ρ_{ij}·Q
/// where ρ_{ij} = exp(-λ_dist · d_{ij})
fn build_cost_matrix(
    Q: f64,
    w: &DVector<f64>,
    venues: &[Venue],
    dist: &DMatrix<f64>, // m×m matrix of "distances"
    lambda_dist: f64,
) -> DMatrix<f64> {
    let m = venues.len();
    let mut C = DMatrix::zeros(m, m);

    // pre‑compute slippage terms s_i(Q·w_i)
    let s: Vec<f64> = venues
        .iter()
        .zip(w.iter())
        .map(|(v, wi)| slippage(v, Q * wi))
        .collect();

    for i in 0..m {
        for j in 0..m {
            let rho = (-lambda_dist * dist[(i, j)]).exp();
            C[(i, j)] = s[i] + s[j] + rho * Q;
        }
    }
    C
}

/// Symmetrize and add a tiny diagonal for numerical stability.
///   C̃ = 2C + Cᵀ + εI   (ε = 1e-6)
fn symmetrize(C: &DMatrix<f64>) -> DMatrix<f64> {
    let eps = 1e-6;
    let m = C.nrows();
    let mut Ct = C.transpose();
    let mut Ctilde = C * 2.0 + &Ct;
    for i in 0..m {
        Ctilde[(i, i)] += eps;
    }
    Ctilde
}

/// Project a vector onto the probability simplex Δ^{m-1}
///   w = max(v - τ·1, 0)   with τ chosen s.t. Σ w_i = 1
/// Implementation follows the O(m log m) algorithm of Duchi et al. (2008).
fn simplex_projection(v: &DVector<f64>) -> DVector<f64> {
    let mut u = v.clone();
    u.as_mut_slice().sort_by(|a, b| b.partial_cmp(a).unwrap()); // descending

    let mut cssv = 0.0;
    let mut rho = 0usize;
    for (i, &val) in u.iter().enumerate() {
        cssv += val;
        let t = (cssv - 1.0) / (i as f64 + 1.0);
        if val > t {
            rho = i + 1;
        }
    }

    let tau = (u.iter().take(rho).sum::<f64>() - 1.0) / rho as f64;
    v.map(|x| if x - tau > 0.0 { x - tau } else { 0.0 })
}

/// Very simple Adelic‑tube indicator.
/// For demonstration we only require that the product over the first few primes
/// of |w_i * λ_i|_p be < |ρ|_p (here we replace the p‑adic norm by a
/// ordinary absolute value and a small threshold).  Returns 1 if the condition
/// holds for every venue, otherwise 0.
fn adelic_tube_indicator(
    w: &DVector<f64>,
    lambdas: &DVector<f64>,
    rho_mat: &DMatrix<f64>,
) -> f64 {
    let primes = [2u64, 3, 5, 7, 11];
    let m = w.len();
    for i in 0..m {
        let prod: f64 = primes
            .iter()
            .map(|&p| (w[i] * lambdas[i]).abs().powf(1.0 / p as f64))
            .product();
        // Use the average off‑diagonal ρ as a proxy for |ρ|_p
        let rho_avg = (rho_mat.sum() - rho_mat.trace()) / ((m * (m - 1)) as f64);
        if prod >= rho_avg {
            return 0.0; // violates the tube constraint        }
    }
    1.0}

/// Compute a placeholder ATR‑10 (average true range over the last 10 periods).
/// In a real system this would be fed from market data.
fn atr10(_: f64) -> f64 {
    // dummy constant – replace with actual ATR calculation
    0.02
}

/// Dynamic blow‑up threshold: λ_blow‑up = ATR10 · κ_schur
fn blowup_threshold(atr10: f64, kappa_schur: f64) -> f64 {
    atr10 * kappa_schur
}

/// Main Schur‑routing step.
/// Returns the optimal weight vector w* (simplex‑constrained).
fn schur_routing(
    Q: f64,
    w_prev: &DVector<f64>,
    venues: &[Venue],
    dist: &DMatrix<f64>,
    lambda_dist: f64,
    kappa_schur: f64,
) -> DVector<f64> {
    // 1️⃣ Build instantaneous cost matrix using the previous weights
    let C = build_cost_matrix(Q, w_prev, venues, dist, lambda_dist);

    // 2️⃣ Symmetrize & regularise
    let Ctilde = symmetrize(&C);

    // 3️⃣ Eigen (Schur) decomposition of the symmetric matrix
    //    Ctilde = Q · Λ · Qᵀ  → eigenvalues on diag(Λ), eigenvectors in Q
    let eigen = eigen::Eigen::new(Ctilde.clone(), false, true).unwrap();
    let lambdas = eigen.eigenvalues; // real because Ctilde is symmetric    let Qmat = eigen.eigenvectors;   // orthogonal matrix

    // 4️⃣ Pick eigenvector belonging to the smallest eigenvalue
    let k_star = lambdas        .iter()
        .enumerate()
        .min_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap())
        .map(|(idx, _)| idx)
        .unwrap();
    let v_opt = Qmat.column(k_star); // already unit‑length

    // 5️⃣ Project onto simplex → feasible weights
    let w_hat = simplex_projection(&v_opt);

    // 6️⃣ Adelic‑tube indicator (uses current λ and a rough ρ matrix)
    //    ρ_{ij} = exp(-λ_dist·d_{ij})
    let mut rho_mat = DMatrix::zeros(venues.len(), venues.len());
    for i in 0..venues.len() {
        for j in 0..venues.len() {
            rho_mat[(i, j)] = (-lambda_dist * dist[(i, j)]).exp();
        }
    }
    let adelic_ind = adelic_tube_indicator(&w_hat, &lambdas, &rho_mat);

    // 7️⃣ Blow‑up filter using ATR‑10 threshold
    let lambda_min = lambdas.iter().cloned().fold(f64::INFINITY, |a, b| a.min(b));
    let lambda_blow_up = blowup_threshold(atr10(Q), kappa_schur);
    let blowup_ind = if lambda_min < lambda_blow_up { 1.0 } else { 0.0 };

    // 8️⃣ Final weight (the adelic term and blow‑up term are scalars)
    let w_star = w_hat * adelic_ind * blowup_ind;

    // If the indicator killed the solution, fall back to uniform routing
    if w_star.sum() < 1e-12 {
        let uniform = DVector::from_element(venues.len(), 1.0 / venues.len() as f64);
        return uniform;
    }
    w_star
}

/// ---------------------------------------------------------------------------
/// Example usage (demo)
/// ---------------------------------------------------------------------------
fn main() {
    // ----- Parameters -------------------------------------------------------
    let Q_t = 1_000_000.0; // position size to execute (e.g., USD notional)
    let m = 3;             // number of venues    // Venue liquidity specs (γᵢ, δᵢ)
    let venues = vec![
        Venue { gamma: 0.1, delta: 1.5 },
        Venue { gamma: 0.08, delta: 1.6 },
        Venue { gamma: 0.12, delta: 1.4 },
    ];

    // Distance matrix (latency / correlation / shared flow) – lower = closer
    let dist = DMatrix::from_vec(
        m,
        m,
        vec![
            0.0, 0.3, 0.5,
            0.3, 0.0, 0.2,
            0.5, 0.2, 0.0,
        ],
    );
    let lambda_dist = 2.0; // decay rate for correlated impact

    // Schur‑specific constant
    let kappa_schur = 0.5;

    // Start from an uniform guess
    let mut w = DVector::from_element(m, 1.0 / m as f64);

    // Run a few iterations to let the cost matrix adapt to the new weights
    for iter in 0..5 {
        w = schur_routing(Q_t, &w, &venues, &dist, lambda_dist, kappa_schur);
        println!(
            "Iteration {}: w = [{:.6}, {:.6}, {:.6}] (sum = {:.6})",
            iter,
            w[0],
            w[1],
            w[2],
            w.sum()
        );
    }

    // Final weights can now be fed to an execution engine.
    println!("\nFinal routing weights: {:?}", w);
}
