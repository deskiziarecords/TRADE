//! Example usage — mirrors the Python `example_usage()` function exactly.

use position_sizing::*;

fn main() {
    println!("{}", "=".repeat(60));
    println!("POSITION SIZING LIBRARY — EXAMPLE USAGE");
    println!("{}", "=".repeat(60));

    // ── 1. Risk of Ruin ────────────────────────────────────────
    println!("\n1. RISK OF RUIN");
    println!("{}", "-".repeat(40));
    let ruin_prob = risk_of_ruin(0.55, 0.02, 2.0);
    println!("Risk of ruin: {:.2}%", ruin_prob * 100.0);

    let max_risk = maximum_safe_risk(0.55, 2.0, 0.05);
    println!("Maximum safe risk per trade: {:.2}%", max_risk * 100.0);

    // ── 2. Volatility Targeting ────────────────────────────────
    println!("\n2. VOLATILITY TARGETING");
    println!("{}", "-".repeat(40));
    let atr_history = vec![0.12, 0.15, 0.18, 0.20, 0.22, 0.19, 0.16, 0.14, 0.13, 0.12];
    let scaling = volatility_targeting(&atr_history, 0.15, 3.0, 0.2);
    println!("Volatility scaling factor: {:.2}x", scaling);

    // ── 3. Adaptive Kelly ──────────────────────────────────────
    println!("\n3. ADAPTIVE KELLY");
    println!("{}", "-".repeat(40));
    let kelly = AdaptiveKelly::default();
    let kelly_fraction = kelly.calculate(0.55, 1.5, MarketRegime::Trending);
    println!("Adaptive Kelly fraction: {:.2}%", kelly_fraction * 100.0);

    // ── 4. Bayesian Sizer ──────────────────────────────────────
    println!("\n4. BAYESIAN SIZER");
    println!("{}", "-".repeat(40));
    let mut bayesian = BayesianSizer::default();
    bayesian.update(TradeResult { is_win: true,  profit_loss:  0.10, timestamp: None });
    bayesian.update(TradeResult { is_win: false, profit_loss: -0.05, timestamp: None });
    bayesian.update(TradeResult { is_win: true,  profit_loss:  0.12, timestamp: None });
    println!("Bayesian Kelly fraction: {:.2}%", bayesian.current_kelly(0.25) * 100.0);
    let (lo, hi) = bayesian.confidence_interval(0.95);
    println!("Win rate 95% CI: {:.2}% – {:.2}%", lo * 100.0, hi * 100.0);

    // ── 5. Optimal f ───────────────────────────────────────────
    println!("\n5. OPTIMAL F");
    println!("{}", "-".repeat(40));
    let trades = vec![0.10, -0.05, 0.12, -0.03, 0.08, -0.04, 0.15, -0.02];
    let opt = optimal_f(&trades, None);
    println!("Optimal f: {:.2}%", opt * 100.0);

    // ── 6. Entropy ─────────────────────────────────────────────
    println!("\n6. ENTROPY UNCERTAINTY");
    println!("{}", "-".repeat(40));
    let price_dist = vec![0.05, 0.10, 0.15, 0.20, 0.25, 0.15, 0.05, 0.03, 0.02];
    let entropy = entropy_uncertainty(&price_dist, true);
    println!("Market entropy: {:.3}", entropy);
    println!("Uncertainty scaling: {:.2}x", uncertainty_scaling_factor(entropy, 2.0));

    // ── 7. Comprehensive Position Sizer ───────────────────────
    println!("\n7. COMPREHENSIVE POSITION SIZER");
    println!("{}", "-".repeat(40));
    let sizer = ComprehensivePositionSizer::new(100_000.0);
    let result = sizer.calculate_position(
        0.55, 1.5, 0.01,
        MarketRegime::Trending,
        None, None,
    );
    println!("Risk fraction:     {:.2}%",  result.risk_fraction     * 100.0);
    println!("Risk amount:       ${:.2}",  result.risk_amount);
    println!("Notional position: ${:.2}",  result.notional_position);
    println!("\nComponent breakdown:");
    println!("  bayesian_kelly: {:.2}%", result.components.bayesian_kelly * 100.0);
    println!("  regime_kelly:   {:.2}%", result.components.regime_kelly   * 100.0);
    println!("  vol_scaling:    {:.2}x", result.components.vol_scaling);
    println!("  mae_scaling:    {:.2}x", result.components.mae_scaling);
    println!("  max_risk_cap:   {:.2}%", result.components.max_risk_cap   * 100.0);

    println!("\n{}", "=".repeat(60));
    println!("All algorithms executed successfully!");
    println!("{}", "=".repeat(60));
}
