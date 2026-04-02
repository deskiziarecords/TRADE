// ─────────────────────────────────────────────────────────────────────────────
// config.rs  –  All tuneable parameters in one place
// ─────────────────────────────────────────────────────────────────────────────

/// Redis connection settings
pub const REDIS_URL: &str = "redis://127.0.0.1:6379/0";

/// Redis stream written by UROL (clean OHLCV bars)
pub const STREAM_CLEAN_TICKS: &str = "clean:ticks";

/// Redis stream consumed by AECABI (IPDA signals)
pub const STREAM_JAX_SIGNALS: &str = "jax:signals";

/// Redis key for persisted global state
pub const STATE_KEY: &str = "trading:global_state";

/// Bar duration in milliseconds (1-minute bars)
pub const BUCKET_MS: i64 = 60_000;

/// Trading days
pub const LOOKBACK_DAYS: [u32; 3] = [20, 40, 60];

/// 1-minute bars → 1 440 bars per 24-hour day
pub const BARS_PER_DAY: usize = 1_440;

/// Kill-zone definitions as (start_utc_hour, end_utc_hour) — exclusive end.
/// NY session:     12:00–15:00 UTC (07:00–10:00 EST)
/// London session: 07:00–10:00 UTC (02:00–05:00 EST)
pub const KILL_ZONES: [(u32, u32); 2] = [(12, 15), (7, 10)];

// ── Risk parameters (tune per account) ───────────────────────────────────────

/// Account equity in account currency
pub const EQUITY: f64 = 100_000.0;

/// Fraction of equity risked per trade (1 %)
pub const RISK_PER_TRADE: f64 = 0.01;

/// Pip value for standard FX pairs (use 0.01 for JPY pairs)
pub const PIP_VALUE: f64 = 0.0001;

// ── Phase-detection thresholds ────────────────────────────────────────────────

/// Volume-spike multiplier for manipulation detection
pub const VOL_SPIKE_FACTOR: f64 = 1.5;

/// Return-volatility multiplier for manipulation price-move detection
pub const PRICE_MOVE_SIGMA: f64 = 2.0;

/// Wilder ATR smoothing period (bars)
pub const ATR_PERIOD: usize = 20;

/// Short lookback (bars) used for recent-volume comparisons inside phase logic
pub const RECENT_VOL_BARS: usize = 5;

// ── State-persistence interval ────────────────────────────────────────────────

/// How often UROL flushes GlobalState to Redis (milliseconds)
pub const STATE_FLUSH_MS: u64 = 500;
