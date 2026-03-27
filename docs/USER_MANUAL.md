# AEGIS: User Manual

Welcome to the **Autonomous Execution & Generalized Intelligence System (AEGIS)**. This manual provides a comprehensive guide on how to use the system, explains the internal architecture, and details the relationships between the files in the newly organized repository.

---

## 1. System Overview

AEGIS is a high-performance, JAX-accelerated institutional trading system designed for low-latency market data ingestion and mathematically-optimized execution. The system is split into two primary domains:

1.  **Hyperion (System-Level, Rust):** A high-performance data fabric responsible for market data ingestion, normalization, and low-latency IPC.
2.  **Trading Engine (Math-Level, Python/JAX):** A sophisticated alpha generation and execution layer that uses JAX for high-performance tensor computations and mathematical verification.

### The Three Computational Layers

*   **Hyperion (Rust):** Low-latency data fabric for fragmented market feeds.
*   **Zeta-Flux (JAX):** Scalping engine for signal generation based on Order Flow Imbalance (OFI).
*   **Adelic Manifold (JAX):** Execution and risk management layer using Adelic Tube Refinement and Schur-complement routing.

---

## 2. Repository Structure

The repository is organized into a clean, modular hierarchy:

```text
aegis-trading-system/
├── hyperion/                # [Rust] System-level components
│   ├── fix-encoder/         # SIMD-accelerated FIX protocol encoder
│   ├── rpd_net/             # io_uring-powered networking and IPC
│   ├── rpd_executor/        # Main execution engine binary (Rust)
│   ├── schur_engine/        # High-performance Schur-routing logic
│   ├── ev-atr/              # EV-ATR confluence calculation demo
│   └── schur/               # Additional Schur-routing demonstrations
│
├── trading_engine/          # [Python/JAX] Math-level components
│   ├── aegis/               # Main Aegis Python package
│   │   ├── adelic_manifold/ # Adelic Tube Refinement & Schur routing
│   │   ├── zeta_flux/       # Signal generation & MTP trajectories
│   │   ├── execution/       # FIX/REST gateways (IPDA/AECABI/UROL)
│   │   ├── risk/            # Governance & risk management hierarchies
│   │   ├── simulators/      # Market simulation scripts
│   │   ├── config/          # Broker and environment configurations
│   │   └── app/             # Dashboard and user-facing applications
│   └── tests/               # Python unit and integration tests
│
├── deployment/              # Docker and Kubernetes configurations
├── scripts/                 # Setup and bootstrap scripts
├── docs/                    # Architectural diagrams and documentation
├── data/                    # Data ingestion and sample data
├── Cargo.toml               # Rust workspace manifest
└── pyproject.toml           # Python dependencies and workspace config
```

---

## 3. How to Use AEGIS

### Prerequisites

*   **Rust (1.77+):** For building the Hyperion components.
*   **Python (3.11+):** For the Trading Engine.
*   **CUDA (12.2+) & cuDNN:** For JAX GPU acceleration.
*   **uv:** For managing Python dependencies.

### Installation

1.  **Build the entire system:**
    ```bash
    make build
    ```
    This will compile all Rust crates in the workspace and synchronize Python dependencies via `uv sync`.

2.  **Configure your environment:**
    Copy the example environment file and add your credentials:
    ```bash
    cp .env.example .env
    ```

### Running the System

To start the full pipeline (Ingestor + Engine + Execution):
```bash
make run
```

To run only the Python engine (for testing or backtesting):
```bash
PYTHONPATH=trading_engine uv run python -m aegis.main
```

---

## 4. Component Relationships & Data Flow

### From Market to Signal

1.  **Market Exchange:** UDP/TCP market data feeds are ingested by **Hyperion** via `rpd_net`, which uses `io_uring` for extremely low-latency I/O.
2.  **Time-Bucketizer:** Raw market data is transformed into synchronous tensors.
3.  **Signal Generation:** The **Zeta-Flux** layer (`trading_engine/aegis/zeta_flux/`) processes these tensors to generate alpha signals. It uses Multi-Token Prediction (MTP) to forecast future trajectories.
4.  **Verification:** Signals are passed to the **Adelic Manifold** (`trading_engine/aegis/adelic_manifold/`). This layer uses custom JAX primitives to enforce "Adelic Tube" containment, ensuring the signal is mathematically stable.

### From Signal to Execution

5.  **Schur Routing:** If a signal is valid, the **Schur-complement routing** algorithm calculates the optimal allocation across fragmented liquidity venues.
6.  **FIX Encoding:** The **FIX Encoder** (`hyperion/fix-encoder/`) generates the FIX messages using SIMD instructions.
7.  **Execution Gateway:** The **AECABI** gateway (`trading_engine/aegis/execution/`) sends the orders to the venue (e.g., via Interactive Brokers).

---

## 5. Development Workflow

### Adding Dependencies

*   **Rust:**
    ```bash
    cd hyperion/<crate-name> && cargo add <dependency>
    ```
*   **Python:**
    ```bash
    uv add <dependency>
    ```

### Running Tests

*   **Rust tests:**
    ```bash
    cargo test
    ```
*   **Python tests:**
    ```bash
    PYTHONPATH=trading_engine pytest trading_engine/tests/
    ```

### Code Formatting

We use standard formatting for both languages:
```bash
# Formats Rust with rustfmt and Python with Ruff
make fmt
```

---

## 6. Deployment

AEGIS is designed for containerized deployment in high-performance environments. The `deployment/docker/` directory contains:
*   **Dockerfile.rust:** Optimized multi-stage build for Hyperion.
*   **Dockerfile.python:** JAX-optimized container for the Trading Engine.

Use `docker-compose up -d` to launch the full stack locally for testing.
