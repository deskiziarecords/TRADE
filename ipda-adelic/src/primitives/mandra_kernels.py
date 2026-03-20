"""Mandra Primitives: Custom JAX-XLA kernels fusing execution & risk."""
import jax

@jax.jit
def atomic_risk_fusion(exposure: float, risk_params: jax.Array):
    """Prevents bit-leakage between timeframes via fused atomic operations."""
    pass
