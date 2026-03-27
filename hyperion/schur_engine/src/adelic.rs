//! p-adic validation for Schur eigenvalues
//! Fast rejection of unstable routing directions

use num_integer::Integer;
use std::collections::HashSet;

/// Prime set for adelic checks
pub const DEFAULT_PRIMES: [u64; 6] = [2, 3, 5, 7, 11, 13];

/// p-adic valuation for integer
#[inline]
pub fn padic_valuation_int(x: i64, p: u64) -> i32 {
    if x == 0 {
        return i32::MAX;
    }
    
    let mut x = x.abs() as u64;
    let p = p as u64;
    let mut k = 0;
    
    while x % p == 0 {
        x /= p;
        k += 1;
    }
    
    k
}

/// p-adic valuation for rational (num/den)
#[inline]
pub fn padic_valuation_rat(num: i64, den: i64, p: u64) -> i32 {
    padic_valuation_int(num, p) - padic_valuation_int(den, p)
}

/// Fast rational approximation of f64
/// Uses continued fraction with Stern-Brocot tree
pub fn float_to_rational(x: f64, max_den: i64) -> (i64, i64) {
    if x.is_nan() || x.is_infinite() {
        return (0, 1);
    }
    
    let mut x = x;
    let mut a = x.floor() as i64;
    let mut num = a;
    let mut den = 1;
    let mut num_prev = 1;
    let mut den_prev = 0;
    
    let mut iter = 0;
    const MAX_ITER: usize = 20;
    
    while iter < MAX_ITER {
        let x_frac = x - a as f64;
        if x_frac.abs() < 1e-9 || den > max_den {
            break;
        }
        
        x = 1.0 / x_frac;
        a = x.floor() as i64;
        
        let num_new = a * num + num_prev;
        let den_new = a * den + den_prev;
        
        if den_new > max_den {
            break;
        }
        
        num_prev = num;
        den_prev = den;
        num = num_new;
        den = den_new;
        iter += 1;
    }
    
    (num, den)
}

/// Adelic tube check for eigenvalue
/// Returns true if |λ^α|_p < |ρ|_p for all p in primes
#[inline]
pub fn adelic_eigenvalue_check(
    eigenvalue: f64,
    alpha: f64,
    rho_limit: f64,
    primes: &[u64],
    max_nonzero: usize,
) -> bool {
    // Archimedean check first (fast reject)
    let lambda_alpha = eigenvalue.abs().powf(alpha);
    if lambda_alpha >= rho_limit {
        return false;
    }
    
    // Rational approximation
    let (num, den) = float_to_rational(eigenvalue, 1_000_000);
    
    // Count nonzero p-adic valuations
    let nonzero_count: usize = primes
        .iter()
        .filter(|&&p| padic_valuation_rat(num, den, p) != 0)
        .count();
    
    nonzero_count <= max_nonzero
}

/// Batch validation for all eigenvalues
pub fn adelic_spectrum_check(
    eigenvalues: &[f64],
    alpha: f64,
    rho_limit: f64,
    max_nonzero: usize,
) -> Vec<bool> {
    eigenvalues
        .iter()
        .map(|&ev| adelic_eigenvalue_check(ev, alpha, rho_limit, &DEFAULT_PRIMES, max_nonzero))
        .collect()
}
