"""
Risk Governance Hierarchy
Level 4: Hard Circuit Breaker (Drawdown > 12% -> size = 0)
Level 3: Concurrency Limit (Max 3 positions)
Level 2: Volatility Normalization (ATR > 2x avg -> halve exposure)
Level 1: Vector Confluence (Scale risk 0.5x - 2.0x)
"""
from dataclasses import dataclass

@dataclass
class RiskState:
    current_drawdown: float
    active_positions: int
    current_atr: float
    avg_atr: float
    regime_similarity: float

def apply_governance_hierarchy(base_size: float, state: RiskState) -> float:
    # Level 4
    if state.current_drawdown > 0.12: return 0.0
    # Level 3
    if state.active_positions >= 3: return 0.0
    # Level 2
    size = base_size / 2.0 if state.current_atr > (2 * state.avg_atr) else base_size
    # Level 1
    size = size * max(0.5, min(2.0, state.regime_similarity))
    
    return size
