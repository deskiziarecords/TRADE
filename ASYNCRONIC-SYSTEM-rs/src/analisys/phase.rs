#![allow(unused_imports)]
// ─────────────────────────────────────────────────────────────────────────────
// phase.rs  –  IPDA phase detector (Accumulation / Manipulation / Distribution)
// ─────────────────────────────────────────────────────────────────────────────

use crate::{
    config::{LOOKBACK_DAYS, BARS_PER_DAY, PRICE_MOVE_SIGMA, RECENT_VOL_BARS, VOL_SPIKE_FACTOR},
    indicators::{mean, rolling_return_vol},
    types::{Bar, Phase},
};

/// Maximum bar count we ever need in the rolling buffer
/// (longest look-back converted to bars).
pub const MAX_BUFFER_BARS: usize = {
    let max_days = LOOKBACK_DAYS[2]; // 60 days
    (max_days as usize) * BARS_PER_DAY
};

/// Minimum bars in the buffer before phase detection can run.
/// Uses the shortest look-back (20 days) so signals appear early.
pub const MIN_BARS_FOR_PHASE: usize = LOOKBACK_DAYS[0] as usize * BARS_PER_DAY;

/// Detect the current IPDA phase from the rolling bar history.
///
/// Rules (in priority order):
/// 1. **Accumulation** – last bar makes a higher low *and* volume is
///    contracting vs. the prior `RECENT_VOL_BARS` average.
/// 2. **Manipulation** – absolute return on the last bar exceeds
///    `PRICE_MOVE_SIGMA × rolling_return_vol` *and* volume spikes.
/// 3. **Distribution** – last bar makes a lower high *and* volume is
///    expanding vs. the prior `RECENT_VOL_BARS` average.
/// 4. **Flat** – none of the above conditions are met.
pub fn detect_phase(bars: &[Bar]) -> Phase {
    // Need at least the 20-day window
    if bars.len() < MIN_BARS_FOR_PHASE {
        return Phase::Flat;
    }

    // Work on the most recent 20-day window
    let lookback_20 = LOOKBACK_DAYS[0] as usize * BARS_PER_DAY;
    let df20 = &bars[bars.len().saturating_sub(lookback_20)..];

    let n = df20.len();
    if n < RECENT_VOL_BARS + 2 {
        return Phase::Flat;
    }

    let last  = &df20[n - 1];
    let prev  = &df20[n - 2];

    // Recent-volume baseline: mean of the last RECENT_VOL_BARS bars
    let recent_vols: Vec<f64> = df20[n.saturating_sub(RECENT_VOL_BARS)..n - 1]
        .iter()
        .map(|b| b.volume)
        .collect();
    let avg_recent_vol = mean(&recent_vols);

    // ── 1. Accumulation ──────────────────────────────────────────────────────
    let higher_low      = last.low > prev.low;
    let contracting_vol = last.volume < avg_recent_vol;
    if higher_low && contracting_vol {
        return Phase::Accumulation;
    }

    // ── 2. Manipulation ──────────────────────────────────────────────────────
    let ret_vol = rolling_return_vol(df20, RECENT_VOL_BARS);
    let price_change = if prev.close != 0.0 {
        ((last.close - prev.close) / prev.close).abs()
    } else {
        0.0
    };
    let vol_spike = last.volume > VOL_SPIKE_FACTOR * avg_recent_vol;
    if price_change > PRICE_MOVE_SIGMA * ret_vol && vol_spike {
        return Phase::Manipulation;
    }

    // ── 3. Distribution ──────────────────────────────────────────────────────
    let lower_high    = last.high < prev.high;
    let expanding_vol = last.volume > avg_recent_vol;
    if lower_high && expanding_vol {
        return Phase::Distribution;
    }

    Phase::Flat
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_bar(high: f64, low: f64, close: f64, volume: f64) -> Bar {
        Bar { open: (high + low) / 2.0, high, low, close, volume, ts: 0 }
    }

    #[test]
    fn too_few_bars_returns_flat() {
        let bars = vec![make_bar(1.1, 1.0, 1.05, 1000.0); 10];
        assert_eq!(detect_phase(&bars), Phase::Flat);
    }
}
