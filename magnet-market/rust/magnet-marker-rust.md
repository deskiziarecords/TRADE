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
## Explicit component

 The original function computes a decay-weighted pointer to a series of prices, where each price's relevance diminishes over time based on an exponential decay function.
Key Changes:

    Function Signature:
        In Rust, we define the function with fn followed by the function name and parameters. The parameters are specified with their types, such as &[f64] for a slice of floating-point numbers and f64 for a single floating-point number.

    Array Handling:
        Python's np.ndarray is replaced with a Rust slice &[f64], which is a reference to a one-dimensional array of 64-bit floating-point numbers. The return type is a Vec<f64>, which is a dynamic array in Rust.

    Age Calculation:
        The age array is created using a range and reversed to mimic the behavior of np.arange(len(prices))[::-1]. In Rust, we use rev() to reverse the range.

    Weight Calculation:
        The weights are computed using an iterator that maps over the age vector, applying the exponential decay formula. The map function in Rust is similar to Python's list comprehensions.

    Final Calculation:
        The final return statement combines the prices and weights using zip and map, multiplying corresponding elements to produce the final weighted prices.
---

## hidden engine

function soul_force into Rust. The original function computes the attractive force exerted by a latent "magnet" field, which is influenced by a gravitational constant ( G ) and an equilibrium price level ( eq ).
Key Changes:

    Function Signature:
        In Rust, we specify the types of the parameters explicitly. Here, ptr is defined as a reference to a one-dimensional array of 64-bit floating-point numbers (&ndarray::Array1<f64>), while eq and G are both f64 types.

    Return Type:
        The return type is also specified as ndarray::Array1<f64>, indicating that the function will return a one-dimensional array of floating-point numbers.

    Array Operations:
        The operation ptr - eq is directly translated to Rust, leveraging the capabilities of the ndarray crate, which allows for element-wise operations similar to NumPy in Python.



---
## windowed-extremum

The provided Python code defines a function windowed_extremum that computes the sliding window maximum or minimum of a given array. The function takes a NumPy array, a window size, and a mode (either "max" or "min") as parameters. It returns a new array of the same shape as the input, with the first window-1 entries filled with NaN values.

In the Rust version, we maintain the same functionality while adhering to Rust's syntax and type system. Here are the key points of the conversion:

    Function Signature: The function signature in Rust uses &Vec<f64> to represent a reference to a vector of floating-point numbers, which is analogous to the NumPy array in Python. The window parameter is of type usize, and mode is a string slice &str.

    Error Handling: Instead of raising exceptions, Rust uses panic! to handle errors when the window size is less than 1 or when the mode is invalid.

    Sliding Window Logic: The sliding window is implemented using a loop that iterates through the input vector. For each position, it creates a slice of the vector corresponding to the current window and computes either the maximum or minimum value based on the specified mode.

    Result Initialization: The result vector is initialized with NaN values using f64::NAN, which is the equivalent of NumPy's NaN in Rust.

    Returning the Result: Finally, the function returns the result vector, which contains the computed extremum values aligned with the original input.\

---

