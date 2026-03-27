# In main loop
if mandra.transition_permitted(proposed_sigma, current_sigma, t, phi_seq):
    # Recalculate EV for new regime
    ev_new = ensemble.ev_forecast(proposed_sigma)
    
    # Resize position
    q_new, _ = position_size(
        equity=equity,
        ev_t=ev_new,
        atr_t=atr_current,
        phi_t=phi_current,
        adelic_valid=adelic_check(signal),
        params=regime_params[proposed_sigma]
    )
    
    execute_rebalance(q_new)
else:
    # Mandra blocked: maintain current sizing
    pass
