## Multi-Signal System Overview

### What It Does
A **market state classifier** that analyzes price action through 5 independent lenses to detect trading opportunities and risk conditions.

### How It Works (5 Parallel Detectors)

| Signal | What It Detects | How |
|--------|----------------|-----|
| **Volatility Decay** | Volatility compression (pre-breakout) | ATR falls below 70% of recent levels within 1-3 bars |
| **FVG Asymmetry** | Liquidity imbalances | Unbalanced fair value gaps (bullish vs bearish gaps) over 5-10 bars |
| **Interrupt Score** | Micro-structure anomalies | Weighted combo of order flow, spread, volume features |
| **Sensor Fusion** | Multi-stream confidence | Weighted average of normalized sensors → squash with tanh |
| **OB Predictor** | Overbought extremes | Bar range > 1.5× ATR with cooldown |

### Decision Flow
```
Raw Market Data → 5 Parallel Algorithms → Individual Booleans → Combined Market State
```

Each algorithm produces `true/false`. The system doesn't force a single decision—it gives you **5 independent perspectives** to act on.

---

## Use Cases

### 1. **Mean Reversion Trading**
- **Use signals:** `overbought` + `volatility_decay`
- **Logic:** Overbought + compressing volatility = pending reversal
- **Action:** Short when both fire

### 2. **Breakout Anticipation**
- **Use signals:** `volatility_decay` alone
- **Logic:** Low volatility after high volatility = squeeze building
- **Action:** Place straddle or prepare for directional move

### 3. **Trend Confirmation**
- **Use signals:** `fvg_asymmetry` + `fusion`
- **Logic:** Unfilled gaps in one direction + high sensor confidence = strong trend
- **Action:** Enter in gap direction

### 4. **Risk Avoidance**
- **Use signals:** `interrupt` OR `fvg_asymmetry` (high asymmetry)
- **Logic:** Market micro-structure breaking down or liquidity hunting
- **Action:** Reduce position size or stay flat

### 5. **Portfolio Regime Filter**
- **Use signals:** All 5 aggregated
- **Logic:** Count `true` signals to determine market regime
  - 0-1 true = Normal/Choppy
  - 2-3 true = Trending/Active  
  - 4-5 true = Extreme/Crisis
- **Action:** Scale position sizing based on regime count

### 6. **Entry Timing for Existing Strategies**
- **Use signals:** `volatility_decay` + `fusion`
- **Logic:** Don't enter until volatility compresses AND sensors align
- **Action:** Filter your primary strategy's entries

### 7. **Stop Loss Adjustment**
- **Use signals:** `interrupt` + `overbought`
- **Logic:** If both fire, expect acceleration
- **Action:** Tighten stops or move to breakeven

---

## Simple Integration Example

```rust
let signals = analyzer.analyze_bar(high, low, close, features, sensors, &history);

// Strategy: Short on overbought + volatility decay
if signals.overbought && signals.volatility_decay {
    execute_short(position_size);
}

// Risk: Reduce size if market unstable
let risk_multiplier = match (signals.interrupt, signals.fvg_asymmetry) {
    (true, true) => 0.25,  // High risk
    (true, false) => 0.50, // Moderate risk
    _ => 1.00,             // Normal risk
};
```

---

## Key Advantage

Not a black-box "buy/sell" signal. **Transparent, interpretable, composable**—you decide which combinations matter for YOUR strategy.
