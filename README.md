# AEGIS: Autonomous Execution & Generalized Intelligence System

<div align="center">

**A Next-Generation, JAX-Accelerated Trading Execution Manifold**

[![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![JAX](https://img.shields.io/badge/JAX-F6A312?style=for-the-badge&logo=jax&logoColor=white)](https://github.com/google/jax)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

##  Overview

**AEGIS** is a high-performance institutional trading engine designed to bridge the gap between high-frequency data ingestion and mathematical execution optimization. It unifies three distinct computational layers into a single, coherent pipeline:

1.  **Hyperion (Rust):** A low-latency data fabric responsible for normalizing fragmented market feeds and managing zero-copy memory transfer.
2.  **Zeta-Flux (JAX):** A scalping engine that utilizes Order Flow Imbalance (OFI) to extract alpha signals from microstructure noise.
3.  **Adelic-Mandra-Schur Manifold (JAX):** An execution layer that applies "Causal Truth Gating," Lipschitz-continuous risk management, and Schur-complement routing to optimize block trades across dark pools.

### Core Innovation
The system utilizes **Custom JAX Primitives** to enforce mathematical constraints (Causal Verification & Adelic Tubes) directly on the GPU, ensuring that execution stability is mathematically guaranteed rather than heuristically applied.

---

##  Architecture

The pipeline is strictly separated into **System-Level** (Rust) and **Math-Level** (Python/JAX) domains.

```text
[Market Exchanges]          (UDP/TCP Feeds)
        ↓
[Hyperion Ingestor]         (Rust - Kernel Bypass & Normalization)
        ↓
[Time-Bucketizer]           (Rust - Async Stream → Synchronous Tensor)
        ↓
[Shared Memory IPC]          (Zero-Copy Transfer)
        ↓
[Zeta-Flux Scalper]         (JAX - OFI Signal Gen & Confidence Scoring)
        ↓
[Adelic Manifold]           (JAX - Verification, Kelly/CVaR Risk, Schur Routing)
        ↓
[Execution Dispatcher]      (Python - FIX Protocol / REST API)
        ↓
[Venues]                    (Execution)
```

### Component Breakdown

| Component | Language | Role | Key Tech |
|-----------|----------|------|----------|
| **Hyperion** | Rust | Data Ingestion | `tokio`, `rdma`, `shared_memory` |
| **Zeta-Flux** | Python/JAX | Alpha Generation | `OFI`, `Sigmoid Gates`, `vmap` |
| **Adelic Manifold** | Python/JAX | Execution & Risk | `XLA`, `Conjugate Gradient`, `Kelly Criterion` |

---

## Key Features

*   **Causal Truth Gating:** A custom JAX primitive that mathematically prevents "look-ahead bias" and hallucinations in the signal path.
*   **Zero-Copy Pipeline:** Data moves from the network card to the GPU tensor without CPU serialization overhead.
*   **Adelic Verification:** Formal containment proofs ($\|y^\alpha\| < \|\rho\|$) ensure signals stay within stable bounds.
*   **Schur Complement Routing:** Solves optimal block allocation across fragmented liquidity venues in $O(\log N)$ time.
*   **UV-Powered Workflow:** Uses `uv` for instant dependency resolution and virtual environment management.

---

## Quick Start

### Prerequisites
*   **Rust** (1.70+)
*   **Python** (3.11+)
*   **CUDA** (12.2+) & cuDNN (for GPU acceleration)
*   **uv** (The Python package installer)
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/your-org/aegis-trading-system.git
    cd aegis-trading-system
    ```

2.  **Build the System**
    The `Makefile` handles both Rust compilation and Python environment setup via `uv`.
    ```bash
    make build
    ```
    *This runs `cargo build --release` and `uv sync` automatically.*

3.  **Configuration**
    Copy the environment template and add your API keys:
    ```bash
    cp .env.example .env
    # Edit .env with your exchange credentials
    ```

### Running AEGIS

To start the full pipeline (Ingestor + Engine + Execution):

```bash
make run
```

To run only the Python/JAX engine (for testing/backtesting):

```bash
uv run python -m aegis.main
```

---

##  Development Workflow

We use `uv` to manage the Python environment. You do not need to manually activate a venv.

### Running Tests
```bash
# Unit tests for JAX logic
uv run pytest trading_engine/tests/

# Rust tests
cd hyperion && cargo test
```

### Code Formatting
```bash
# Format Python (Ruff) & Rust
make fmt
```

### Adding Dependencies
```bash
# Add a Python dependency (e.g., polars)
uv add polars

# Add a Rust dependency (via Cargo)
cd hyperion && cargo add tokio-util
```

---

## Configuration

### Tensor Shapes
The system expects input tensors normalized to `[-1, 1]` with the following shape:
*   **Input:** `(Batch, Assets, Depth, Features)`
    *   `Batch`: Dynamic (typically 8-64)
    *   `Assets`: Fixed (e.g., 32)
    *   `Depth`: Order book depth (e.g., 10 levels)
    *   `Features`: 4 (Bid Price, Bid Vol, Ask Price, Ask Vol)

### Risk Parameters
Located in `trading_engine/aegis/config/settings.py`:
```python
ADELIC_TUBE_RADIUS = 0.05
KELLY_FRACTION_LIMIT = 0.02
CVAR_THRESHOLD = 0.95
```

---

## 🐳 Docker Deployment

AEGIS includes multi-stage Dockerfiles optimized for production.

```bash
# Build the images
docker-compose build

# Run the stack
docker-compose up -d
```

*Note: The Dockerfile utilizes `uv` for extremely fast layer caching during builds.*

---

##  License

Distributed under the MIT License. See `LICENSE` for more information.

##  Contributing

Contributions are welcome! Please ensure all tests pass and code is formatted via `make fmt` before submitting a PR.

---

**Built for the future of algorithmic trading.**
