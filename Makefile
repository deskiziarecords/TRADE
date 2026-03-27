# AEGIS Makefile

# --- Configuration ---
RUST_WORKSPACE := Cargo.toml
PYTHON_WORKSPACE := pyproject.toml

# --- Commands ---
.PHONY: build run test fmt clean help

help:
	@echo "AEGIS: Autonomous Execution & Generalized Intelligence System"
	@echo ""
	@echo "Usage:"
	@echo "  make build    Build the full system (Rust crates & Python environment)"
	@echo "  make run      Run the full pipeline"
	@echo "  make test     Run both Rust and Python tests"
	@echo "  make fmt      Format both Rust and Python code"
	@echo "  make clean    Clean build artifacts"

build:
	@echo "[BUILD] Compiling Rust workspace..."
	cargo build --release
	@echo "[BUILD] Synchronizing Python dependencies via uv..."
	@if command -v uv > /dev/null; then uv sync; else echo "Warning: uv not found, skipping sync."; fi

run:
	@echo "[RUN] Starting AEGIS full pipeline..."
	@echo "[RUN] Note: In production, start Hyperion ingestors followed by Trading Engine."
	PYTHONPATH=trading_engine:trading_engine/aegis python3 -m aegis.main

test:
	@echo "[TEST] Running Rust tests..."
	cargo test
	@echo "[TEST] Running Python tests..."
	PYTHONPATH=trading_engine:trading_engine/aegis pytest trading_engine/tests/

fmt:
	@echo "[FMT] Formatting Rust code..."
	cargo fmt
	@echo "[FMT] Formatting Python code via ruff..."
	@if command -v ruff > /dev/null; then ruff format trading_engine/; else echo "Warning: ruff not found, skipping Python formatting."; fi

clean:
	@echo "[CLEAN] Removing build artifacts..."
	cargo clean
	find . -type d -name "__pycache__" -exec rm -rf {} +
