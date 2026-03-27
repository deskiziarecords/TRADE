use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use schur_engine::{SchurRouter, RoutingParams, Venue};
use nalgebra::DMatrix;

fn bench_schur_3venues(c: &mut Criterion) {
    let venues = vec![
        Venue { id: 0, liquidity: 0.1, latency_ms: 20.0, fees: 0.0001 },
        Venue { id: 1, liquidity: 0.05, latency_ms: 50.0, fees: 0.0002 },
        Venue { id: 2, liquidity: 0.08, latency_ms: 15.0, fees: 0.00015 },
    ];
    
    let params = RoutingParams {
        slippage_gamma: vec![0.1, 0.05, 0.08],
        slippage_delta: vec![1.5, 1.5, 1.5],
        correlation_decay: 0.01,
        adelic_alpha: 1.5,
        adelic_rho: 3.5,
        adelic_max_nonzero: 3,
        blowup_kappa: 3.0,
    };
    
    let router = SchurRouter::new(venues, params);
    let ofi = DMatrix::from_element(3, 3, 0.3);
    let prev_w = nalgebra::DVector::from_element(3, 1.0/3.0);
    
    c.bench_with_input(BenchmarkId::new("schur", "3venues"), &router, |b, r| {
        b.iter(|| r.optimize(black_box(52100.0), black_box(&ofi), black_box(&prev_w)))
    });
}

fn bench_schur_8venues(c: &mut Criterion) {
    // Simulate 8 venues (major + ECNs)
    let venues: Vec<Venue> = (0..8).map(|i| Venue {
        id: i,
        liquidity: 0.05 + (i as f64 * 0.01),
        latency_ms: 10.0 + (i as f64 * 5.0),
        fees: 0.0001 + (i as f64 * 0.00005),
    }).collect();
    
    let params = RoutingParams {
        slippage_gamma: vec![0.1; 8],
        slippage_delta: vec![1.5; 8],
        correlation_decay: 0.01,
        adelic_alpha: 1.5,
        adelic_rho: 3.5,
        adelic_max_nonzero: 4,
        blowup_kappa: 3.0,
    };
    
    let router = SchurRouter::new(venues, params);
    let ofi = DMatrix::from_element(8, 8, 0.2);
    let prev_w = nalgebra::DVector::from_element(8, 1.0/8.0);
    
    c.bench_with_input(BenchmarkId::new("schur", "8venues"), &router, |b, r| {
        b.iter(|| r.optimize(black_box(52100.0), black_box(&ofi), black_box(&prev_w)))
    });
}

criterion_group!(benches, bench_schur_3venues, bench_schur_8venues);
criterion_main!(benches);
