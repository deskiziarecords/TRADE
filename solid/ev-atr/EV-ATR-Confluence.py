import jax.numpy as jnp
from functools import partial

@jax.jit
def position_size(
    equity: float,
    ev_t: float,
    atr_t: float,
    atr_ref: float,
    phi_t: float,
    adelic_valid: bool,
    params: dict
) -> tuple[float, dict]:
    """
    EV-ATR-Confluence position sizing.
    
    Returns: (notional_size, diagnostics_dict)
    """
    # Unpack parameters
    lambda_frac = params['lambda_frac']      # 3.0
    beta_vol = params['beta_vol']            # 0.5
    alpha_phi = params['alpha_phi']         # 1.5
    phi_min = params['phi_min']              # 0.60
    f_risk = params['f_risk']                # 0.01
    avg_win = params['avg_win']              # 0.015
    avg_loss = params['avg_loss']            # 0.005 (stop distance)
    l_max = params['l_max']                  # 50.0
    
    # Guard conditions
    valid = (
        (ev_t > 0) & 
        (phi_t >= phi_min) & 
        adelic_valid &
        (atr_t > 0)
    )
    
    # 1. Kelly fraction
    # Add epsilon to prevent div by zero
    f_kelly = ev_t / (lambda_frac * avg_win * avg_loss + 1e-10)
    f_kelly = jnp.clip(f_kelly, 0.0, 1.0)  # Cap at full Kelly
    
    # 2. Volatility attenuation
    g_vol = jnp.power(atr_ref / (atr_t + 1e-10), beta_vol)
    g_vol = jnp.clip(g_vol, 0.1, 1.0)  # Floor at 10% size in extreme vol
    
    # 3. Confluence modulation
    h_conf = jnp.power(phi_t, alpha_phi)
    
    # 4. Base risk amount
    c_max = f_risk * equity
    
    # Combined sizing
    risk_amount = f_kelly * g_vol * h_conf * c_max * valid
    
    # Convert to notional using stop distance
    notional = risk_amount / (avg_loss + 1e-10)
    
    # Leverage cap
    max_notional = l_max * equity
    notional = jnp.clip(notional, 0.0, max_notional)
    
    # Round to lot size (e.g., 1000 units for forex)
    lot_size = params.get('lot_size', 1000)
    units = jnp.floor(notional / lot_size) * lot_size
    
    diagnostics = {
        'f_kelly': f_kelly,
        'g_vol': g_vol,
        'h_conf': h_conf,
        'risk_amount': risk_amount,
        'theoretical_notional': notional,
        'final_units': units,
        'leverage_used': notional / (equity + 1e-10),
        'valid_signal': valid
    }
    
    return units, diagnostics


# Usage example
params = {
    'lambda_frac': 3.0,
    'beta_vol': 0.5,
    'alpha_phi': 1.5,
    'phi_min': 0.60,
    'f_risk': 0.01,
    'avg_win': 0.015,
    'avg_loss': 0.005,
    'l_max': 50.0,
    'lot_size': 1000
}

units, diag = position_size(
    equity=100000.0,
    ev_t=0.0114,      # 1.14%
    atr_t=0.008,      # 0.8%
    atr_ref=0.005,    # 0.5%
    phi_t=0.75,
    adelic_valid=True,
    params=params
)

print(f"Position: {units:,.0f} units")
print(f"Leverage: {diag['leverage_used']:.2f}x")
print(f"Kelly %: {diag['f_kelly']*100:.1f}%")
