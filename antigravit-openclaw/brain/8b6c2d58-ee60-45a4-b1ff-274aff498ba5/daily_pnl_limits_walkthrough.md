# Daily P&L Limits - Implementation Walkthrough

## Overview

Implemented **daily P&L limit enforcement** as the highest-priority recommendation from the trading capability analysis. This prevents runaway losses by automatically halting trading when daily losses exceed a configured threshold.

---

## Changes Made

### 1. [config.py](file:///c:/Users/rovie%20segubre/btc_15min_options_bot/config.py)

Added new configuration options:

```python
# Daily P&L Limits - Trading halt when daily loss exceeds threshold
DAILY_PNL_LIMIT_ENABLED: bool = True       # Enable/disable the feature
DAILY_PNL_LOSS_LIMIT: float = -50.0        # Max daily loss in USDC
DAILY_PNL_PROFIT_LIMIT: float = 100.0      # Max daily profit (optional)
DAILY_PNL_ENABLE_PROFIT_LIMIT: bool = False  # Enable profit limit
DAILY_PNL_RESET_HOUR_UTC: int = 0          # Reset hour (0 = midnight UTC)
```

---

### 2. [main_bot_optimized.py](file:///c:/Users/rovie%20segubre/btc_15min_options_bot/main_bot_optimized.py)

#### `can_trade()` - Complete rewrite (lines 997-1034)

**Before:**
```python
def can_trade(self, market_slug: str) -> bool:
    """Check if we can place a new trade"""
    # No limits - allow unlimited trading
    return True
```

**After:**
- Checks `MAX_DAILY_TRADES` limit
- Checks `DAILY_PNL_LOSS_LIMIT` when enabled
- Checks optional `DAILY_PNL_PROFIT_LIMIT`
- Calls `_check_daily_reset()` for automatic daily reset

#### `_check_daily_reset()` - New method (lines 1036-1060)

Automatically resets `daily_pnl` and `daily_trades` when crossing into a new trading day based on `DAILY_PNL_RESET_HOUR_UTC`.

#### `record_pnl()` - New method (lines 1062-1070)

Centralized P&L recording with consistent logging:
```python
def record_pnl(self, pnl_amount: float, context: str = "trade"):
    """Record P&L from a trade or exit, updating daily totals."""
    self.daily_pnl += pnl_amount
    print(f"[P&L] {context}: ${pnl_amount:+.2f} | Daily total: ${self.daily_pnl:+.2f}")
```

#### `_record_exit()` - Updated (line 2158)

Now uses `record_pnl()` for consistent tracking instead of direct assignment.

---

### 3. [.env.example](file:///c:/Users/rovie%20segubre/btc_15min_options_bot/.env.example)

Added documentation for the new settings.

---

## Usage

### Enable Daily P&L Limits (default: ON)

The feature is **enabled by default**. To configure:

```env
# In .env file
DAILY_PNL_LIMIT_ENABLED=true
DAILY_PNL_LOSS_LIMIT=-50.0      # Stop at $50 loss
DAILY_PNL_RESET_HOUR_UTC=0      # Reset at midnight UTC
```

### Disable (for testing/debugging)

```env
DAILY_PNL_LIMIT_ENABLED=false
```

### Enable Profit Target (optional)

Take profits and stop trading after reaching a daily profit goal:

```env
DAILY_PNL_ENABLE_PROFIT_LIMIT=true
DAILY_PNL_PROFIT_LIMIT=100.0    # Stop at $100 daily profit
```

---

## Behavior Summary

| Condition | Result |
|-----------|--------|
| `daily_trades >= MAX_DAILY_TRADES` | Trading halted |
| `daily_pnl <= DAILY_PNL_LOSS_LIMIT` | Trading halted with warning |
| `daily_pnl >= DAILY_PNL_PROFIT_LIMIT` (if enabled) | Trading halted with success message |
| New trading day detected | Stats reset, trading resumes |

---

## Verification

✅ **Syntax checks passed** for both `config.py` and `main_bot_optimized.py`

```bash
python -m py_compile config.py           # Exit code: 0
python -m py_compile main_bot_optimized.py  # Exit code: 0
```

---

## Example Console Output

When loss limit is reached:
```
[STOP] Daily loss limit reached: $-52.35 <= $-50.00
       Trading halted until daily reset. Manual override: set DAILY_PNL_LIMIT_ENABLED=false
```

When daily reset occurs:
```
[RESET] Daily P&L stats reset (new trading day)
        Previous: $-52.35 P&L, 23 trades
        Daily stats initialized at 2026-01-28T00:00:00+00:00
```

When P&L is recorded:
```
[P&L] exit UP: $+3.45 | Daily total: $+12.80
```
