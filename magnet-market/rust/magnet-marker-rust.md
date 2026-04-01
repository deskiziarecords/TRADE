# Magnet‑Market: A Conceptual‑to‑Code Framework

> **IPDA L20,40,60​**, Windowed Extremum Search, Potential Function Φmag​, …  
> This repository turns the poetic market‑mechanics you described into **executable, testable Python modules**.  
> Think of each file as a *organ* in a living trading system:  
> - **Explicit Component** → *The Body* (observable price‑time series)  
> - **Hidden Engine**   → *The Soul* (latent forces, order‑flow heuristics)  
> - **Synthesized Reality** → The *model* that fuses both into a tradable signal.

---

## Modules at a Glance

```

| Module | Concept (from your list) | Core Idea (short) |
|--------|--------------------------|-------------------|
| `explicit_component.rs` | **The Body** | Raw price‑time series as a pointer into a decaying memory address space. |
| `hidden_engine.rs` | **The Soul** | Latent “magnet” field that pulls price toward equilibrium via a gravitational‑like constant. |
| `synthesized_reality.rs` | **The “Synthesized” Reality** | Fusion layer: combines explicit observations with hidden forces to produce a forecast. |
| `ipda_l20_40_60.rs` | **IPDA L20,40,60​** | Implied Probability Distribution Approximation at 20 %, 40 %, 60 % quantiles – a fast, non‑parametric CDF estimate. |
| `windowed_extremum_search.rs` | **Windowed Extremum Search** | Sliding‑window max/min detection (price as pointer to time‑decayed memory). |
| `potential_function.rs` / `euclidean_vector_attraction.py` | **Φmag​ – Euclidean Vector Attraction** | Price movement = $-\nabla\Phi$ where $\Phi(\mathbf{x}) = \frac{1}{2}k\|\mathbf{x}-\mathbf{x}_0\|^2$. |
| `s_and_d_psi.rs` / `heuristic_pattern_classifier.py` | **S&D ΨS&D​ – Heuristic Pattern Classifier** | Garbage‑collection‑style detection of retail liquidity pools (unallocated RAM). |
| `gamma_amplifier.rs` | **Γ – Second‑Order Feedback Loop** | Amplifies curvature of the potential (second derivative) → exponential acceleration. |
| `spectral_misalignment.rs` | **M – Fourier Phase Analysis** | Detects phase desynchronization in multi‑frequency components → early “knock” warning. |
| `utils/math_helpers.rs` | Small reusable helpers (norms, FFT wrappers, KD‑tree memory). | — |

```
Each module exposes a **single public function** (or class) that returns a numeric signal you can plug into a back‑tester or execution engine.

---


## windowed-extremum

The provided Python code defines a function windowed_extremum that computes the sliding window maximum or minimum of a given array. The function takes a NumPy array, a window size, and a mode (either "max" or "min") as parameters. It returns a new array of the same shape as the input, with the first window-1 entries filled with NaN values.

In the Rust version, we maintain the same functionality while adhering to Rust's syntax and type system. Here are the key points of the conversion:

    Function Signature: The function signature in Rust uses &Vec<f64> to represent a reference to a vector of floating-point numbers, which is analogous to the NumPy array in Python. The window parameter is of type usize, and mode is a string slice &str.

    Error Handling: Instead of raising exceptions, Rust uses panic! to handle errors when the window size is less than 1 or when the mode is invalid.

    Sliding Window Logic: The sliding window is implemented using a loop that iterates through the input vector. For each position, it creates a slice of the vector corresponding to the current window and computes either the maximum or minimum value based on the specified mode.

    Result Initialization: The result vector is initialized with NaN values using f64::NAN, which is the equivalent of NumPy's NaN in Rust.

    Returning the Result: Finally, the function returns the result vector, which contains the computed extremum values aligned with the original input.
