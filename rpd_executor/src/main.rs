//! RPD Executor binary entry point

use rpd_executor::{ExecutionEngine, EngineConfig, HighResClock};
use schur_engine::{SchurRouter, RoutingParams, Venue};
use rpd_net::{TradingUring, UringConfig, FastTcp};
use tokio::sync::mpsc;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "rpd_executor=info".into()),
        )
        .with(tracing_subscriber::fmt::layer().with_target(false))
        .init();
    
    // Configuration
    let config = EngineConfig {
        engine_cpu: 8,
        io_cpu: 9,
        target_latency_us: 5.0,
        max_latency_us: 10.0,
        max_orders_per_second: 1000,
        max_notional_per_minute: 10_000_000.0,
        max_batch_size: 32,
        batch_timeout_us: 50,
    };
    
    // Initialize Schur router
    let venues = vec![
        Venue { id: 0, liquidity: 0.1, latency_ms: 20.0, fees: 0.0001 },
        Venue { id: 1, liquidity: 0.05, latency_ms: 50.0, fees: 0.0002 },
        Venue { id: 2, liquidity: 0.08, latency_ms: 15.0, fees: 0.00015 },
    ];
    
    let routing_params = RoutingParams {
        slippage_gamma: vec![0.1, 0.05, 0.08],
        slippage_delta: vec![1.5, 1.5, 1.5],
        correlation_decay: 0.01,
        adelic_alpha: 1.5,
        adelic_rho: 3.5,
        adelic_max_nonzero: 3,
        blowup_kappa: 3.0,
    };
    
    let router = SchurRouter::new(venues, routing_params);
    
    // Initialize io_uring
    let uring_config = UringConfig {
        sq_entries: 4096,
        cq_entries: 8192,
        sqpoll_idle: 0,
        iopoll: true,
        cq_entries_flags: 0,
    };
    
    let uring = TradingUring::new(uring_config)?;
    
    // Connect sockets (simplified)
    let sockets = vec![
        FastTcp::new(connect_venue("203.0.113.10:443").await?),
        FastTcp::new(connect_venue("203.0.113.11:443").await?),
        FastTcp::new(connect_venue("203.0.113.12:443").await?),
    ];
    
    // Channels
    let (signal_tx, signal_rx) = mpsc::channel(1024);
    let (event_tx, mut event_rx) = mpsc::channel(1024);
    
    // Spawn engine
    let engine = ExecutionEngine::new(
        config,
        router,
        uring,
        sockets,
        signal_rx,
        event_tx,
    ).await?;
    
    let engine_handle = tokio::spawn(async move {
        engine.run().await
    });
    
    // Spawn event handler
    let event_handle = tokio::spawn(async move {
        while let Some(event) = event_rx.recv().await {
            tracing::info!(?event, "Order event");
        }
    });
    
    // Simulate strategy signals (in production: from IPC/socket)
    tokio::spawn(async move {
        let mut seq = 0;
        loop {
            tokio::time::sleep(tokio::time::Duration::from_millis(1)).await;
            seq += 1;
            
            let signal = OrderSignal {
                seq_num: seq,
                timestamp_ns: HighResClock::new().now_ns(),
                symbol: "EUR/USD".to_string(),
                side: if seq % 2 == 0 { Side::Buy } else { Side::Sell },
                equity: 100000.0,
                ev_t: 0.0114,
                atr_t: 0.008,
                phi_t: 0.75,
                adelic_valid: true,
                venues: vec![
                    VenueSnapshot { venue_id: 0, ofi: 0.3, latency_us: 20000.0, available_liquidity: 1000000.0 },
                    VenueSnapshot { venue_id: 1, ofi: 0.2, latency_us: 50000.0, available_liquidity: 500000.0 },
                    VenueSnapshot { venue_id: 2, ofi: 0.4, latency_us: 15000.0, available_liquidity: 800000.0 },
                ],
            };
            
            let _ = signal_tx.send(signal).await;
        }
    });
    
    // Wait for shutdown
    tokio::select! {
        result = engine_handle => {
            result??;
        }
        _ = tokio::signal::ctrl_c() => {
            info!("Shutdown signal received");
        }
    }
    
    event_handle.abort();
    Ok(())
}

async fn connect_venue(addr: &str) -> std::io::Result<std::os::unix::io::RawFd> {
    use tokio::net::TcpStream;
    let stream = TcpStream::connect(addr).await?;
    Ok(stream.into_std()?.into_raw_fd())
}
