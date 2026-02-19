# BTC Options Bot - Codebase File Analysis

## Summary

This analysis identifies which files are **required** versus **not required** when running the bot via:
- `run_test_mode.bat`
- `Run_both_bots.bat`

Both batch files execute the same two Python scripts:
1. **`main_bot_optimized.py`** - The main trading bot
2. **`order_cancellation_bot.py`** - Order cancellation monitoring

---

## Entry Point Analysis

### `run_test_mode.bat`
```batch
# Runs:
python order_cancellation_bot.py
python main_bot_optimized.py --test
```

### `Run_both_bots.bat`
```batch
# Runs:
python order_cancellation_bot.py
python main_bot_optimized.py
```

---

## Files REQUIRED for Bot Operation

### Core Modules (Directly Imported)

| File | Purpose | Imported By |
|------|---------|-------------|
| `config.py` | Configuration & environment variables | All modules |
| `main_bot_optimized.py` | Main trading bot logic (3700+ lines) | Entry point |
| `order_cancellation_bot.py` | Limit order timeout & cancellation | Entry point |
| `order_cancellation_integration.py` | Integration layer for order tracking | main_bot_optimized |
| `module2_market_orchestrator.py` | Market discovery via Gamma API | main_bot_optimized |
| `module3_pricing_engine.py` | Fair value pricing (Black-Scholes) | main_bot_optimized, module4 |
| `module4_execution_engine.py` | CLOB order execution | main_bot_optimized |
| `fast_price_fetcher.py` | BTC price fetching with caching | main_bot_optimized |
| `websocket_price_fetcher.py` | Real-time Binance WebSocket prices | fast_price_fetcher |
| `calculate_volatility.py` | Volatility/sigma calculations | main_bot_optimized |
| `indicator_filters.py` | Technical indicators (RSI, BB, ATR, etc.) | main_bot_optimized |
| `amplification_strategies.py` | Edge amplification strategies (3600+ lines) | main_bot_optimized |
| `polymarket_orderbook_websocket.py` | Polymarket order book WebSocket | main_bot_optimized |
| `binance_ofi_logger.py` | Binance order flow imbalance | amplification_strategies |
| `module1_chainlink_harvester.py` | Chainlink price lookups | fast_price_fetcher |
| `allowance_utils.py` | ERC-20 allowance helpers | module4_execution_engine |
| `utils.py` | Trade logging utilities | main_bot_optimized |

### Data Files (Required)

| File | Purpose |
|------|---------|
| `.env` | Environment variables (API keys, wallet, config) |
| `active_orders.json` | Shared order tracking between bots |
| `cancel_signals.json` | Cancel signal communication |
| `model_parameters.json` | Volatility model parameters |
| `test_mode_state.json` | Test mode simulator state (created at runtime) |
| `test_cancelled_orders.json` | Test mode cancellation signals |

### Required Directories

| Directory | Purpose |
|-----------|---------|
| `py_clob_client/` | Polymarket CLOB client library |

---

## Files NOT REQUIRED for Bot Operation

### Standalone Scripts (Utility/Testing)

These are standalone utility scripts that are **NOT imported** by the main bot:

| File | Purpose | Why Not Needed |
|------|---------|----------------|
| `main_bot.py` | Original/legacy main bot | Superseded by `main_bot_optimized.py` |
| `analyze_market_structure.py` | Market analysis script | Standalone utility |
| `binance_ofi.py` | Standalone Binance OFI testing | Not imported (uses `binance_ofi_logger.py` instead) |
| `check_config.py` | Config verification script | Standalone utility |
| `check_markets.py` | Market checking script | Standalone utility |
| `debug_velocity.py` | Velocity debugging | Standalone utility |
| `direct_market_query.py` | Direct market query tool | Standalone utility |
| `example_cancellation_bot_timing.py` | Timing example | Documentation/example |
| `fetch_specific_market.py` | Market fetching tool | Standalone utility |
| `final_update.py` | One-time update script | Standalone utility |
| `find_active_15min_markets.py` | Market discovery tool | Standalone utility |
| `fix_encoding.py` | Encoding fix utility | One-time utility |
| `inspect_sampling_markets.py` | Market inspection | Standalone utility |
| `safe_update_method.py` | Update method testing | Standalone utility |
| `search_15min_markets.py` | Market search tool | Standalone utility |
| `search_btc_15min.py` | BTC market search | Standalone utility |
| `sigma_method_demo.py` | Sigma method demonstration | Demo script |
| `switch_sigma.py` | Sigma switching tool | Standalone utility |
| `update_market_discovery.py` | Market discovery update | Standalone utility |
| `update_module2.py` | Module 2 update script | One-time utility |
| `polymarket_rtds_client.py` | RTDS client (appears empty/incomplete) | Incomplete placeholder |
| `ta_data_fetcher.py` | TA data fetcher (appears empty) | Incomplete placeholder |

### Test Files (Not Used in Production)

All files starting with `test_` are pytest unit tests:

| File | Purpose |
|------|---------|
| `test_*.py` (36 files in root) | Unit tests for various modules |
| `tests/` directory (31 files) | Additional unit tests |

### Documentation Files

| File | Purpose |
|------|---------|
| `AMPLIFICATION_STRATEGIES.md` | Strategy documentation |
| `AMPLIFICATION_TUNING.md` | Tuning documentation |
| `ATR_IMPLEMENTATION_SUMMARY.md` | ATR implementation notes |
| `OPTIMIZATION_SUMMARY.md` | Optimization notes |
| `ORDER_CANCELLATION_BOT_README.md` | Cancellation bot docs |
| `PERFORMANCE_OPTIMIZATION_REPORT.md` | Performance report |
| `PRICE_FETCHING_OPTIMIZATION.md` | Price fetching docs |
| `PROJECT_JOURNEY_AND_INSIGHTS.md` | Project history |
| `PROJECT_SUMMARY.md` | Project summary |
| `QUICKSTART.md` | Quick start guide |
| `QUICK_REFERENCE.md` | Quick reference |
| `README.md` | Main readme |
| `SIGMA_METHOD_GUIDE.md` | Sigma method guide |
| `STRATEGY_TIMEFRAMES.md` | Timeframe documentation |
| `TEST_MODE_GUIDE.md` | Test mode guide |
| `TEST_RESULTS.md` | Test results |
| `UP_DOWN_MARKET_STRATEGY.md` | Strategy documentation |
| `WEBSOCKET_INTEGRATION_GUIDE.py` | WebSocket guide (misnamed as .py) |
| `new_method.txt` | Method notes |

### Alternative Launch Scripts (Not Used by Target Batch Files)

| File | Purpose |
|------|---------|
| `run_both_bots.ps1` | PowerShell version |
| `run_side_by_side_test.bat` | Side-by-side testing |
| `start_dual_bot.bat` | Alternative launcher |
| `start_dual_bot.sh` | Unix shell launcher |
| `switch_sigma.bat` | Sigma switching launcher |

### Backup Files

| File | Purpose |
|------|---------|
| `module2_market_orchestrator.py.backup` | Backup of module2 |

### Log Files

| File | Purpose |
|------|---------|
| `shadow_run.log` | Shadow run logs |
| `shadow_run_20251222_044437.log` | Dated shadow run log |

### Setup Scripts

| File | Purpose |
|------|---------|
| `scripts/setup_allowance.py` | One-time allowance setup |

---

## Dependency Graph

```
run_test_mode.bat / Run_both_bots.bat
├── order_cancellation_bot.py
│   ├── config.py
│   └── py_clob_client/
│
└── main_bot_optimized.py
    ├── config.py
    ├── fast_price_fetcher.py
    │   └── websocket_price_fetcher.py
    │   └── module1_chainlink_harvester.py
    ├── module2_market_orchestrator.py
    ├── module3_pricing_engine.py
    ├── module4_execution_engine.py
    │   ├── module3_pricing_engine.py
    │   ├── allowance_utils.py
    │   └── py_clob_client/
    ├── calculate_volatility.py
    ├── indicator_filters.py
    ├── order_cancellation_integration.py
    ├── polymarket_orderbook_websocket.py
    └── amplification_strategies.py
        └── binance_ofi_logger.py
```

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Required Python modules** | 17 |
| **Required data/config files** | 6 |
| **Not Required (standalone scripts)** | 21 |
| **Not Required (test files)** | 67 |
| **Not Required (documentation)** | 18 |
| **Not Required (alternative launchers)** | 5 |
| **Not Required (logs/backups)** | 3 |

---

## Recommendations

### Files Safe to Remove (if cleaning up)

1. **Test files** (`test_*.py`, `tests/`) - Only needed for development/CI
2. **Standalone utility scripts** - Only needed for manual debugging
3. **Documentation files** - Optional for production
4. **Log files** - Can be regenerated
5. **Backup files** - Old backups
6. **Legacy files** - `main_bot.py` (superseded)

### Files You Should KEEP

1. All 17 core Python modules listed above
2. `.env` and configuration files
3. `py_clob_client/` directory
4. `requirements.txt` for dependency installation
5. `.gitignore` for version control
