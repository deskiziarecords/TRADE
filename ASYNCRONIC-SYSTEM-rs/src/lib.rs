//! IPDA Trading Engine
//! 
//! Async trading system with 5 concurrent Tokio tasks:
//! - UROL: Tick ingestion, MAD filter, OHLCV bucketing, watchdog
//! - IPDA: Core signal loop (Redis clean:ticks → jax:signals)
//! - AECABI: TCA filter, order submission, shadow fill engine
//! - State: Global persistence + background flush
//! - Kill Zone: Session gating (London/NY)

#![warn(missing_docs)]
#![warn(rust_2018_idioms)]
#![warn(clippy::pedantic)]
#![allow(clippy::module_name_repetitions)]

// ═══════════════════════════════════════════════════════════════════════════════
// PUBLIC API EXPORTS
// ═══════════════════════════════════════════════════════════════════════════════

pub mod aecabi;
pub mod config;
pub mod indicators;
pub mod ipda;
pub mod kill_zone;
pub mod phase;
pub mod state;
pub mod types;
pub mod urol;

// Re-export commonly used types for convenience
pub use types::{Action, Bar, GlobalState, Phase, Signal, Tick};

// Re-export configuration constants
pub use config::Constants;

// ═══════════════════════════════════════════════════════════════════════════════
// ASYNC RUNTIME ORCHESTRATION (Used by main.rs)
// ═══════════════════════════════════════════════════════════════════════════════

use tokio::task::JoinHandle;
use tracing::{error, info, warn};

/// Spawn all 5 concurrent system tasks.
/// 
/// Returns a vector of handles for supervision. If any task panics,
/// the watchdog should trigger graceful shutdown via kill switch.
/// 
/// # Errors
/// Returns error if Redis/SQLite connections fail on startup.
pub async fn spawn_system_tasks(
    redis_conn: redis::aio::MultiplexedConnection,
    sqlite_pool: sqlx::SqlitePool,
    shutdown: tokio::sync::broadcast::Sender<()>,
) -> anyhow::Result<Vec<JoinHandle<anyhow::Result<()>>>> {
    let mut handles = Vec::with_capacity(5);
    let mut rx = shutdown.subscribe();

    // Task 1: UROL - Tick Ingestion Pipeline
    let urol_handle = tokio::spawn({
        let redis = redis_conn.clone();
        let kill_switch = shutdown.clone();
        async move {
            info!("UROL: Starting tick ingestion");
            urol::run(redis, kill_switch).await
        }
    });
    handles.push(urol_handle);

    // Task 2: IPDA - Core Signal Generation
    let ipda_handle = tokio::spawn({
        let redis = redis_conn.clone();
        let pool = sqlite_pool.clone();
        let kill_switch = shutdown.clone();
        async move {
            info!("IPDA: Starting signal loop");
            ipda::run(redis, pool, kill_switch).await
        }
    });
    handles.push(ipda_handle);

    // Task 3: AECABI - Execution Engine
    let aecabi_handle = tokio::spawn({
        let pool = sqlite_pool.clone();
        let kill_switch = shutdown.clone();
        async move {
            info!("AECABI: Starting execution engine");
            aecabi::run(pool, kill_switch).await
        }
    });
    handles.push(aecabi_handle);

    // Task 4: State Persistence Background Task
    let state_handle = tokio::spawn({
        let pool = sqlite_pool.clone();
        let kill_switch = shutdown.clone();
        async move {
            info!("STATE: Starting persistence task");
            state::background_persist(pool, kill_switch).await
        }
    });
    handles.push(state_handle);

    // Task 5: Kill Zone Session Gate + Watchdog
    let kill_zone_handle = tokio::spawn({
        let kill_switch = shutdown.clone();
        async move {
            info!("KILL_ZONE: Starting session gate");
            kill_zone::run(kill_switch).await
        }
    });
    handles.push(kill_zone_handle);

    // Supervision: Monitor for task failures
    tokio::spawn(async move {
        let mut rx = shutdown.subscribe();
        loop {
            tokio::select! {
                _ = rx.recv() => {
                    info!("Supervision: Shutdown signal received");
                    break;
                }
                _ = tokio::time::sleep(std::time::Duration::from_secs(1)) => {
                    // Health check could go here
                }
            }
        }
    });

    Ok(handles)
}

/// Graceful shutdown coordinator.
/// 
/// Aborts all tasks and ensures SQLite connections are flushed.
pub async fn graceful_shutdown(
    handles: Vec<JoinHandle<anyhow::Result<()>>>,
    pool: sqlx::SqlitePool,
) {
    info!("Initiating graceful shutdown...");
    
    // Signal all tasks to stop
    for handle in handles {
        handle.abort();
    }
    
    // Ensure database connections closed cleanly
    pool.close().await;
    
    info!("Shutdown complete");
}

// ═══════════════════════════════════════════════════════════════════════════════
// MODULE PRELUDE (Internal macros/utilities)
// ═══════════════════════════════════════════════════════════════════════════════

/// Internal prelude for module consistency
pub(crate) mod prelude {
    pub use tracing::{debug, error, info, trace, warn};
    pub use anyhow::{Context, Result};
    pub use std::sync::Arc;
    pub use tokio::sync::{RwLock, Mutex, mpsc, broadcast};
}
