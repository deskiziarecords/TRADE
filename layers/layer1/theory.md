

## Layer 1: The Compiler (IPDA) — Explicit State Machine

### Formal Definition

The Compiler defines the **valid address space** and **structural decision nodes** that all other layers reference. It operates on three lookback windows (20, 40, 60 periods) and maintains a phase state that determines what actions are "legal" at any given time.

---

### State Space

```
S_compiler ∈ {ACCUMULATION, MANIPULATION, DISTRIBUTION, INVALID}
```

| State | Symbol | Meaning |
|-------|--------|---------|
| ACCUMULATION | `A` | Price consolidating within range; institutions building positions |
| MANIPULATION | `M` | Price sweeps beyond range to harvest liquidity |
| DISTRIBUTION | `D` | Price expanding directionally; positions being exited |
| INVALID | `I` | Range structure broken; compiler cannot provide valid context |

---

### Observable State Variables

```
Range_20 = [H20, L20, Mid20]
Range_40 = [H40, L40, Mid40]
Range_60 = [H60, L60, Mid60]

Equilibrium = mean(H60, L60, H40, L40, H20, L20)

Phase_History = [S_{t-3}, S_{t-2}, S_{t-1}, S_t]
```

---

### Transition Conditions

#### ACCUMULATION → MANIPULATION
```
Trigger = (Price touches Range_60 boundary) 
          OR (Time_in_Accumulation > τ_max)
          OR (Volume collapses to < 0.5·Avg_Volume for 5 bars)
```

#### MANIPULATION → DISTRIBUTION
```
Trigger = (Sweep_Complete) AND (Displacement_Detected)
Sweep_Complete = (Price exceeds Range_60 boundary by > 0.3·ATR)
Displacement_Detected = (Close > Range_60 boundary) OR (Close < Range_60 boundary)
```

#### MANIPULATION → ACCUMULATION (Failed Sweep)
```
Trigger = (Sweep_Fails) AND (Returns_Inside_Range)
Sweep_Fails = (Price exceeds boundary by < 0.15·ATR)
Returns_Inside_Range = (Close between L60 and H60)
```

#### DISTRIBUTION → ACCUMULATION (Cycle Complete)
```
Trigger = (Price retraces to Range_60 equilibrium) 
          OR (Volume drops to < 0.6·Avg_Volume)
          OR (Time_in_Distribution > τ_max_distribution)
```

#### ANY STATE → INVALID
```
Trigger = (Price breaks ALL ranges simultaneously)
          OR (Range_60 width expands > 2.5·Historical_Range_Width)
          OR (Central_Bank_Override = True)
```

#### INVALID → ACCUMULATION (Recovery)
```
Trigger = (Price establishes new 60-period range)
          AND (Range_60 width normalized)
          AND (No_Central_Bank_Override for 5 periods)
```

---

### Outputs to Other Layers

| Output | Symbol | Destination | Format |
|--------|--------|-------------|--------|
| Current Phase | `S_compiler` | All layers | Categorical |
| Range Boundaries | `H60, L60, H40, L40, H20, L20` | Memory, Collector | Float array |
| Equilibrium | `E = mean(H60, L60)` | All layers | Float |
| Range Validity | `V = 1 if S ≠ I else 0` | All layers | Boolean |
| Phase Transition Flag | `ΔS = 1 if S_t ≠ S_{t-1} else 0` | All layers | Boolean |

---

### Internal Metrics for Metacognition

The Compiler also produces metrics that other layers use to assess *its* reliability:

```
Range_Coherence = 1 - (StdDev(Range_Width_{t-20:t}) / Mean(Range_Width))
Phase_Naturalness = 1 if (A→M→D sequence) else 0.5 if (A→M→A) else 0
Compiler_Confidence = Range_Coherence · Phase_Naturalness
```

When `Compiler_Confidence` drops below 0.4, other layers should:
- **Memory**: Freeze hidden state updates
- **Collector**: Reduce sweep aggression
- **Amplifier**: Cap gamma exposure
- **Privileged**: (already overriding)

---

### State Machine Diagram (Text Representation)

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
              ┌───────────┐                               │
              │  INVALID  │                               │
              └───────────┘                               │
                    ▲                                     │
                    │ Recovery                             │
                    │                                     │
     ┌──────────────┴──────────────┐                      │
     │                              │                      │
     ▼                              ▼                      │
┌───────────┐                ┌───────────┐                │
│ACCUMULATION├───────────────►│MANIPULATION│               │
└───────────┘                └───────────┘                │
     ▲                              │                      │
     │                              │                      │
     │     Failed Sweep              │ Displacement        │
     │                              ▼                      │
     │                        ┌───────────┐                │
     └────────────────────────┤DISTRIBUTION│               │
                              └───────────┘                │
                                    │                      │
                                    │ Cycle Complete      │
                                    └──────────────────────┘
```

---

### Implementation Skeleton

```python
class IPDACompiler:
    """Layer 1: The Compiler - Defines valid address space and phase state"""
    
    def __init__(self, lookbacks=[20, 40, 60]):
        self.lookbacks = lookbacks
        self.state = 'INVALID'
        self.state_history = []
        self.ranges = {lb: {'high': None, 'low': None, 'mid': None} for lb in lookbacks}
        self.equilibrium = None
        self.confidence = 0.0
        
    def update(self, price_data: dict, external_overrides: dict) -> dict:
        """
        Update compiler state based on new price data
        
        Args:
            price_data: {'high': float, 'low': float, 'close': float, 'volume': float}
            external_overrides: {'central_bank_active': bool}
            
        Returns:
            outputs: dict with state, ranges, equilibrium, validity, transition
        """
        # Update range calculations
        self._update_ranges(price_data)
        
        # Check for invalidation
        if self._check_invalidation(price_data, external_overrides):
            self._transition_to('INVALID')
        elif self.state == 'INVALID':
            if self._check_recovery():
                self._transition_to('ACCUMULATION')
        else:
            # Normal state transitions
            self._apply_transition_rules(price_data)
        
        # Update internal metrics
        self._update_confidence()
        
        # Prepare outputs for other layers
        return self._format_outputs()
    
    def _update_ranges(self, price_data):
        """Update rolling high/low for each lookback window"""
        pass
    
    def _check_invalidation(self, price_data, overrides):
        """Check if compiler should enter INVALID state"""
        if overrides.get('central_bank_active', False):
            return True
        
        price = price_data['close']
        # Price breaks ALL ranges simultaneously
        if (price > self.ranges[60]['high'] and 
            price > self.ranges[40]['high'] and 
            price > self.ranges[20]['high']):
            return True
        if (price < self.ranges[60]['low'] and 
            price < self.ranges[40]['low'] and 
            price < self.ranges[20]['low']):
            return True
        
        # Range width explosion
        current_width = self.ranges[60]['high'] - self.ranges[60]['low']
        historical_width = self._historical_width_mean()
        if current_width > 2.5 * historical_width:
            return True
            
        return False
    
    def _apply_transition_rules(self, price_data):
        """Apply state transition logic based on current state"""
        if self.state == 'ACCUMULATION':
            if self._check_manipulation_trigger(price_data):
                self._transition_to('MANIPULATION')
                
        elif self.state == 'MANIPULATION':
            if self._check_distribution_trigger(price_data):
                self._transition_to('DISTRIBUTION')
            elif self._check_failed_sweep(price_data):
                self._transition_to('ACCUMULATION')
                
        elif self.state == 'DISTRIBUTION':
            if self._check_cycle_complete(price_data):
                self._transition_to('ACCUMULATION')
    
    def _check_manipulation_trigger(self, price_data):
        """Check if Accumulation → Manipulation"""
        price = price_data['close']
        # Price touches 60-period boundary
        if price >= self.ranges[60]['high'] or price <= self.ranges[60]['low']:
            return True
        # Time-based trigger
        if self._time_in_state() > 20:  # τ_max
            return True
        # Volume collapse
        if price_data['volume'] < 0.5 * self._avg_volume():
            return True
        return False
    
    def _check_distribution_trigger(self, price_data):
        """Check if Manipulation → Distribution"""
        price = price_data['close']
        sweep_depth = self._sweep_depth(price_data)
        # Sweep complete: exceeds boundary by > 0.3 ATR
        if sweep_depth > 0.3 * self._atr():
            # Displacement detected
            if (price > self.ranges[60]['high'] and 
                price_data['close'] > self.ranges[60]['high']):
                return True
            if (price < self.ranges[60]['low'] and 
                price_data['close'] < self.ranges[60]['low']):
                return True
        return False
    
    def _update_confidence(self):
        """Update compiler's self-assessment"""
        range_coherence = 1 - (self._range_width_std() / self._range_width_mean())
        phase_naturalness = 1.0 if self._is_natural_sequence() else 0.5
        self.confidence = range_coherence * phase_naturalness
    
    def _format_outputs(self):
        """Format outputs for consumption by other layers"""
        return {
            'state': self.state,
            'state_history': self.state_history[-3:],
            'ranges': self.ranges,
            'equilibrium': self.equilibrium,
            'valid': self.state != 'INVALID',
            'transition': self._detect_transition(),
            'confidence': self.confidence
        }
```

---

