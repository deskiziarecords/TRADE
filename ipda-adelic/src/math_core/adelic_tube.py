"""Adelic Tube Refinement - Enforces Logical Viscosity."""
import jax.numpy as jnp

def apply_logical_viscosity(signal_density: float, rho_bound: float) -> float:
    """Bounds informational density (|y^alpha| < |rho|)."""
    return float(jnp.clip(signal_density, -rho_bound, rho_bound))
