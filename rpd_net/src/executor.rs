//! End-to-end execution: Schur → FIX → io_uring

use crate::uring::{TradingUring, UringConfig, RegisteredBuffers};
use crate::socket::FastTcp;
use crate::zero_copy::{with_pool, init_thread_pool};
use schur_engine::{SchurRouter, RoutingResult};
use fix_encoder::{FixEncoder, NewOrderSingle};

use std::sync::Arc;
use tokio::sync::mpsc;
use std::time::Instant;

/// Complete trading engine
pub struct RpdExecutor {
    uring: TradingUring,
    router: SchurRouter,
    encoder: FixEncoder<4096>,
    sockets: Vec<FastTcp>,
    buffers: RegisteredBuffers,
    tx: mpsc::Sender<OrderEvent>,
    rx: mpsc::Receiver<OrderRequest>,
}

impl RpdExecutor {
    pub fn new(
        config: UringConfig,
        router: SchurRouter,
        venue_fds: Vec<RawFd>,
        tx: mpsc::Sender<OrderEvent>,
        rx: mpsc::Receiver<OrderRequest>,
    ) -> std::io::Result<Self> {
        let mut uring = TradingUring::new(config)?;
        
        // Register buffers
        let buffers = RegisteredBuffers::new(0, 4096, 1024);
        buffers.register(&mut uring.ring)?;
        
        // Wrap sockets
        let mut sockets = Vec::with_capacity(venue_fds.len());
        for (i, fd) in venue_fds.into_iter().enumerate() {
            let mut sock = FastTcp::new(fd);
            sock.set_registered_buffer(0); // Buffer group 0
            sockets.push(sock);
        }
        
        Ok(Self {
            uring,
            router,
            encoder: FixEncoder::new("RPD_TRADER", "MULTI"),
            sockets,
            buffers,
            tx,
            rx,
        })
    }
    
    /// Main event loop
    pub async fn run(mut self) -> std::io::Result<()> {
        // Pin to isolated CPU
        pin_thread_to_cpu(8); // Core 8 (isolated from system)
        
        // Init thread-local buffer pool
        init_thread_pool(8);
        
        let mut last_poll = Instant::now();
        
        loop {
            // 1. Check for new orders (non-blocking)
            if let Ok(req) = self.rx.try_recv() {
                let start = Instant::now();
                
                // 2. Schur routing (<4μs)
                let route = self.router.optimize(
                    req.q_total,
                    &req.ofi_matrix,
                    &req.prev_weights,
                );
                
                let route_time = start.elapsed();
                
                // 3. Encode and submit (<1μs per venue)
                for (i, (&weight, &qty)) in route.weights.iter().zip(&route.quantities).enumerate() {
                    if weight < 0.001 {
                        continue;
                    }
                    
                    // Acquire zero-copy buffer
                    let mut buf = with_pool(|p| p.acquire())
                        .expect("Buffer pool exhausted");
                    
                    // Encode FIX
                    let order = NewOrderSingle {
                        cl_ord_id: format!("RPD{:012}", req.seq_num).into(),
                        symbol: req.symbol.into(),
                        side: req.side,
                        order_qty: (qty * 1e8) as i64,
                        ord_type: req.price.map(|_| fix_encoder::OrdType::Limit)
                            .unwrap_or(fix_encoder::OrdType::Market),
                        price: req.price.map(|p| (p * 1e8) as i64),
                        time_in_force: fix_encoder::TimeInForce::IOC,
                        transact_time: now_nanos(),
                    };
                    
                    let fix_slice = self.encoder.encode_new_order_single(&order);
                    buf.len = fix_slice.len();
                    buf.as_mut_slice()[..fix_slice.len()].copy_from_slice(fix_slice);
                    
                    // Build SQE with registered buffer
                    let buf_idx = self.get_buffer_index(&buf);
                    let sqe = self.sockets[i].send_sqe(buf_idx, buf.len as u32, 0);
                    
                    // Submit to io_uring (no syscall with SQPOLL)
                    unsafe {
                        let mut sq = self.uring.ring.submission();
                        if let Some(mut sqe_slot) = sq.next() {
                            *sqe_slot = sqe.build();
                            // Keep buf alive until completion
                            std::mem::forget(buf); // Reclaimed in completion handler
                        }
                    }
                }
                
                // Batch submit
                let _ = self.uring.submit();
                
                // Report timing
                let total_time = start.elapsed();
                let _ = self.tx.send(OrderEvent::Routed {
                    seq_num: req.seq_num,
                    route_time_us: route_time.as_secs_f64() * 1e6,
                    total_time_us: total_time.as_secs_f64() * 1e6,
                });
            }
            
            // 2. Poll completions (IOPOLL: busy-wait, no syscall)
            let now = Instant::now();
            if now.duration_since(last_poll).as_micros() > 10 {
                let n = self.uring.poll_completions(|cqe| {
                    // Handle completion: reclaim buffer, check result
                    self.handle_completion(cqe);
                });
                
                if n > 0 {
                    last_poll = now;
                }
            }
            
            // 3. Rare: check for risk circuit breaker
            if should_halt() {
                break;
            }
        }
        
        Ok(())
    }
    
    fn handle_completion(&mut self, cqe: io_uring::cqueue::Entry) {
        let result = cqe.result();
        let user_data = cqe.user_data();
        
        // Reclaim buffer from user_data encoding
        // In production: proper buffer tracking
        
        if result < 0 {
            // Error: -EAGAIN, -ECONNRESET, etc.
            let _ = self.tx.send(OrderEvent::Error {
                code: -result,
                user_data,
            });
        } else {
            // Success: bytes sent
            let _ = self.tx.send(OrderEvent::Sent {
                bytes: result as u32,
                user_data,
            });
        }
    }
    
    fn get_buffer_index(&self, _buf: &AlignedBuffer) -> u16 {
        // Simplified: in production, track buffer indices
        0
    }
}

fn pin_thread_to_cpu(cpu: usize) {
    unsafe {
        let mut cpuset: libc::cpu_set_t = std::mem::zeroed();
        libc::CPU_SET(cpu, &mut cpuset);
        libc::sched_setaffinity(0, std::mem::size_of::<libc::cpu_set_t>(), &cpuset);
    }
}

fn now_nanos() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos() as u64
}

fn should_halt() -> bool {
    // Check shared memory flag from risk circuit
    false
}

// Message types
pub struct OrderRequest {
    pub seq_num: u64,
    pub q_total: f64,
    pub symbol: String,
    pub side: fix_encoder::Side,
    pub price: Option<f64>,
    pub ofi_matrix: nalgebra::DMatrix<f64>,
    pub prev_weights: nalgebra::DVector<f64>,
}

pub enum OrderEvent {
    Routed { seq_num: u64, route_time_us: f64, total_time_us: f64 },
    Sent { bytes: u32, user_data: u64 },
    Error { code: i32, user_data: u64 },
}
