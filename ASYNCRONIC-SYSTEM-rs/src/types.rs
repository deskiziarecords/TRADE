// ─────────────────────────────────────────────────────────────────────────────
// types.rs  –  Shared data structures for the IPDA → UROL → AECABI pipeline
// ─────────────────────────────────────────────────────────────────────────────

use serde::{Deserialize, Serialize};

// ── OHLCV bar (written by UROL, read by IPDA core) ───────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Bar {
    pub open:   f64,
    pub high:   f64,
    pub low:    f64,
    pub close:  f64,
    pub volume: f64,
    /// Milliseconds since Unix epoch (UTC)
    pub ts:     i64,
}

// ── IPDA market phase ─────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Phase {
    Accumulation,
    Manipulation,
    Distribution,
    Flat,
}

impl std::fmt::Display for Phase {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Phase::Accumulation => write!(f, "ACCUMULATION"),
            Phase::Manipulation => write!(f, "MANIPULATION"),
            Phase::Distribution => write!(f, "DISTRIBUTION"),
            Phase::Flat         => write!(f, "FLAT"),
        }
    }
}

// ── Trade direction ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Action {
    Buy,
    Sell,
    Flat,
}

impl std::fmt::Display for Action {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Action::Buy  => write!(f, "BUY"),
            Action::Sell => write!(f, "SELL"),
            Action::Flat => write!(f, "FLAT"),
        }
    }
}

// ── Signal published to `jax:signals` (consumed by AECABI) ───────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signal {
    pub action:     Action,
    /// Position size in lots / contracts
    pub size:       f64,
    pub phase:      Phase,
    pub kill_zone:  bool,
    /// Unix timestamp (seconds, float)
    pub timestamp:  f64,
    /// Reference close price at signal time (None when action = Flat)
    pub price:      Option<f64>,
}

// ── Persisted global state (UROL state-persistence schema) ───────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlobalState {
    // Existing UROL / AECABI fields
    pub open_positions:    Vec<serde_json::Value>,
    pub current_drawdown:  f64,
    pub mandra_gate_level: u32,
    pub last_fft_spectrum: Vec<f64>,
    pub active_trade_id:   Option<String>,

    // IPDA-specific additions
    pub ipda_phase:            Phase,
    /// Which look-back (20 / 40 / 60 days) is currently primary
    pub ipda_lookback:         u32,
    pub kill_zone_active:      bool,
    /// Unix epoch-seconds when the current accumulation phase began
    pub accumulation_start_ts: Option<i64>,
}

impl Default for GlobalState {
    fn default() -> Self {
        Self {
            open_positions:        vec![],
            current_drawdown:      0.0,
            mandra_gate_level:     0,
            last_fft_spectrum:     vec![],
            active_trade_id:       None,
            ipda_phase:            Phase::Flat,
            ipda_lookback:         20,
            kill_zone_active:      false,
            accumulation_start_ts: None,
        }
    }
}
