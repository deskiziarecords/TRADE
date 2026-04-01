//@version=6
indicator("Adaptive ALMA 3.0 - System", overlay=true, max_bars_back = 1000, timeframe = '', timeframe_gaps = false)

// INPUTS
src = (open + close + close) / 3
//src = input.source(close, "Source")

group_alma = "ALMA Adaptation"
min_len    = input.int(3, "Min. Length", minval=2, group=group_alma, tooltip="Minimum window size for ALMA. Used during high-efficiency trend phases to reduce lag.")
max_len    = input.int(11, "Max. Length", maxval=100, group=group_alma, tooltip="Maximum window size for ALMA. Used during low-efficiency or noisy phases to increase smoothing.")

group_extra = "Additional ALMA Averages"
show_extra  = input.bool(true, "Show Medium & Long ALMAs", group=group_extra, tooltip="Toggle visibility of the Medium and Long term ALMA reference lines.")
med_len     = input.int(50, "Medium Length", minval=1, group=group_extra, tooltip="Period for the Medium-term ALMA.")
med_off     = input.float(0.8, "Medium Offset", step = 0.025, group=group_extra, tooltip="Gaussian offset for the Medium ALMA (0 to 1). Higher values reduce lag.")
med_sig     = input.float(4.0, "Medium Sigma", step = 0.25, group=group_extra, tooltip="Gaussian sigma for the Medium ALMA. Higher values make the filter 'sharper'.")
long_len    = input.int(200, "Long Length", minval=1, group=group_extra, tooltip="Period for the Long-term ALMA.")
long_off    = input.float(0.8, "Long Offset", step = 0.025, group=group_extra, tooltip="Gaussian offset for the Long ALMA.")
long_sig    = input.float(4.0, "Long Sigma", step = 0.25, group=group_extra, tooltip="Gaussian sigma for the Long ALMA.")

group_opt = "Sigma/Offset Dynamics"
min_off = input.float(0.1, "Min. Offset", 0.0, 1.0, step = 0.025, group=group_opt, tooltip="Lowest offset value used when market efficiency is low (smooth phase).")
max_off = input.float(0.35, "Max. Offset", 0.0, 1.0, step = 0.025, group=group_opt, tooltip="Highest offset value used when market efficiency is high (fast-tracking phase).")
min_sig = input.float(2.25, "Min. Sigma", 0.25, step = 0.25, group=group_opt, tooltip="Minimum sigma value for the adaptive engine.")
max_sig = input.float(7.0, "Max. Sigma", 0.5, step = 0.25, group=group_opt, tooltip="Maximum sigma value for the adaptive engine.")

group_evasive = "Global Evasion Engine (Adaptive)"
atr_noise_min   = input.int(2, "Min Noise Period (Adaptive)", minval=2, group=group_evasive, tooltip="Shortest lookback for noise detection during volatile periods.")
atr_noise_max   = input.int(14, "Max Noise Period (Adaptive)", minval=2, group=group_evasive, tooltip="Longest lookback for noise detection during stable periods.")
atr_slow_len    = input.int(200, "Slow ATR (Background)", minval=10, group=group_evasive, tooltip="Lookback period for the baseline market volatility (ATR).")
atr_master_mult = input.float(2.0, "Sensitivity", minval=0.1, step=0.05, group=group_evasive, tooltip="Master multiplier for the trend reversal threshold. Higher values lead to fewer, more confirmed signals.")
use_autotune    = input.bool(true, "Use Auto-Tune Evasion", group=group_evasive, tooltip="Dynamically adjusts the noise threshold based on recent price-to-mean distance.")

group_shift = "Signal Shift"
sig_offset  = input.int(-1, "Arrows Offset (Shift)", minval=-10, maxval=10, group=group_shift, tooltip="Horizontal shift for signal arrows on the chart.")

group_bb     = "BB-ALMA Settings"
bb_src       = input.source(close, "BB Source", group=group_bb, tooltip="Source price for the Bollinger Bands calculation.")
bb_len       = input.int(20, "BB Length", minval=1, group=group_bb, tooltip="Lookback period for the Bollinger Bands.")
bb_offset    = input.float(0.25, "BB ALMA Offset", minval=0, maxval=1, step=0.01, group=group_bb, tooltip="ALMA offset used as the basis for Bollinger Bands.")
bb_sigma     = input.float(1.0, "BB ALMA Sigma", minval=0, group=group_bb, tooltip="ALMA sigma used as the basis for Bollinger Bands.")
bb_mult      = input.float(1.8, "BB Multiplier", minval=0.1, step=0.1, group=group_bb, tooltip="Standard deviation multiplier for the width of the bands.")

// Three.js equivalent of the Pine Script code
// Initialize the scene, camera, and renderer
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
const renderer = new THREE.WebGLRenderer();
renderer.setSize(window.innerWidth, window.innerHeight);
document.body.appendChild(renderer.domElement);

// INPUTS
let src = (open + close + close) / 3; // Equivalent to Pine Script's source calculation

// ALMA Adaptation parameters
let min_len = 3; // Minimum Length
let max_len = 11; // Maximum Length

// Additional ALMA Averages
let show_extra = true; // Show Medium & Long ALMAs
let med_len = 50; // Medium Length
let med_off = 0.8; // Medium Offset
let med_sig = 4.0; // Medium Sigma
let long_len = 200; // Long Length
let long_off = 0.8; // Long Offset
let long_sig = 4.0; // Long Sigma

// Sigma/Offset Dynamics
let min_off = 0.1; // Min. Offset
let max_off = 0.35; // Max. Offset
let min_sig = 2.25; // Min. Sigma
let max_sig = 7.0; // Max. Sigma

// Global Evasion Engine (Adaptive)
let atr_noise_min = 2; // Min Noise Period (Adaptive)
let atr_noise_max = 14; // Max Noise Period (Adaptive)
let atr_slow_len = 200; // Slow ATR (Background)
let atr_master_mult = 2.0; // Sensitivity
let use_autotune = true; // Use Auto-Tune Evasion

// Signal Shift
let sig_offset = -1; // Arrows Offset (Shift)

// BB-ALMA Settings
let bb_src = close; // BB Source
let bb_len = 20; // BB Length
let bb_offset = 0.25; // BB ALMA Offset
let bb_sigma = 1.0; // BB ALMA Sigma
let bb_mult = 1.8; // BB Multiplier
