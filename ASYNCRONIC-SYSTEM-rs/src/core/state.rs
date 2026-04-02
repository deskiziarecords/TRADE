// ─────────────────────────────────────────────────────────────────────────────
// state.rs  –  GlobalState persistence  (UROL reliability layer)
//
// Flushes state to Redis every STATE_FLUSH_MS milliseconds so that a
// crash + restart loses at most one flush interval of context.
// ─────────────────────────────────────────────────────────────────────────────

use anyhow::Result;
use redis::AsyncCommands;
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{interval, Duration};
use tracing::{error, info};

use crate::{config::{STATE_FLUSH_MS, STATE_KEY}, types::GlobalState};

/// Shared, async-safe handle to the live GlobalState.
pub type SharedState = Arc<RwLock<GlobalState>>;

/// Load state from Redis, falling back to `Default` if the key is absent.
pub async fn load_state(con: &mut impl AsyncCommands) -> Result<GlobalState> {
    let raw: Option<String> = con.get(STATE_KEY).await?;
    match raw {
        Some(json) => {
            let state = serde_json::from_str(&json)?;
            info!("State loaded from Redis");
            Ok(state)
        }
        None => {
            info!("No persisted state found – starting fresh");
            Ok(GlobalState::default())
        }
    }
}

/// Persist state to Redis.
pub async fn flush_state(con: &mut impl AsyncCommands, state: &GlobalState) -> Result<()> {
    let json = serde_json::to_string(state)?;
    con.set::<_, _, ()>(STATE_KEY, json).await?;
    Ok(())
}

/// Background task: flush the shared state to Redis every `STATE_FLUSH_MS` ms.
///
/// Spawned once at startup; runs until the process exits.
pub async fn state_flush_loop(shared: SharedState, mut con: redis::aio::MultiplexedConnection) {
    let mut tick = interval(Duration::from_millis(STATE_FLUSH_MS));
    loop {
        tick.tick().await;
        let state = shared.read().await.clone();
        let json = match serde_json::to_string(&state) {
            Ok(j)  => j,
            Err(e) => { error!("State serialisation failed: {e}"); continue; }
        };
        if let Err(e) = con.set::<_, _, ()>(STATE_KEY, json).await {
            error!("Redis state flush failed: {e}");
        }
    }
}
