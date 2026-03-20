# IPDA Trading System – Full Pipeline

A production-ready, self-healing IPDA (Interbank Price Delivery Algorithm) trading system
for EUR/USD via Interactive Brokers, built for colocation deployment on Ubuntu 22.04+.

## Architecture

```
IB Gateway (TWS)
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  UROL  –  Reliability & Observability Layer         │
│  • Subscribes EUR/USD 5-min real-time bars          │
│  • MAD outlier filter (z > 3.5 rejected)            │
│  • Publishes clean bars → Redis stream clean:ticks  │
│  • Persists GlobalState every 0.5s (Redis + SQLite) │
│  • Watchdog: reconnects on stale data               │
│  • Kill-switch: halts on 5% daily drawdown          │
└─────────────────────────────────────────────────────┘
      │  clean:ticks
      ▼
┌─────────────────────────────────────────────────────┐
│  IPDA Core  –  Signal Generator                     │
│  • Reads clean bars (Redis consumer group)          │
│  • 20/40/60-day rolling OHLCV buffers               │
│  • Phase detection: ACCUMULATION / MANIPULATION /   │
│    DISTRIBUTION / FLAT                              │
│  • Multi-timeframe confirmation (40+60 day agree)   │
│  • Kill-zone gate: London 07-10 UTC, NY 12-15 UTC  │
│  • ATR-20 volatility-scaled position sizing         │
│  • Publishes signals → Redis stream jax:signals     │
└─────────────────────────────────────────────────────┘
      │  jax:signals
      ▼
┌─────────────────────────────────────────────────────┐
│  AECABI  –  Execution Gateway                       │
│  • TCA filter: edge must be > 3× all-in cost        │
│  • Idempotent order deduplication (SHA-256 trade_id)│
│  • IOC market orders via ib_insync                  │
│  • Shadow engine: every signal → shadow_trades.db   │
│  • Slippage guard (reject if > 2 pips)              │
│  • Emergency flatten on HALT command                │
│  • Exponential back-off IB reconnection             │
└─────────────────────────────────────────────────────┘
      │
      ▼
  logs/shadow_trades.sqlite   (all fills + shadows)
  logs/urol.log / ipda.log / aecabi.log
```

## Directory Layout

```
ipda_system/
├── urol/
│   └── urol.py              ← UROL process
├── ipda_core/
│   └── ipda_core.py         ← IPDA signal generator
├── aecabi/
│   └── aecabi.py            ← execution gateway
├── infra/
│   ├── setup.sh             ← one-shot setup (installs Redis, venv, systemd)
│   └── smoke_test.py        ← pre-flight verification
└── logs/                    ← created automatically
    ├── urol.log
    ├── ipda.log
    ├── aecabi.log
    └── shadow_trades.sqlite
```

## Quick Start

### Step 1 – Run setup (as root/sudo)

```bash
sudo bash infra/setup.sh
```

This installs Redis, creates a Python 3.11 venv at `/opt/ipda_system/venv`,
installs all dependencies, and registers three systemd services.

### Step 2 – Start IB Gateway

Launch IB Gateway (paper account) on your colo box:
- Port: **4002** (paper) or **4001** (live)
- API access: enabled, trusted IPs = 127.0.0.1
- Auto-restart: enabled

### Step 3 – Smoke test

```bash
cd /path/to/ipda_system
/opt/ipda_system/venv/bin/python infra/smoke_test.py
```

All checks should show ✅. The IB check will show ⚠️ if Gateway isn't running yet
(that's fine at this stage).

### Step 4 – Start the pipeline

```bash
sudo systemctl start ipda-urol
sudo systemctl start ipda-core
sudo systemctl start ipda-aecabi
```

Check status:

```bash
sudo systemctl status ipda-urol ipda-core ipda-aecabi
```

### Step 5 – Monitor logs

```bash
# All three in parallel
tail -f logs/urol.log logs/ipda.log logs/aecabi.log

# Shadow fills only
sqlite3 logs/shadow_trades.sqlite \
  "SELECT ts, action, size, fill_price, phase, status FROM fills ORDER BY ts DESC LIMIT 20;"
```

## Config Reference

All config is at the top of each file in a `CONFIG` block.

| Parameter | File | Default | Description |
|-----------|------|---------|-------------|
| `IB_PORT` | urol.py, aecabi.py | 4002 | 4001 = live |
| `ACCOUNT_SIZE` | urol.py, ipda_core.py | $100,000 | Notional equity |
| `RISK_PER_TRADE` | ipda_core.py | 0.01 | 1% per trade |
| `MAX_DAILY_DD` | urol.py | 0.05 | 5% kill-switch |
| `TCA_EDGE_MULT` | aecabi.py | 3.0 | Edge / cost ratio |
| `MAX_SLIPPAGE_PIPS` | aecabi.py | 2.0 | Slippage guard |
| `LOOKBACK_DAYS` | ipda_core.py | [20,40,60] | IPDA look-backs |
| `KILL_ZONES_UTC` | ipda_core.py | [(7,10),(12,15)] | London + NY sessions |
| `BAR_SIZE` | urol.py | "5 mins" | IB bar resolution |

## Going Live

1. Change `IB_PORT = 4001` in `urol/urol.py` and `aecabi/aecabi.py`
2. Change `IB_CLIENT_ID` to values not used by other IB connections
3. Run smoke test again: `python infra/smoke_test.py --skip-ib`
4. Start with tiny size: set `RISK_PER_TRADE = 0.001` (0.1%) initially
5. Monitor shadow PnL vs live PnL in `shadow_trades.sqlite` for 1 week
6. Scale up only after shadow and live track within a few bps

## Extending to More Symbols

Add more symbols to UROL:

```python
# urol/urol.py
SYMBOLS = ["EUR.USD", "GBP.USD", "NQ", "ES"]
```

For futures (ES, NQ), change the contract type:

```python
# In UROL._subscribe() and AECABI.on_signal()
contract = Contract(secType="FUT", symbol="ES",
                    exchange="CME", currency="USD",
                    lastTradeDateOrContractMonth="202506")
```

## Kill-Switch

UROL automatically publishes a `HALT` command to the `control:commands` Redis stream
when daily drawdown exceeds `MAX_DAILY_DD`. AECABI consumes this and flattens all
open positions immediately.

You can also trigger manually:

```bash
redis-cli XADD control:commands '*' command HALT reason manual
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No bars in `clean:ticks` | IB Gateway not running or wrong port | Check `systemctl status ipda-urol` |
| FLAT signals only | Outside kill-zone or insufficient history | Wait for London/NY session; allow 20 days of bars |
| TCA always failing | ATR too small or size too small | Reduce `TCA_EDGE_MULT` to 2.0 for testing |
| IB order rejected | Paper account restrictions | Check IB paper account permissions |
| Redis connection refused | Redis not running | `sudo systemctl start redis-server` |
