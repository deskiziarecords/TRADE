use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use fix_encoder::{FixEncoder, NewOrderSingle, Side, OrdType, TimeInForce};
use std::time::{SystemTime, UNIX_EPOCH};

fn bench_encode_new_order_single(c: &mut Criterion) {
    let mut encoder = FixEncoder::<4096>::new("RPD_TRADER", "OANDA");
    
    let order = NewOrderSingle {
        cl_ord_id: "RPD202403240001".into(),
        symbol: "EUR/USD".into(),
        side: Side::Buy,
        order_qty: 150000000000, // 1.5 @ 1e8 scaling
        ord_type: OrdType::Limit,
        price: Some(108000000),    // 1.08000
        time_in_force: TimeInForce::IOC,
        transact_time: SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos() as u64,
    };
    
    c.bench_with_input(
        BenchmarkId::new("encode", "new_order_single"),
        &order,
        |b, order| {
            b.iter(|| {
                encoder.reset();
                black_box(encoder.encode_new_order_single(order))
            })
        },
    );
}

fn bench_encode_batch(c: &mut Criterion) {
    let mut group = c.benchmark_group("batch_encode");
    
    for size in [10, 100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::from_parameter(size),
            size,
            |b, &size| {
                let mut encoder = FixEncoder::<4096>::new("RPD_TRADER", "OANDA");
                let orders: Vec<NewOrderSingle> = (0..size)
                    .map(|i| NewOrderSingle {
                        cl_ord_id: format!("RPD{:012}", i).into(),
                        symbol: "EUR/USD".into(),
                        side: if i % 2 == 0 { Side::Buy } else { Side::Sell },
                        order_qty: 100000000000 + i as i64 * 1000000,
                        ord_type: OrdType::Limit,
                        price: Some(108000000 + i as i64 * 1000),
                        time_in_force: TimeInForce::IOC,
                        transact_time: 1711324800000000000u64 + i as u64 * 1000,
                    })
                    .collect();
                
                b.iter(|| {
                    for order in &orders {
                        encoder.reset();
                        black_box(encoder.encode_new_order_single(order));
                    }
                });
            },
        );
    }
    
    group.finish();
}

criterion_group!(benches, bench_encode_new_order_single, bench_encode_batch);
criterion_main!(benches);
