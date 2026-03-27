//! Async tokio execution engine
//! End-to-end: Signal → Schur → FIX → io_uring → Confirmation

use tokio::sync::{mpsc, oneshot, RwLock};
use tokio::time::{interval, Instant, Duration};
use futures::stream::{Stream, StreamExt};
use parking_lot::Mutex;
use quanta::Clock;
use std::sync::Arc;
use std::pin::Pin;
use tracing::{info, warn, error, trace};

use schur_engine::{SchurRouter, RoutingResult, RoutingParams, Venue};
use fix_encoder::{FixEncoder, NewOrderSingle, Side, OrdType, TimeInForce};
use rpd_net::{
    TradingUring, UringConfig, FastTcp, RegisteredBuffers,
    OrderRequest, OrderEvent, init_thread_pool, with_pool,
};

/// High-precision clock for latency measurement
pub struct HighResClock {
    inner: Clock,
    baseline: u64,
}

impl HighResClock {
    pub fn new() -> Self {
        let clock = Clock::new();
        let baseline = clock.raw();
        Self { inner: clock, baseline }
    }
    
    #[inline(always)]
    pub fn now_ns(&self) -> u64 {
        self.inner.raw() - self.baseline
    }
    
    #[inline(always)]
    pub fn elapsed_ns(&self, start: u64) -> u64 {
        self.now_ns() - start
    }
}

/// Execution engine configuration
#[derive(Debug, Clone)]
pub struct EngineConfig {
    /// CPU isolation
    pub engine_cpu: usize,           // Core for main loop (e.g., 8)
    pub io_cpu: usize,               // Core for io_uring (e.g., 9)
    
    /// Latency targets
    pub target_latency_us: f64,      // 5.0 microsecond p99
    pub max_latency_us: f64,         // 10.0 microsecond hard limit
    
    /// Risk limits
    pub max_orders_per_second: u32,  // 1000
    pub max_notional_per_minute: f64, // $10M
    
    /// Batch sizes
    pub max_batch_size: usize,       // 32 orders
    pub batch_timeout_us: u64,       // 50 microseconds
}

/// Order signal from strategy
#[derive(Debug, Clone)]
pub struct OrderSignal {
    pub seq_num: u64,
    pub timestamp_ns: u64,           // Strategy generation time
    pub symbol: String,
    pub side: Side,
    pub equity: f64,
    pub ev_t: f64,
    pub atr_t: f64,
    pub phi_t: f64,
    pub adelic_valid: bool,
    pub venues: Vec<VenueSnapshot>,
}

#[derive(Debug, Clone)]
pub struct VenueSnapshot {
    pub venue_id: u32,
    pub ofi: f64,
    pub latency_us: f64,
    pub available_liquidity: f64,
}

/// Internal order with routing decision
#[derive(Debug)]
pub struct RoutedOrder {
    pub signal: OrderSignal,
    pub routing: RoutingResult,
    pub route_time_ns: u64,
    pub encode_time_ns: u64,
}

/// Execution statistics
#[derive(Debug, Default)]
pub struct ExecutionStats {
    pub orders_submitted: u64,
    pub orders_filled: u64,
    pub orders_rejected: u64,
    pub avg_latency_ns: f64,
    pub p99_latency_ns: f64,
    pub max_latency_ns: u64,
    pub circuit_breaker_triggers: u64,
}

/// Main execution engine
pub struct ExecutionEngine {
    config: EngineConfig,
    clock: HighResClock,
    
    // Components
    router: Arc<RwLock<SchurRouter>>,
    encoder: Arc<Mutex<FixEncoder<4096>>>,
    uring: Arc<Mutex<TradingUring>>,
    sockets: Vec<FastTcp>,
    
    // Channels
    signal_rx: mpsc::Receiver<OrderSignal>,
    event_tx: mpsc::Sender<OrderEvent>,
    
    // State
    stats: Arc<Mutex<ExecutionStats>>,
    circuit_open: Arc<AtomicBool>,
    last_order_ns: AtomicU64,
    notional_window: Arc<Mutex<SlidingWindow<f64>>>,
}

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

impl ExecutionEngine {
    pub async fn new(
        config: EngineConfig,
        router: SchurRouter,
        uring: TradingUring,
        sockets: Vec<FastTcp>,
        signal_rx: mpsc::Receiver<OrderSignal>,
        event_tx: mpsc::Sender<OrderEvent>,
    ) -> std::io::Result<Self> {
        let encoder = FixEncoder::new("RPD_TRADER", "MULTI");
        
        Ok(Self {
            config,
            clock: HighResClock::new(),
            router: Arc::new(RwLock::new(router)),
            encoder: Arc::new(Mutex::new(encoder)),
            uring: Arc::new(Mutex::new(uring)),
            sockets,
            signal_rx,
            event_tx,
            stats: Arc::new(Mutex::new(ExecutionStats::default())),
            circuit_open: Arc::new(AtomicBool::new(false)),
            last_order_ns: AtomicU64::new(0),
            notional_window: Arc::new(Mutex::new(SlidingWindow::new(
                Duration::from_secs(60),
                10000,
            ))),
        })
    }
    
    /// Main async execution loop
    pub async fn run(mut self) -> anyhow::Result<()> {
        // Pin to isolated CPU
        pin_thread_to_cpu(self.config.engine_cpu);
        init_thread_pool(self.config.engine_cpu);
        
        info!(
            cpu = self.config.engine_cpu,
            target_latency_us = self.config.target_latency_us,
            "RPD Execution Engine starting"
        );
        
        // Spawn io_uring completion handler
        let uring_handle = self.spawn_completion_handler();
        
        // Spawn risk monitor
        let risk_handle = self.spawn_risk_monitor();
        
        // Main order processing loop
        let mut batch: Vec<OrderSignal> = Vec::with_capacity(self.config.max_batch_size);
        let mut batch_start = Instant::now();
        
        loop {
            // Check circuit breaker
            if self.circuit_open.load(Ordering::SeqCst) {
                warn!("Circuit open, draining orders");
                self.drain_and_halt().await;
                break;
            }
            
            // Timeout-based or size-based batching
            let timeout = if batch.is_empty() {
                Duration::from_secs(3600) // Infinite wait for first
            } else {
                Duration::from_micros(self.config.batch_timeout_us)
            };
            
            // Receive with timeout
            match tokio::time::timeout(timeout, self.signal_rx.recv()).await {
                Ok(Some(signal)) => {
                    // Rate limit check
                    if !self.check_rate_limit(&signal) {
                        continue;
                    }
                    
                    batch.push(signal);
                    
                    // Flush if batch full
                    if batch.len() >= self.config.max_batch_size {
                        self.process_batch(&mut batch).await;
                        batch.clear();
                        batch_start = Instant::now();
                    }
                }
                Ok(None) => {
                    // Channel closed
                    info!("Signal channel closed, shutting down");
                    break;
                }
                Err(_) => {
                    // Timeout: process partial batch
                    if !batch.is_empty() {
                        self.process_batch(&mut batch).await;
                        batch.clear();
                        batch_start = Instant::now();
                    }
                }
            }
        }
        
        // Cleanup
        drop(batch);
        uring_handle.await?;
        risk_handle.await?;
        
        Ok(())
    }
    
    /// Process batch of orders: Schur → FIX → io_uring
    async fn process_batch(&self, signals: &mut [OrderSignal]) {
        let batch_start_ns = self.clock.now_ns();
        
        for signal in signals.iter_mut() {
            let order_start_ns = self.clock.now_ns();
            
            // 1. Check adelic constraint (fast reject)
            if !signal.adelic_valid {
                self.emit_event(OrderEvent::Rejected {
                    seq_num: signal.seq_num,
                    reason: "adelic_violation".to_string(),
                    latency_ns: self.clock.elapsed_ns(order_start_ns),
                }).await;
                continue;
            }
            
            // 2. Build OFI matrix from venue snapshots
            let ofi_matrix = self.build_ofi_matrix(&signal.venues);
            let prev_weights = self.get_prev_weights(signal.symbol.clone()).await;
            
            // 3. Schur routing (async with read lock)
            let route_start_ns = self.clock.now_ns();
            let routing = {
                let router = self.router.read().await;
                router.optimize(signal.equity, &ofi_matrix, &prev_weights)
            };
            let route_time_ns = self.clock.elapsed_ns(route_start_ns);
            
            // Check routing validity
            if !routing.adelic_valid || routing.blowup_detected {
                self.emit_event(OrderEvent::Rejected {
                    seq_num: signal.seq_num,
                    reason: "routing_invalid".to_string(),
                    latency_ns: self.clock.elapsed_ns(order_start_ns),
                }).await;
                continue;
            }
            
            // 4. Encode and submit per venue
            let encode_start_ns = self.clock.now_ns();
            let mut submissions = 0;
            
            for (i, (&weight, &qty)) in routing.weights.iter().zip(&routing.quantities).enumerate() {
                if weight < 0.001 || qty < 1.0 {
                    continue; // Skip negligible
                }
                
                // Acquire zero-copy buffer
                let mut buf = match with_pool(|p| p.acquire()) {
                    Some(b) => b,
                    None => {
                        error!("Buffer pool exhausted");
                        break;
                    }
                };
                
                // Build FIX message
                let order = NewOrderSingle {
                    cl_ord_id: format!("RPD{:016}{:04}", signal.seq_num, i).into(),
                    symbol: signal.symbol.clone().into(),
                    side: signal.side,
                    order_qty: (qty * 1e8) as i64,
                    ord_type: OrdType::Limit, // Or Market based on signal
                    price: None, // Market order for speed
                    time_in_force: TimeInForce::IOC,
                    transact_time: self.clock.now_ns(),
                };
                
                // Encode
                let encoder = self.encoder.lock();
                let fix_slice = encoder.encode_new_order_single(&order);
                buf.len = fix_slice.len();
                buf.as_mut_slice()[..fix_slice.len()].copy_from_slice(fix_slice);
                drop(encoder); // Release lock
                
                // Submit to io_uring
                let buf_idx = self.buffer_to_index(&buf);
                let sqe = self.sockets[i].send_sqe(buf_idx, buf.len as u32, 0);
                
                // Async submit (non-blocking)
                let mut uring = self.uring.lock();
                unsafe {
                    let mut sq = uring.ring.submission();
                    if let Some(sqe_slot) = sq.next() {
                        *sqe_slot = sqe.user_data(signal.seq_num << 16 | i as u64).build();
                        // Buffer reclaimed in completion handler
                        std::mem::forget(buf);
                        submissions += 1;
                    }
                }
                
                // Batch submit every 8 SQEs
                if submissions % 8 == 0 {
                    let _ = uring.submit();
                }
            }
            
            // Final submit for remainder
            if submissions > 0 {
                let mut uring = self.uring.lock();
                let _ = uring.submit();
            }
            
            let encode_time_ns = self.clock.elapsed_ns(encode_start_ns);
            let total_time_ns = self.clock.elapsed_ns(order_start_ns);
            
            // Update stats
            {
                let mut stats = self.stats.lock();
                stats.orders_submitted += 1;
                stats.avg_latency_ns = 0.99 * stats.avg_latency_ns + 0.01 * total_time_ns as f64;
                if total_time_ns > stats.max_latency_ns {
                    stats.max_latency_ns = total_time_ns;
                }
            }
            
            // Emit telemetry
            self.emit_event(OrderEvent::Submitted {
                seq_num: signal.seq_num,
                route_time_ns,
                encode_time_ns,
                total_time_ns,
                venues_used: submissions,
            }).await;
            
            // Store weights for next iteration
            self.store_weights(signal.symbol.clone(), routing.weights.clone()).await;
            
            // Check latency SLA
            if total_time_ns > (self.config.max_latency_us * 1000.0) as u64 {
                warn!(
                    seq_num = signal.seq_num,
                    latency_us = total_time_ns as f64 / 1000.0,
                    "Latency SLA violated"
                );
            }
        }
        
        // Batch telemetry
        let batch_time_ns = self.clock.elapsed_ns(batch_start_ns);
        trace!(
            batch_size = signals.len(),
            batch_time_us = batch_time_ns as f64 / 1000.0,
            "Batch processed"
        );
    }
    
    /// Spawn io_uring completion handler
    fn spawn_completion_handler(&self) -> tokio::task::JoinHandle<()> {
        let uring = self.uring.clone();
        let event_tx = self.event_tx.clone();
        let stats = self.stats.clone();
        let clock = HighResClock::new();
        
        tokio::task::spawn_blocking(move || {
            pin_thread_to_cpu(9); // Isolated I/O core
            
            loop {
                let mut uring = uring.lock();
                let n = uring.poll_completions(|cqe| {
                    let result = cqe.result();
                    let user_data = cqe.user_data();
                    let seq_num = user_data >> 16;
                    let venue_id = (user_data & 0xFFFF) as u32;
                    
                    // Reclaim buffer (simplified)
                    // In production: track buffer indices properly
                    
                    let event = if result < 0 {
                        OrderEvent::NetworkError {
                            seq_num,
                            venue_id,
                            error_code: -result,
                        }
                    } else {
                        OrderEvent::Sent {
                            seq_num,
                            venue_id,
                            bytes_sent: result as u32,
                            send_time_ns: clock.now_ns(),
                        }
                    };
                    
                    let _ = event_tx.try_send(event);
                    
                    // Update stats
                    if result >= 0 {
                        let mut s = stats.lock();
                        s.orders_filled += 1;
                    }
                });
                
                // Yield if no completions (cooperative)
                if n == 0 {
                    std::thread::yield_now();
                }
            }
        })
    }
    
    /// Spawn risk monitor
    fn spawn_risk_monitor(&self) -> tokio::task::JoinHandle<()> {
        let circuit = self.circuit_open.clone();
        let stats = self.stats.clone();
        let notional = self.notional_window.clone();
        
        tokio::spawn(async move {
            let mut interval = interval(Duration::from_millis(10));
            
            loop {
                interval.tick().await;
                
                // Check circuit breaker conditions
                let s = stats.lock();
                let current_p99 = s.p99_latency_ns;
                drop(s);
                
                if current_p99 > 15_000_000.0 { // 15ms p99
                    warn!("Circuit breaker: latency spike detected");
                    circuit.store(true, Ordering::SeqCst);
                }
                
                // Check notional limit
                let n = notional.lock();
                let minute_notional: f64 = n.sum();
                drop(n);
                
                if minute_notional > 10_000_000.0 { // $10M/min
                    warn!("Circuit breaker: notional limit exceeded");
                    circuit.store(true, Ordering::SeqCst);
                }
            }
        })
    }
    
    /// Helper: emit event (non-blocking)
    async fn emit_event(&self, event: OrderEvent) {
        let _ = self.event_tx.try_send(event);
    }
    
    /// Helper: build OFI matrix
    fn build_ofi_matrix(&self, venues: &[VenueSnapshot]) -> nalgebra::DMatrix<f64> {
        let n = venues.len();
        let mut m = nalgebra::DMatrix::zeros(n, n);
        
        for i in 0..n {
            for j in 0..n {
                m[(i, j)] = venues[i].ofi * venues[j].ofi; // Correlation proxy
            }
        }
        
        m
    }
    
    /// Helper: get previous weights
    async fn get_prev_weights(&self, symbol: String) -> nalgebra::DVector<f64> {
        // From shared state or uniform default
        nalgebra::DVector::from_element(3, 1.0 / 3.0)
    }
    
    /// Helper: store weights
    async fn store_weights(&self, symbol: String, weights: Vec<f64>) {
        // To shared state
    }
    
    /// Helper: buffer to index mapping
    fn buffer_to_index(&self, _buf: &AlignedBuffer) -> u16 {
        0 // Simplified
    }
    
    /// Helper: rate limit check
    fn check_rate_limit(&self, _signal: &OrderSignal) -> bool {
        let now_ns = self.clock.now_ns();
        let last = self.last_order_ns.swap(now_ns, Ordering::Relaxed);
        let delta_ns = now_ns - last;
        
        // Max 1000 orders/sec = 1ms between orders
        delta_ns > 1_000_000
    }
    
    /// Helper: drain and halt
    async fn drain_and_halt(&mut self) {
        // Cancel pending orders, close positions
        warn!("Emergency halt initiated");
    }
}

/// Sliding window for notional tracking
struct SlidingWindow<T> {
    duration: Duration,
    capacity: usize,
    data: Vec<(Instant, T)>,
}

impl<T: Default + Copy + std::ops::Add<Output = T>> SlidingWindow<T> {
    fn new(duration: Duration, capacity: usize) -> Self {
        Self {
            duration,
            capacity,
            data: Vec::with_capacity(capacity),
        }
    }
    
    fn push(&mut self, time: Instant, value: T) {
        self.data.push((time, value));
        self.trim(time);
    }
    
    fn trim(&mut self, now: Instant) {
        let cutoff = now - self.duration;
        self.data.retain(|(t, _)| *t > cutoff);
    }
    
    fn sum(&self) -> T {
        self.data.iter().map(|(_, v)| *v).fold(T::default(), |a, b| a + b)
    }
}

fn pin_thread_to_cpu(cpu: usize) {
    unsafe {
        let mut cpuset: libc::cpu_set_t = std::mem::zeroed();
        libc::CPU_SET(cpu, &mut cpuset);
        libc::sched_setaffinity(0, std::mem::size_of::<libc::cpu_set_t>(), &cpuset);
    }
}
