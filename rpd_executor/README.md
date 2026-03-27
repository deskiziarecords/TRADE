```
rust/
├── rpd_executor/
│   ├── Cargo.toml
│   └── src/
│       ├── main.rs           # Binary entry
│       ├── lib.rs            # Public API
│       ├── engine.rs         # Core execution loop
│       ├── pipeline.rs       # Schur → FIX → io_uring chain
│       ├── orders.rs         # Order lifecycle management
│       ├── risk_guard.rs     # Real-time circuit breaker
│       └── telemetry.rs      # Latency tracking
```
## Expectedd Performance

```
| Stage                     | Latency | Cumulative           |
| ------------------------- | ------- | -------------------- |
| Adellic filter            | ~50 ns  | ~50 ns               |
| Schur routing             | ~3.8 μs | ~3.85 μs             |
| FIX encoding              | ~350 ns | ~4.2 μs              |
| io\_uring submit (SQPOLL) | ~50 ns  | ~4.25 μs             |
| **End-to-end p50**        | —       | **~4.3 μs**          |
| **End-to-end p99**        | —       | **~5.1 μs**          |
| **Throughput**            | —       | **~230K orders/sec** |

```
