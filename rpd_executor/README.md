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
