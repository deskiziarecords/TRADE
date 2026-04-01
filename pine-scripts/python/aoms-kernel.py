# version = 6
# strategy("AOMS Kernel & Reverse Period Detector", shorttitle="RPD_AOMS", overlay=True, initial_capital=100000)

# ──────────────────────────────────────────────────────────────
# 1️⃣ INPUTS & PARAMETERS
# ──────────────────────────────────────────────────────────────
group_core = "AOMS Kernel Settings"
lookback_len = 20  # Lookback Horizon
displacement_k = 1.5  # Displacement Multiplier (k)
veto_threshold = 0.7  # Body/Range Veto (λ6)

group_sensors = "5-Lambda Sensor Array"
gamma_thresh = 0.0  # Temporal Sign Threshold (γ)
phi_limit = 0.6  # Confluence Threshold (φ)
delta_vol = 0.5  # Persistence Failure (δ)

# ──────────────────────────────────────────────────────────────
# 2️⃣ VOLATILITY & STRUCTURAL OPERATORS
# ──────────────────────────────────────────────────────────────
tiny = 0.000000000001  # FIX: Pine v6 has no 1e-12 literal

atr = ta.atr(lookback_len)
range_t = high - low
body_t = abs(close - open)
pvi = ta.sma(abs(close - close[1]), lookback_len)

vol_val = volume * close
vol_stdev = ta.stdev(vol_val, lookback_len)
grad_u = (vol_val - nz(vol_val[1])) / (vol_stdev + tiny)

inst_signature = body_t / (range_t + tiny) > veto_threshold
displacement_valid = (range_t > displacement_k * atr) and inst_signature

# ──────────────────────────────────────────────────────────────
# 3️⃣ REGIME STATE SPACE
# ──────────────────────────────────────────────────────────────
# FIX: use `var` so the variable persists correctly across bars
regime_state = 0.0

h_high = ta.highest(high, lookback_len)
l_low = ta.lowest(low, lookback_len)
box_width = h_high - l_low

if box_width < atr * 1.5:
    regime_state = 0.0
elif (low < nz(l_low[1]) or high > nz(h_high[1])) and not displacement_valid:
    regime_state = 1.0
else:
    regime_state = 2.0

# ──────────────────────────────────────────────────────────────
# 4️⃣ THE 5-LAMBDA SENSOR ARRAY
# ──────────────────────────────────────────────────────────────
# λ1: Phase Entrapment
lambda_1 = regime_state == 2.0 and (pvi / (atr + tiny)) < delta_vol

# λ2: Temporal Alignment Failure
# FIX: cast math.sign() result to float before passing to ta.sma()
rolling_returns_sign = ta.sma(float(math.sign(close - close[1])), lookback_len)
lambda_2 = regime_state == 1.0 and rolling_returns_sign < gamma_thresh

# λ3: Spectral Phase Inversion
# FIX: math.atan2() does not exist in Pine v6 — approximate phase via slope sign
src = hlc3
price_center = src - nz(src[2])
smoothed_pc = ta.sma(price_center, 7)
# Phase proxy: when price_center and its smoothed form disagree in sign → inversion
lambda_3 = (price_center > 0 and smoothed_pc < 0) or (price_center < 0 and smoothed_pc > 0)

# λ4: Confluence Collapse
rsi = ta.rsi(close, 14)
lambda_4 = (rsi > 70 and close < close[1]) or (rsi < 30 and close > close[1])

# λ5: Liquidity Field Inversion
# FIX: wrap both sides in nz() to avoid na propagation on early bars
lambda_5 = (nz(grad_u) * nz(grad_u[1])) < 0

# ──────────────────────────────────────────────────────────────
# 5️⃣ ADELIC COHERENCE & CAUSAL GATE
# ──────────────────────────────────────────────────────────────
rho = 0.5 * ta.stdev(close, 60)
adelic_norm = ta.stdev(close, 5)
is_coherent = adelic_norm < rho

lambda_count = (1 if lambda_1 else 0) + (1 if lambda_2 else 0) + (1 if lambda_3 else 0) + \
               (1 if lambda_4 else 0) + (1 if lambda_5 else 0)
unified_score = lambda_count / 5.0
reverse_trigger = unified_score > 0.6 or not is_coherent

# ──────────────────────────────────────────────────────────────
# 6️⃣ EXECUTION MANIFOLD
# ──────────────────────────────────────────────────────────────
long_signal = (regime_state == 2.0) and displacement_valid and not reverse_trigger and close > nz(h_high[1])
short_signal = (regime_state == 2.0) and displacement_valid and not reverse_trigger and close < nz(l_low[1])

if long_signal:
    strategy.entry("AOMS_LONG", strategy.long, comment="AOMS_COHERENT")

if short_signal:
    strategy.entry("AOMS_SHORT", strategy.short, comment="AOMS_COHERENT")

if reverse_trigger:
    strategy.close_all(comment="RPD_HALT")

# ──────────────────────────────────────────────────────────────
# 7️⃣ VISUALIZATION
# ──────────────────────────────────────────────────────────────
rpd_table = table.new(position.top_right, 2, 6,
     bgcolor=color.new(color.black, 10), border_width=1)

if barstate.islast:
    table.cell(rpd_table, 0, 0, "Regime (σt)", text_color=color.white)
    table.cell(rpd_table, 1, 0, str(regime_state), text_color=color.lime if regime_state == 2.0 else color.yellow)
    table.cell(rpd_table, 0, 1, "AOMS Coherence", text_color=color.white)
    table.cell(rpd_table, 1, 1, "STABLE" if is_coherent else "FRACTURE", text_color=color.lime if is_coherent else color.red)
    table.cell(rpd_table, 0, 2, "RPD Unified Score", text_color=color.white)
    table.cell(rpd_table, 1, 2, str(unified_score), text_color=color.red if reverse_trigger else color.silver)

plotshape(reverse_trigger, "Reverse Trigger", shape.xcross, location.top, color.red, size=size.small)
bgcolor(color.new(color.purple, 90) if not is_coherent else None)
