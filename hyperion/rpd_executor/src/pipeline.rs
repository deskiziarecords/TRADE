//! Composable pipeline stages for order processing

use futures::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};

/// Pipeline stage trait
pub trait PipelineStage<Input, Output> {
    fn process(&self, input: Input) -> impl Future<Output = Option<Output>>;
}

/// Concrete stages

pub struct AdellicFilter;

impl PipelineStage<OrderSignal, OrderSignal> for AdellicFilter {
    async fn process(&self, input: OrderSignal) -> Option<OrderSignal> {
        if input.adelic_valid {
            Some(input)
        } else {
            None
        }
    }
}

pub struct SchurStage {
    router: Arc<RwLock<SchurRouter>>,
}

impl PipelineStage<OrderSignal, RoutedOrder> for SchurStage {
    async fn process(&self, input: OrderSignal) -> Option<RoutedOrder> {
        let router = self.router.read().await;
        let ofi = build_ofi_matrix(&input.venues);
        let prev = get_prev_weights(&input.symbol).await;
        
        let start = Instant::now();
        let routing = router.optimize(input.equity, &ofi, &prev);
        let route_time = start.elapsed();
        
        Some(RoutedOrder {
            signal: input,
            routing,
            route_time_ns: route_time.as_nanos() as u64,
            encode_time_ns: 0,
        })
    }
}

pub struct FixEncodeStage {
    encoder: Arc<Mutex<FixEncoder<4096>>>,
}

impl PipelineStage<RoutedOrder, EncodedOrder> for FixEncodeStage {
    async fn process(&self, mut input: RoutedOrder) -> Option<EncodedOrder> {
        let encoder = self.encoder.lock();
        let start = Instant::now();
        
        let mut packets = Vec::new();
        for (i, (&weight, &qty)) in input.routing.weights.iter().zip(&input.routing.quantities).enumerate() {
            if weight < 0.001 { continue; }
            
            let order = NewOrderSingle { /* ... */ };
            let fix = encoder.encode_new_order_single(&order);
            
            packets.push(VenuePacket {
                venue_id: i as u32,
                fix_data: fix.to_vec(), // In production: zero-copy
            });
        }
        
        input.encode_time_ns = start.elapsed().as_nanos() as u64;
        
        Some(EncodedOrder {
            routed: input,
            packets,
        })
    }
}

pub struct IouringSubmitStage {
    uring: Arc<Mutex<TradingUring>>,
    sockets: Vec<FastTcp>,
}

impl PipelineStage<EncodedOrder, SubmittedOrder> for IouringSubmitStage {
    async fn process(&self, input: EncodedOrder) -> Option<SubmittedOrder> {
        let mut uring = self.uring.lock();
        let start = Instant::now();
        
        for packet in &input.packets {
            let sqe = self.sockets[packet.venue_id as usize]
                .send_sqe(0, packet.fix_data.len() as u32, 0);
            
            unsafe {
                let mut sq = uring.ring.submission();
                if let Some(slot) = sq.next() {
                    *slot = sqe.build();
                }
            }
        }
        
        let _ = uring.submit();
        
        Some(SubmittedOrder {
            encoded: input,
            submit_time_ns: start.elapsed().as_nanos() as u64,
        })
    }
}
