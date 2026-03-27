```
rust/
├── schur_engine/
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs          # Public API
│   │   ├── schur.rs        # Core decomposition
│   │   ├── adelic.rs       # p-adic validation
│   │   ├── simplex.rs       # Projection algorithms
│   │   └── io_uring.rs     # Kernel-bypass execution
│   └── benches/
│       └── schur_bench.rs
