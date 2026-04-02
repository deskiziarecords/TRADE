// ─────────────────────────────────────────────────────────────────────────────
// indicators.rs  –  Low-level technical indicators (no external crate needed)
// ─────────────────────────────────────────────────────────────────────────────

use crate::types::Bar;

/// Wilder's Average True Range over the last `period` bars.
///
/// Returns 0.0 when `bars` is too short to compute anything meaningful.
pub fn atr(bars: &[Bar], period: usize) -> f64 {
    if bars.len() < 2 {
        return 0.0;
    }

    // True Range for each bar (needs previous close)
    let tr: Vec<f64> = bars
        .windows(2)
        .map(|w| {
            let prev_close = w[0].close;
            let cur = &w[1];
            let hl  = cur.high - cur.low;
            let hpc = (cur.high - prev_close).abs();
            let lpc = (cur.low  - prev_close).abs();
            hl.max(hpc).max(lpc)
        })
        .collect();

    if tr.is_empty() {
        return 0.0;
    }

    // Wilder's smoothing: ATR[i] = (ATR[i-1] * (period-1) + TR[i]) / period
    let p = period as f64;
    let mut current_atr = tr[0];
    for &t in tr.iter().skip(1) {
        current_atr = (current_atr * (p - 1.0) + t) / p;
    }
    current_atr
}

/// Simple mean of a slice (returns 0.0 for empty input).
pub fn mean(values: &[f64]) -> f64 {
    if values.is_empty() { return 0.0; }
    values.iter().sum::<f64>() / values.len() as f64
}

/// Population standard deviation of a slice.
pub fn std_dev(values: &[f64]) -> f64 {
    if values.len() < 2 { return 0.0; }
    let m = mean(values);
    let var = values.iter().map(|v| (v - m).powi(2)).sum::<f64>() / values.len() as f64;
    var.sqrt()
}

/// Percentage changes between consecutive close prices.
pub fn pct_changes(closes: &[f64]) -> Vec<f64> {
    closes
        .windows(2)
        .map(|w| (w[1] - w[0]) / w[0])
        .collect()
}

/// Rolling standard deviation of the last `window` pct-changes.
/// Returns 0.0 when there is insufficient data.
pub fn rolling_return_vol(bars: &[Bar], window: usize) -> f64 {
    if bars.len() < window + 1 {
        return 0.0;
    }
    let closes: Vec<f64> = bars.iter().map(|b| b.close).collect();
    let changes = pct_changes(&closes);
    let recent  = &changes[changes.len().saturating_sub(window)..];
    std_dev(recent)
}
