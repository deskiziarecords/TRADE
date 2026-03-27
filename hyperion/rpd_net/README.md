```
rust/
├── rpd_net/
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs          # Public API
│   │   ├── uring.rs        # io_uring core
│   │   ├── socket.rs       # TCP/UDP fast paths
│   │   ├── executor.rs     # Tokio integration
│   │   ├── zero_copy.rs    # Buffer management
│   │   ├── polling.rs      # IOPOLL/SQPOLL modes
│   │   └── timestamps.rs   # Hardware timestamping
│   ├── benches/
│   │   └── net_bench.rs
│   └── examples/
│       └── main_loop.rs
```
## Expected Performance

```
| Component                     | Latency     | Throughput          |
| ----------------------------- | ----------- | ------------------- |
| **Schur routing**             | ~3.8 μs     | 260K routes/sec     |
| **FIX encoding**              | ~350 ns     | 2.8M msg/sec        |
| **io\_uring submit** (SQPOLL) | ~50 ns      | 20M SQE/sec         |
| **Completion poll** (IOPOLL)  | ~100 ns     | 10M CQE/sec         |
| **End-to-end (single venue)** | **~4.2 μs** | **240K orders/sec** |
| **End-to-end (3 venues)**     | **~5.1 μs** | **196K orders/sec** |
```

