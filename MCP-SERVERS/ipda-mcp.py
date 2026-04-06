#!/usr/bin/env python3
"""
IPDA Trading MCP Server
Model Context Protocol server for candlestick pattern trading system
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional, Any

# MCP imports [^13^]
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.lowlevel import Server, NotificationOptions
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, 
    EmbeddedResource, LoggingLevel
)

# Your existing modules (import or embed)
from pattern_rag_pipeline import PatternVectorDB, IPDAPatternValidator
from market_encoder import CandlestickPatternEncoder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ipda_mcp_server")


# ==============================================================================
# GLOBAL STATE (managed via lifespan)
# ==============================================================================

class IPDAServerState:
    """Shared state across MCP server lifespan"""
    
    def __init__(self):
        self.pattern_db: Optional[PatternVectorDB] = None
        self.validator: Optional[IPDAPatternValidator] = None
        self.encoder = CandlestickPatternEncoder()
        self.active_signals: Dict[str, Any] = {}
        self.trade_history: List[Dict] = []
        
    async def initialize(self, db_path: str = "./pattern_vectors"):
        """Initialize vector database and validators"""
        logger.info(f"Initializing IPDA state with DB: {db_path}")
        self.pattern_db = PatternVectorDB(db_path)
        self.validator = IPDAPatternValidator(db_path)
        
    def get_stats(self) -> Dict:
        """Current server statistics"""
        if not self.pattern_db:
            return {"status": "uninitialized"}
        
        db_stats = self.pattern_db.get_stats()
        return {
            "status": "active",
            "database": db_stats,
            "active_signals": len(self.active_signals),
            "trade_history_count": len(self.trade_history),
            "timestamp": datetime.now().isoformat()
        }


# ==============================================================================
# LIFESPAN MANAGEMENT
# ==============================================================================

@asynccontextmanager
async def app_lifespan(server: Server) -> AsyncIterator[IPDAServerState]:
    """
    Manage server lifecycle - initialize on start, cleanup on stop
    [^13^][^17^]
    """
    # Initialize
    state = IPDAServerState()
    await state.initialize()
    
    logger.info("IPDA MCP Server initialized")
    
    try:
        yield state
    finally:
        # Cleanup
        logger.info("IPDA MCP Server shutting down")
        # Persist any pending state if needed


# ==============================================================================
# MCP SERVER SETUP
# ==============================================================================

# Create FastMCP server with lifespan [^13^]
mcp = FastMCP(
    "IPDA Trading System",
    instructions="""
    IPDA (Interbank Price Delivery Algorithm) Trading MCP Server.
    
    Provides tools for:
    - Candlestick pattern analysis and encoding
    - Vector database pattern retrieval (RAG)
    - Trading signal validation
    - Market regime detection
    
    Use encode_candles to convert OHLCV to symbolic patterns (B,X,I,W,w,U,D).
    Use query_patterns to retrieve historical pattern matches from vector DB.
    Use validate_signal to check if a trading signal aligns with pattern history.
    """,
    lifespan=app_lifespan
)


# ==============================================================================
# RESOURCES (Read-only data exposure) [^21^]
# ==============================================================================

@mcp.resource("patterns://stats")
def get_pattern_stats() -> str:
    """
    Current pattern database statistics
    URI: patterns://stats
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    stats = state.get_stats()
    return json.dumps(stats, indent=2)


@mcp.resource("patterns://sequence/{date}/{session}")
def get_pattern_sequence(date: str, session: str) -> str:
    """
    Retrieve pattern sequence for specific date and session
    URI: patterns://sequence/2026-03-19/london_session
    """
    # Look for file
    pattern_file = Path(f"./market_output/*_{date}_{session}_sequence.txt")
    matches = list(Path("./market_output").glob(f"*{date}*{session}*_sequence.txt"))
    
    if not matches:
        return json.dumps({"error": f"No sequence found for {date} {session}"})
    
    with open(matches[0]) as f:
        sequence = f.read()
    
    return json.dumps({
        "date": date,
        "session": session,
        "length": len(sequence),
        "sequence_preview": sequence[:100] + "..." if len(sequence) > 100 else sequence,
        "distribution": dict(Counter(sequence))
    }, indent=2)


@mcp.resource("trading://active_signals")
def get_active_signals() -> str:
    """Currently active trading signals"""
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    return json.dumps(state.active_signals, indent=2, default=str)


# ==============================================================================
# TOOLS (Executable functions) [^21^]
# ==============================================================================

@mcp.tool()
def encode_candles(
    ohlcv_data: List[Dict[str, float]],
    body_threshold: float = 0.0001,
    wick_threshold: float = 0.00015
) -> str:
    """
    Encode OHLCV candlestick data to symbolic pattern sequence.
    
    Args:
        ohlcv_data: List of candles with open, high, low, close, volume
        body_threshold: Minimum body size for strong candles
        wick_threshold: Minimum wick size for long wick detection
    
    Returns:
        JSON with pattern sequence and statistics
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    # Update thresholds if provided
    state.encoder.body_threshold = body_threshold
    state.encoder.wick_threshold = wick_threshold
    
    patterns = []
    for candle in ohlcv_data:
        p = state.encoder.encode(
            candle['open'], candle['high'], 
            candle['low'], candle['close']
        )
        patterns.append(p)
    
    sequence = ''.join(patterns)
    
    # Compute metrics
    dist = Counter(sequence)
    from math import log2
    entropy = -sum((c/len(sequence))*log2(c/len(sequence)) for c in dist.values())
    
    return json.dumps({
        "sequence": sequence,
        "length": len(sequence),
        "distribution": dict(dist),
        "entropy": entropy,
        "mechanical_score": 1 - (dist.get('I', 0) / len(sequence))
    }, indent=2)


@mcp.tool()
def query_patterns(
    pattern_sequence: str,
    context_window: int = 20,
    top_k: int = 5
) -> str:
    """
    Query vector database for similar historical patterns.
    Uses RAG to find matching n-grams and ensemble prediction.
    
    Args:
        pattern_sequence: Current pattern sequence (last N candles)
        context_window: How many recent patterns to use for query
        top_k: Number of matches to retrieve per n-gram size
    
    Returns:
        JSON with ensemble prediction and historical matches
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    if not state.pattern_db:
        return json.dumps({"error": "Pattern database not initialized"})
    
    # Use last N patterns for query
    query_seq = pattern_sequence[-context_window:]
    
    results = state.pattern_db.query(query_seq, n_results=top_k)
    
    return json.dumps({
        "query": query_seq,
        "ensemble_prediction": results.get("ensemble", {}),
        "matches_found": len(results.get("matches", [])),
        "by_ngram": {
            str(n): [
                {
                    "pattern": m.pattern,
                    "predicts": m.next_symbol,
                    "confidence": m.confidence,
                    "distance": m.distance
                }
                for m in matches
            ]
            for n, matches in results.get("by_n", {}).items()
        }
    }, indent=2)


@mcp.tool()
def validate_signal(
    pattern_sequence: str,
    proposed_action: str,
    current_price: float,
    min_confidence: float = 0.6
) -> str:
    """
    Validate trading signal against pattern database.
    Checks if pattern history supports the proposed action.
    
    Args:
        pattern_sequence: Recent pattern sequence (last 20+ candles)
        proposed_action: BUY, SELL, or HOLD
        current_price: Current market price
        min_confidence: Minimum confidence threshold for validation
    
    Returns:
        JSON with validation result and recommendation
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    if not state.validator:
        return json.dumps({"error": "Validator not initialized"})
    
    validation = state.validator.validate_signal(
        pattern_sequence, proposed_action, min_confidence
    )
    
    # Store active signal if valid
    if validation['valid']:
        signal_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{proposed_action}"
        state.active_signals[signal_id] = {
            "action": proposed_action,
            "price": current_price,
            "confidence": validation['confidence'],
            "pattern_agreement": validation['pattern_agreement'],
            "timestamp": datetime.now().isoformat()
        }
    
    return json.dumps(validation, indent=2)


@mcp.tool()
def analyze_regime(
    pattern_sequence: str,
    price_history: List[float]
) -> str:
    """
    Analyze current market regime from patterns and price action.
    Detects chop, trend, algorithmic trading, and exhaustion.
    
    Args:
        pattern_sequence: Pattern sequence to analyze
        price_history: Recent price points for correlation
    
    Returns:
        JSON with regime classification and confidence
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    # Pattern-based regime detection
    recent = pattern_sequence[-60:]  # Last 60 candles
    
    metrics = {
        "entropy": 0.0,
        "mechanical_score": 0.0,
        "trend_strength": 0.0,
        "chop_probability": 0.0
    }
    
    if len(recent) >= 20:
        dist = Counter(recent)
        total = len(recent)
        
        # Entropy
        from math import log2
        metrics["entropy"] = -sum((c/total)*log2(c/total) for c in dist.values())
        
        # Mechanical score (low indecision = algo)
        metrics["mechanical_score"] = 1 - (dist.get('I', 0) / total)
        
        # Trend strength (consecutive runs)
        runs = []
        current_run = 1
        for i in range(1, len(recent)):
            if recent[i] == recent[i-1]:
                current_run += 1
            else:
                runs.append(current_run)
                current_run = 1
        runs.append(current_run)
        metrics["trend_strength"] = max(runs) / len(recent) if runs else 0
        
        # Chop detection (high I, low entropy)
        metrics["chop_probability"] = (
            0.4 * (dist.get('I', 0) / total) + 
            0.3 * (1 - metrics["entropy"] / 2.5) +
            0.3 * (1 - metrics["trend_strength"])
        )
    
    # Regime classification
    if metrics["chop_probability"] > 0.6:
        regime = "CHOP_HIGH"
    elif metrics["mechanical_score"] > 0.8:
        regime = "ALGORITHMIC"
    elif metrics["trend_strength"] > 0.15:
        regime = "TRENDING"
    else:
        regime = "MIXED"
    
    return json.dumps({
        "regime": regime,
        "confidence": 1 - metrics["chop_probability"] if regime != "CHOP_HIGH" else metrics["chop_probability"],
        "metrics": metrics,
        "recommendation": "REDUCE_SIZE" if regime in ["CHOP_HIGH", "ALGORITHMIC"] else "NORMAL"
    }, indent=2)


@mcp.tool()
def ingest_historical_patterns(
    sequence_file: str,
    metadata_tag: Optional[str] = None
) -> str:
    """
    Ingest historical pattern file into vector database.
    
    Args:
        sequence_file: Path to *_sequence.txt file
        metadata_tag: Optional tag (e.g., "london_session", "backtest_2026")
    
    Returns:
        JSON with ingestion statistics
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    if not state.pattern_db:
        return json.dumps({"error": "Database not initialized"})
    
    try:
        meta = {"tag": metadata_tag} if metadata_tag else {}
        state.pattern_db.add_patterns_from_file(sequence_file, meta)
        
        stats = state.pattern_db.get_stats()
        return json.dumps({
            "success": True,
            "file": sequence_file,
            "database_stats": stats
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def get_trade_recommendation(
    symbol: str,
    current_patterns: str,
    account_balance: float,
    risk_per_trade: float = 0.02
) -> str:
    """
    Get complete trade recommendation from pattern analysis.
    Combines validation, regime analysis, and position sizing.
    
    Args:
        symbol: Trading pair (e.g., "EURUSD")
        current_patterns: Recent pattern sequence
        account_balance: Current account balance
        risk_per_trade: Risk percentage per trade (default 2%)
    
    Returns:
        JSON with complete trading recommendation
    """
    ctx = mcp.get_context()
    state = ctx.request_context.lifespan_state
    
    # Query patterns for direction
    rag_results = state.pattern_db.query(current_patterns[-20:]) if state.pattern_db else {}
    ensemble = rag_results.get("ensemble", {})
    predicted = ensemble.get("prediction", "I")
    
    # Determine action from prediction
    bullish = ['B', 'U', 'w']
    bearish = ['X', 'D', 'W']
    
    if predicted in bullish:
        action = "BUY"
        confidence = ensemble.get("confidence", 0.5)
    elif predicted in bearish:
        action = "SELL"
        confidence = ensemble.get("confidence", 0.5)
    else:
        action = "HOLD"
        confidence = 0.0
    
    # Regime check
    regime_result = json.loads(analyze_regime(current_patterns, []))
    
    # Position sizing
    size_multiplier = 1.0
    if regime_result["regime"] == "CHOP_HIGH":
        size_multiplier = 0.5
    elif regime_result["regime"] == "ALGORITHMIC":
        size_multiplier = 0.3
    
    position_size = account_balance * risk_per_trade * size_multiplier * confidence
    
    recommendation = {
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "predicted_next_pattern": predicted,
        "regime": regime_result["regime"],
        "position_size": position_size,
        "size_reason": f"Base risk {risk_per_trade} * confidence {confidence:.2f} * regime mult {size_multiplier}",
        "stop_loss": "BELOW_RECENT_WICK" if action == "BUY" else "ABOVE_RECENT_WICK",
        "reasoning": f"Pattern '{predicted}' suggests {action} with {confidence:.0%} historical confidence"
    }
    
    return json.dumps(recommendation, indent=2)


# ==============================================================================
# PROMPTS (Reusable templates) [^21^]
# ==============================================================================

@mcp.prompt()
def pattern_analysis_prompt(pattern_sequence: str) -> str:
    """
    Generate analysis prompt for pattern sequence
    """
    return f"""
    Analyze this candlestick pattern sequence: {pattern_sequence[-30:]}
    
    Key patterns to look for:
    - 'w' followed by 'B' = bullish rejection confirmed (hammer)
    - 'W' in sequence = rejection of highs (bearish)
    - 'IIII' (4+ I's) = high indecision, reduce exposure
    - 'XB' transition = potential reversal
    - Mechanical score > 0.8 = algorithmic trading detected
    
    Provide:
    1. Immediate directional bias
    2. Confidence level (0-100%)
    3. Key risk levels
    4. Recommended position size adjustment
    """


@mcp.prompt()
def trade_review_prompt(trade_id: str) -> str:
    """
    Review a completed trade
    """
    return f"""
    Review trade {trade_id} using IPDA methodology:
    
    1. Was the pattern sequence supportive of the entry?
    2. Did the RAG prediction match actual outcome?
    3. Was regime detection accurate?
    4. What can be improved for next trade?
    
    Provide specific pattern-based insights.
    """


# ==============================================================================
# MAIN ENTRY
# ==============================================================================

if __name__ == "__main__":
    # Run with stdio transport for Claude/Cursor integration [^13^][^15^]
    # Or use SSE for web/dashboard integration
    
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "sse":
        # Server-Sent Events for HTTP clients [^15^]
        mcp.run(transport="sse", port=8000)
    else:
        # Standard stdio for Claude Desktop [^13^][^18^]
        mcp.run(transport="stdio")
