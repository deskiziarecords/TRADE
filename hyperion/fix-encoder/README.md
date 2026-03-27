```
rust/
├── fix_encoder/
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs          # Public API
│   │   ├── message.rs      # FIX message types
│   │   ├── encoder.rs      # Zero-copy encoding
│   │   ├── decoder.rs      # Fast validation
│   │   ├── checksum.rs     # SIMD CRC32
│   │   └── sofh.rs         # Simple Open Framing Header (FIXP)
│   └── benches/
│       └── fix_bench.rs
```
## Expected Performance

```
| Metric              | Single Message | Batch (100)   | Notes                 |
| ------------------- | -------------- | ------------- | --------------------- |
| **Encode latency**  | ~350 ns        | ~35 μs total  | Zero-copy, stack only |
| **Throughput**      | ~2.8M msg/sec  | ~2.8M msg/sec | Sustained             |
| **Buffer reuse**    | 0 alloc        | 0 alloc       | Pre-allocated 4KB     |
| **Checksum (SIMD)** | ~50 ns         | ~5 μs total   | 32-byte vectors       |
| **SOFH framing**    | ~20 ns         | ~2 μs total   | Big-endian write      |
```
---
##  Integration with schur-engine

``` rs
use schur_engine::{SchurRouter, RoutingResult};
use fix_encoder::{FixEncoder, NewOrderSingle, Side, OrdType, TimeInForce};

pub struct ExecutionPipeline {
    router: SchurRouter,
    encoder: FixEncoder<4096>,
    venues: Vec<VenueConfig>,
}

impl ExecutionPipeline {
    pub fn execute(
        &mut self,
        q_total: f64,
        symbol: &str,
        side: Side,
        price: Option<f64>,
    ) -> Vec<(u32, Vec<u8>)> { // (venue_id, fix_message)
        
        // 1. Route optimization
        let route = self.router.optimize(q_total, &ofi_matrix, &prev_weights);
        
        // 2. Encode per venue
        let mut messages = Vec::with_capacity(route.weights.len());
        
        for (i, (&weight, &qty)) in route.weights.iter().zip(&route.quantities).enumerate() {
            if weight < 0.001 { // Skip negligible
                continue;
            }
            
            let order = NewOrderSingle {
                cl_ord_id: self.generate_cl_ord_id(),
                symbol: symbol.into(),
                side,
                order_qty: (qty * 1e8) as i64, // Scale to FIX decimal
                ord_type: if price.is_some() { OrdType::Limit } else { OrdType::Market },
                price: price.map(|p| (p * 1e8) as i64),
                time_in_force: TimeInForce::IOC,
                transact_time: now_nanos(),
            };
            
            let fix_msg = self.encoder.encode_order_venue(&order, i as u32, &mut self.encoder);
            messages.push((i as u32, fix_msg.to_vec()));
        }
        
        messages
    }
}
```
## Build and Deploy

``` bash
cd rust/fix_encoder
cargo build --release
cargo bench

# Python bindings with PyO3
maturin build --release

# Deploy
scp target/release/libfix_encoder.so rpd@colo:/opt/rpd/rust/
```
