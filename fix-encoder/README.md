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
