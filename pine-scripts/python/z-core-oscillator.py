# //@version=5
# indicator("Swing-Level Z-Score Oscillator", shorttitle="Swing Z-Score", overlay=false)

# --- Presets and Input Parameters ---
grp_main = "🌟 Operating Mode"
preset = input.string("Custom", title="Parameter Preset", options=["Short-term", "Standard", "Long-term", "Custom"], group=grp_main)

grp_custom_exec = "⚡ Custom: Pivots"
c_execLeftBars = input.int(10, title="Left Bars", minval=1, group=grp_custom_exec)
c_execRightBars = input.int(10, title="Right Bars", minval=1, group=grp_custom_exec)

grp_custom_other = "🔧 Custom: Other Settings"
c_stdDevLength = input.int(100, title="StdDev Length", minval=2, tooltip="Period to calculate the standard deviation of errors", group=grp_custom_other)
c_pastPivotsCount = input.int(10, title="Past Pivots Count (N)", minval=1, tooltip="Number of past PH/PL used for Z-Score calculation", group=grp_custom_other)

# Parameter assignment based on preset
execLeftBars = 1 if preset == "Short-term" else 20 if preset == "Long-term" else 10 if preset == "Standard" else c_execLeftBars
execRightBars = 1 if preset == "Short-term" else 20 if preset == "Long-term" else 10 if preset == "Standard" else c_execRightBars

stdDevLength = 10 if preset == "Short-term" else 200 if preset == "Long-term" else 100 if preset == "Standard" else c_stdDevLength
pastPivotsCount = 5 if preset == "Short-term" else 20 if preset == "Long-term" else 10 if preset == "Standard" else c_pastPivotsCount

# --- Pivot Detection ---
# Execution Pivots (For origin points of the horizontal lines)
exec_ph = ta.pivothigh(close, execLeftBars, execRightBars)
exec_pl = ta.pivotlow(close, execLeftBars, execRightBars)

# --- Arrays for saving origin pivots ---
Prices = []

# --- Execution: Save Origin Points ---
if exec_ph is not None:
    Prices.append(exec_ph)
    if len(Prices) > pastPivotsCount + 1:
        Prices.pop(0)

if exec_pl is not None:
    Prices.append(exec_pl)
    if len(Prices) > pastPivotsCount + 1:
        Prices.pop(0)

# --- Horizontal Line (Expected Value) Calculation ---
expectedValues = []

Prices_tmp = Prices[:-1]  # Copy Prices excluding the last element
if len(Prices_tmp) > 0:
    for price in Prices_tmp:
        expectedValues.append(price)

expectedPrice = sum(expectedValues) / len(expectedValues) if expectedValues else None

# --- Z-Score (Oscillator Value) Calculation ---
# Basic price for calculation
calcPrice = close

# Error from the horizontal line (expected value)
error = calcPrice - expectedPrice
# Variance of the error (moving average of squared deviations)
variance = sum((error ** 2 for _ in range(stdDevLength))) / stdDevLength  # Simplified moving average
# Standard deviation
stdDev = variance ** 0.5
# Z-Score calculation (how many standard deviations away)
zScore = error / stdDev if stdDev > 0 else 0

# --- Beautiful and Intelligent Gradient UI Rendering ---
blue_core = "#2962ff"  # Deep Blue
blue_edge = "#82b1ff"  # Light Blue
red_core = "#d50000"  # Deep Red
red_edge = "#ff8a80"  # Light Red

vivid_ob = "#00d5ff"
vivid_os = "#ff0062"

# Dynamic gradient color generation based on value
hist_color_pos = gradient_color(zScore, 0, 2.0, blue_edge, blue_core)
hist_color_neg = gradient_color(zScore, -2.0, 0, red_core, red_edge)

# Apply vivid colors when reaching extremes (OB/OS)
zColor = vivid_ob if zScore >= 2.0 else vivid_os if zScore <= -2.0 else hist_color_pos if zScore >= 0 else hist_color_neg

# For Main Line
line_color_pos = gradient_color(zScore, 0, 2.5, blue_edge, blue_core)
line_color_neg = gradient_color(zScore, -2.5, 0, red_core, red_edge)
line_color = line_color_pos if zScore >= 0 else line_color_neg

# Reference lines rendering
hline_plus2 = 2  # "+2 Sigma"
hline_plus1 = 1  # "+1 Sigma"
hline_zero = 0  # "Center Line"
hline_minus1 = -1  # "-1 Sigma"
hline_minus2 = -2  # "-2 Sigma"

# Lightly highlight the normal ±2σ range
highlight_range(hline_plus2, hline_zero, blue_edge)
highlight_range(hline_zero, hline_minus2, red_edge)

# Oscillator rendering
plot(zScore, title="Z-Score Histogram", color=zColor)
plot(zScore, title="Z-Score Line", color=line_color)

# --- Alert Logic ---
alert_ob_up = crossover(zScore, 2.0)
alert_os_down = crossunder(zScore, -2.0)
alert_zero_up = crossover(zScore, 0)
alert_zero_dn = crossunder(zScore, 0)

if alert_ob_up or alert_os_down or alert_zero_up or alert_zero_dn:
    alert("Z-Score Signal change: " + str(zScore))
