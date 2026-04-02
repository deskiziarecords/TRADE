// ─────────────────────────────────────────────────────────────────────────────
// main.rs  –  Entry point: wires UROL + IPDA core + AECABI
//
// Three concurrent Tokio tasks:
//   1. UROL ingestion  – raw ticks → MAD filter → OHLCV buckets → clean:ticks
//   2. UROL watchdog   – heartbeat + Mandra-gate drawdown kill-switch
//   3. UROL state flush– persists GlobalState to Redis every 500 ms
//   4. IPDA core       – clean:ticks → phase detection → jax:signals
//   5. AECABI gateway  – jax:signals → TCA filter → live order + shadow fill
// ─────────────────────────────────────────────────────────────────────────────

mod aecabi;
mod config;
mod indicators;
mod ipda;
mod kill_zone;
mod phase;
mod state;
mod types;
mod urol;

use anyhow::Result;
use redis::Client;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;
use tracing_subscriber::EnvFilter;

use crate::{
    config::REDIS_URL,
    state::{load_state, state_flush_loop, SharedState},
};

#[tokio::main]
async fn main() -> Result<()> {
    // ── Logging ───────────────────────────────────────────────────────────────
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    info!("═══════════════════════════════════════════════");
    info!("  IPDA Trading System  –  starting all tasks   ");
    info!("═══════════════════════════════════════════════");

    // ── Redis client (one connection per task) ────────────────────────────────
    let client = Client::open(REDIS_URL)?;

    let mut state_con    = client.get_multiplexed_async_connection().await?;
    let flush_con        = client.get_multiplexed_async_connection().await?;
    let urol_ingest_con  = client.get_multiplexed_async_connection().await?;
    let urol_watch_con   = client.get_multiplexed_async_connection().await?;
    let ipda_con         = client.get_multiplexed_async_connection().await?;
    let aecabi_con       = client.get_multiplexed_async_connection().await?;

    // ── UROL: load persisted state ────────────────────────────────────────────
    let initial_state = load_state(&mut state_con).await?;
    info!("Restored state: phase={:?}  drawdown={:.2}%",
        initial_state.ipda_phase,
        initial_state.current_drawdown * 100.0);

    let shared_state: SharedState = Arc::new(RwLock::new(initial_state));

    // ── Task 1: UROL state flush (background, every 500 ms) ──────────────────
    let s1 = Arc::clone(&shared_state);
    tokio::spawn(async move {
        state_flush_loop(s1, flush_con).await;
    });

    // ── Task 2: UROL data ingestion (ticks → OHLCV → clean:ticks) ────────────
    let s2 = Arc::clone(&shared_state);
    tokio::spawn(async move {
        if let Err(e) = urol::run_ingestion(urol_ingest_con, s2).await {
            tracing::error!("UROL ingestion crashed: {e}");
        }
    });

    // ── Task 3: UROL watchdog (heartbeat + Mandra-gate) ──────────────────────
    let s3 = Arc::clone(&shared_state);
    tokio::spawn(async move {
        if let Err(e) = urol::run_watchdog(urol_watch_con, s3).await {
            tracing::error!("UROL watchdog crashed: {e}");
        }
    });

    // ── Task 4: AECABI execution gateway (jax:signals → broker + shadow) ─────
    tokio::spawn(async move {
        if let Err(e) = aecabi::run(aecabi_con).await {
            tracing::error!("AECABI crashed: {e}");
        }
    });

    // ── Task 5: IPDA core (clean:ticks → phase → jax:signals)  [main thread] ─
    let s5 = Arc::clone(&shared_state);
    ipda::run(ipda_con, s5).await?;

    Ok(())
}
