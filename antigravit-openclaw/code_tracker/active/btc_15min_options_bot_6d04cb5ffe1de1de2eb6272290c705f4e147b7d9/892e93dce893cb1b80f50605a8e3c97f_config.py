��"""
Configuration loader for BTC 1-hour options trading bot
Loads environment variables and validates configuration
"""

import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

class Config:
    """Configuration class for trading bot"""
    
    # Polygon Network
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com/")
    CHAIN_ID: int = 137  # Polygon Mainnet
    
    # Chainlink BTC/USD Feed on Polygon
    # NOTE: Get correct address from https://docs.chain.link/data-feeds/price-feeds/addresses
    CHAINLINK_BTC_USD_FEED: str = os.getenv(
        "CHAINLINK_BTC_USD_FEED",
        "0xc907E116054Ad103354f2D350FD2514433D57F6f"  # Example - VERIFY THIS
    )
    
    # Wallet Configuration
    OWNER_PRIVATE_KEY: str = os.getenv("OWNER_PRIVATE_KEY", "")
    PROXY_ADDRESS: str = os.getenv("PROXY_ADDRESS", "")

    # ERC-20 / Allowance settings (optional)
    # Set the stable token used for trading (e.g., USDC on Polygon). If set, the bot will
    # preflight allowance checks before BUY orders when `POLYMARKET_CLOB_SPENDER_ADDRESS` is set.
    # Example USDC on Polygon: 0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174
    STABLE_TOKEN_ADDRESS: str = os.getenv("STABLE_TOKEN_ADDRESS", "")

    # Spender address used by Polymarket/CLOB to pull stable tokens (must be configured for
    # automatic allowance checks/approvals). Leave empty to skip automatic checks.
    POLYMARKET_CLOB_SPENDER_ADDRESS: str = os.getenv("POLYMARKET_CLOB_SPENDER_ADDRESS", "")

    # When true, the bot will attempt to `approve(spender, MaxUint256)` automatically
    # using OWNER_PRIVATE_KEY if allowance is insufficient. Use with care - this requires
    # the private key and RPC to be available. Default: false
    AUTO_APPROVE_ALLOWANCE: bool = os.getenv("AUTO_APPROVE_ALLOWANCE", "false").lower() == "true"

    # Polymarket API
    CLOB_HOST: str = "https://clob.polymarket.com"
    GAMMA_API_HOST: str = "https://gamma-api.polymarket.com"
    
    CLOB_API_KEY: str = os.getenv("CLOB_API_KEY", "")
    CLOB_SECRET: str = os.getenv("CLOB_SECRET", "")
    CLOB_PASSPHRASE: str = os.getenv("CLOB_PASSPHRASE", "")
    
    # CSV Log Rotation
    CSV_ROTATION_ROW_LIMIT: int = int(os.getenv("CSV_ROTATION_ROW_LIMIT", "30000"))
    
    # Trading Parameters
    TRADE_SIZE: float = float(os.getenv("TRADE_SIZE", "2.0"))  # USDC per trade

    # Market order minimum notional enforcement (prevents sub-$1 market buys getting rejected)
    # Note: Due to the exact-2-decimal constraint on (size x price), $1.00 is not always achievable
    # for a given price tick. When ENFORCE_MIN_NOTIONAL_BUY is enabled, the engine will snap to the
    # smallest achievable notional >= MIN_ORDER_NOTIONAL_USDC (e.g., at $0.66, next is $1.32).
    MIN_ORDER_NOTIONAL_USDC: float = float(os.getenv("MIN_ORDER_NOTIONAL_USDC", "1.00"))
    ENFORCE_MIN_NOTIONAL_BUY: bool = os.getenv("ENFORCE_MIN_NOTIONAL_BUY", "true").lower() == "true"
    # If True, allow bumping above TRADE_SIZE budget when needed to satisfy MIN_ORDER_NOTIONAL_USDC.
    # If False, the engine will refuse the order with a clear error.
    ALLOW_MIN_NOTIONAL_BUMP: bool = os.getenv("ALLOW_MIN_NOTIONAL_BUMP", "true").lower() == "true"

    # Sell-side dust suppression / minimum notional
    # Goal: Avoid frequent tiny SELL orders (sub-$1 notionals or very small share amounts).
    # This is primarily intended for profit-taking / partial exits.
    ENFORCE_MIN_SELL_NOTIONAL: bool = os.getenv("ENFORCE_MIN_SELL_NOTIONAL", "true").lower() == "true"
    MIN_SELL_NOTIONAL_USDC: float = float(os.getenv("MIN_SELL_NOTIONAL_USDC", "1.00"))
    ENFORCE_MIN_SELL_SHARES: bool = os.getenv("ENFORCE_MIN_SELL_SHARES", "true").lower() == "true"
    MIN_SELL_SHARES: float = float(os.getenv("MIN_SELL_SHARES", "5.0"))
    # Minimum edge required specifically for BUY entries (separate config)
    # Halved buy entry edge per user request (was 0.015 -> now 0.0075)
    BUY_ENTRY_EDGE: float = float(os.getenv("BUY_ENTRY_EDGE", "0.0075"))  # 0.75% base + taker 0.5% = 1.25% effective
    # Maximum entry edge (if edge >= this value, block buys/sells). Inclusive threshold.
    # Reduced per user request from 0.02 -> 0.015
    MAX_ENTRY_EDGE: float = float(os.getenv("MAX_ENTRY_EDGE", "0.015"))  # 1.5%

    # Optional max-edge relaxation for BUY entries when amplification is strong.
    # If the amplification multiplier for the target side is >= MAX_ENTRY_EDGE_AMP_MIN_MULT,
    # allow BUY edges up to MAX_ENTRY_EDGE_AMP_CAP (never reduces MAX_ENTRY_EDGE if it is higher).
    MAX_ENTRY_EDGE_AMP_CAP: float = float(os.getenv("MAX_ENTRY_EDGE_AMP_CAP", "0.03"))
    MAX_ENTRY_EDGE_AMP_MIN_MULT: float = float(os.getenv("MAX_ENTRY_EDGE_AMP_MIN_MULT", "1.10"))
    TAKER_FEE: float = float(os.getenv("TAKER_FEE", "0.005"))  # 0.5% fee

    # === Pre-order re-evaluation and anti-staleness entry guards ===
    # Maximum allowed price move (percent) between decision and submit; skip buy if move larger.
    ENTRY_PRICE_MOVE_TOLERANCE_PCT: float = float(os.getenv("ENTRY_PRICE_MOVE_TOLERANCE_PCT", "0.5"))  # percent
    # Minimum required amplified total amp for the target side at submit time (e.g., 1.05 => 5% net).
    ENTRY_AMP_THRESHOLD: float = float(os.getenv("ENTRY_AMP_THRESHOLD", "1.05"))
    # Allow small amp decay tolerance relative to initial: don't buy if amp fell by more than this fraction (e.g., 0.02 = 2%).
    ENTRY_AMP_DELTA_TOLERANCE: float = float(os.getenv("ENTRY_AMP_DELTA_TOLERANCE", "0.02"))
    # If True, skip buys when price is near FV and the opposite side's amplification is net positive
    ENTRY_SKIP_IF_NEAR_FV: bool = os.getenv("ENTRY_SKIP_IF_NEAR_FV", "true").lower() == "true"
    # How many ticks (FV_REVERSION_TICK units) count as 'near FV' for this rule
    ENTRY_FV_TICKS: int = int(os.getenv("ENTRY_FV_TICKS", "1"))
    # Require active amplification on target side to allow buys (defaults to True to reduce latency)
    ENTRY_REQUIRE_ACTIVE_AMP: bool = os.getenv("ENTRY_REQUIRE_ACTIVE_AMP", "true").lower() == "true"
    # Minimum epsilon above 1.0 to consider an amp "active" (e.g., 0.01 => amp must be > 1.01)
    ENTRY_AMP_ACTIVE_EPS: float = float(os.getenv("ENTRY_AMP_ACTIVE_EPS", "0.01"))
    # Opposite side amp threshold to consider it 'net positive' for FV proximity rule (e.g., 1.02 => +2%)
    ENTRY_FV_OPP_AMP_THRESHOLD: float = float(os.getenv("ENTRY_FV_OPP_AMP_THRESHOLD", "1.02"))
    # Maximum allowed age (seconds) for re-evaluation price / data to be considered 'fresh'
    ENTRY_RECHECK_MAX_AGE_SEC: float = float(os.getenv("ENTRY_RECHECK_MAX_AGE_SEC", "1.0"))
    # Option: perform a small probe order instead of full size; set to True to enable experimental probe trades
    ENTRY_USE_PROBE_TRADES: bool = os.getenv("ENTRY_USE_PROBE_TRADES", "false").lower() == "true"
    
    # Risk Management
    MAX_POSITION_SIZE: float = float(os.getenv("MAX_POSITION_SIZE", "100.0"))
    MAX_DAILY_TRADES: int = int(os.getenv("MAX_DAILY_TRADES", "50"))
    STOP_LOSS_THRESHOLD: float = float(os.getenv("STOP_LOSS_THRESHOLD", "-50.0"))
    
    # Daily P&L Limits - Trading halt when daily loss exceeds threshold
    DAILY_PNL_LIMIT_ENABLED: bool = os.getenv("DAILY_PNL_LIMIT_ENABLED", "true").lower() == "true"
    DAILY_PNL_LOSS_LIMIT: float = float(os.getenv("DAILY_PNL_LOSS_LIMIT", "-50.0"))  # Max daily loss in USDC
    DAILY_PNL_PROFIT_LIMIT: float = float(os.getenv("DAILY_PNL_PROFIT_LIMIT", "100.0"))  # Max daily profit (optional halt)
    DAILY_PNL_ENABLE_PROFIT_LIMIT: bool = os.getenv("DAILY_PNL_ENABLE_PROFIT_LIMIT", "false").lower() == "true"
    DAILY_PNL_RESET_HOUR_UTC: int = int(os.getenv("DAILY_PNL_RESET_HOUR_UTC", "0"))  # UTC hour to reset daily P&L (0 = midnight)
    
    # Exit Strategy Parameters
    STOP_LOSS_PCT: float = float(os.getenv("STOP_LOSS_PCT", "-30.0"))  # Hard stop-loss percentage
    # When False, the bot will not trigger the anytime HARD_STOP_LOSS exit.
    # Note: EMERGENCY_STOP_LOSS (near expiry) still uses STOP_LOSS_PCT.
    HARD_STOP_LOSS_ENABLED: bool = os.getenv("HARD_STOP_LOSS_ENABLED", "false").lower() == "true"
    TRAILING_STOP_ACTIVATION: float = float(os.getenv("TRAILING_STOP_ACTIVATION", "10.0"))  # Activate trailing stop at +X%
    TRAILING_STOP_DISTANCE: float = float(os.getenv("TRAILING_STOP_DISTANCE", "5.0"))  # Trail by X% from peak
    TAKE_PROFIT_1: float = float(os.getenv("TAKE_PROFIT_1", "10.0"))  # First take-profit level (%)
    TAKE_PROFIT_2: float = float(os.getenv("TAKE_PROFIT_2", "15.0"))  # Second take-profit level (%)
    TAKE_PROFIT_3: float = float(os.getenv("TAKE_PROFIT_3", "20.0"))  # Final take-profit level (%)

    # Fair-value reversion take-profit
    # Goal: If amplification collapses back to ~1.0 (model says edge is gone / fair value reached)
    # and price is within one tick of fair value, take partial profits quickly.
    FV_REVERSION_TAKE_PROFIT_ENABLED: bool = os.getenv("FV_REVERSION_TAKE_PROFIT_ENABLED", "true").lower() == "true"
    # When True, only allow FV_REVERSION_TP if the opposite side ALSO has a valid BUY signal
    # (i.e., would pass the same final-buy checks). This prevents "sell without flip" behavior.
    FV_REVERSION_REQUIRE_OPPOSITE_BUY_SIGNAL: bool = os.getenv("FV_REVERSION_REQUIRE_OPPOSITE_BUY_SIGNAL", "false").lower() == "true"
    # One-tick proximity to fair value (Polymarket odds move in $0.01 increments)
    FV_REVERSION_TICK: float = float(os.getenv("FV_REVERSION_TICK", "0.01"))
    # Treat amplification as "neutral" when within this epsilon of 1.0
    FV_REVERSION_AMP_EPS: float = float(os.getenv("FV_REVERSION_AMP_EPS", "0.02"))
    # Also treat amplification as "neutral" when UP and DOWN multipliers are nearly equal.
    # Example: UP=1.06 and DOWN=1.06 => symmetric (no directional tilt) => neutral for FV reversion TP.
    FV_REVERSION_AMP_SYMM_EPS: float = float(os.getenv("FV_REVERSION_AMP_SYMM_EPS", "0.02"))
    # Optional additional trigger: allow FV reversion if (opposite_amp - current_amp) is net positive by at least this delta.
    # Example: current=1.00 and opposite=1.06 => delta=0.06 (passes); current=1.03 and opposite=1.08 => delta=0.05 (fails).
    FV_REVERSION_OPP_AMP_NET_DELTA: float = float(os.getenv("FV_REVERSION_OPP_AMP_NET_DELTA", "0.061"))
    # Require at least this profit before triggering (helps cover round-trip fees)
    FV_REVERSION_MIN_PNL_PCT: float = float(os.getenv("FV_REVERSION_MIN_PNL_PCT", "1.0"))
    # When True, require the configured minimum P&L before triggering FV reversion TP.
    # Set to false to allow FV reversion TP regardless of current P&L.
    FV_REVERSION_REQUIRE_MIN_PNL: bool = os.getenv("FV_REVERSION_REQUIRE_MIN_PNL", "true").lower() == "true"
    # When True, allow a strong opposite-side amplification delta to override the price proximity
    # requirement for FV reversion TP (i.e., even if price is not within one tick of FV).
    FV_REVERSION_ALLOW_OPP_AMP_OVERRIDE_NEAR_FV: bool = os.getenv("FV_REVERSION_ALLOW_OPP_AMP_OVERRIDE_NEAR_FV", "true").lower() == "true"
    FORCED_EXIT_MINUTES: float = float(os.getenv("FORCED_EXIT_MINUTES", "2.0"))  # Force exit X min before expiry
    TIME_EXIT_MINUTES: float = float(os.getenv("TIME_EXIT_MINUTES", "5.0"))  # Time-based exit if losing
    EMERGENCY_STOP_MINUTES: float = float(os.getenv("EMERGENCY_STOP_MINUTES", "30.0"))  # Emergency stop time window
    # Seconds before a tracked limit order is auto-cancelled and optionally converted to a market order
    # Default restored to 10s for production safety (was reduced for tests)
    LIMIT_ORDER_TIMEOUT: int = int(os.getenv("LIMIT_ORDER_TIMEOUT", "10"))  # Seconds before limit -> market (default: 10s)
    
    # Order Time-in-Force defaults (TIF)
    # Allowed values: FAK (partial+IOC), FOK (all-or-none), IOC, GTC
    ORDER_ENTRY_TIF: str = os.getenv("ORDER_ENTRY_TIF", "FAK").upper()   # Default TIF for new entries
    ORDER_EXIT_TIF:  str = os.getenv("ORDER_EXIT_TIF", "FAK").upper()    # Default TIF for exits
    STRICT_ENTRY_TIF: str = os.getenv("STRICT_ENTRY_TIF", "FOK").upper() # For size-critical entries where partial fills are unacceptable
    
    # Data Processing
    VOLATILITY_WINDOW: int = int(os.getenv("VOLATILITY_WINDOW", "24"))  # 24 hours (1-hour bars)
    UPDATE_INTERVAL: int = int(os.getenv("UPDATE_INTERVAL", "300"))  # 5 minutes
    
    # Sigma Calculation Method
    # Options: "fixed", "volume_weighted", "garman_klass", "atr"
    # Use "fixed" for a constant sigma value (simpler, more stable)
    SIGMA_METHOD: str = "fixed"  # "volume_weighted", "garman_klass", "atr", or "fixed"
    FIXED_SIGMA: float = float(os.getenv("FIXED_SIGMA", "0.7"))  # Fixed sigma value when using fixed method (fallback)
    
    # Fair Value Calculation Method
    # Options: "black_scholes" (theoretical probability), "trade_average" (recent trade SMA), 
    #          "midpoint" (bid+ask/2), "midpoint_depth" (depth-weighted midpoint), "hybrid" (weighted combination)
    # Default behavior changed to "midpoint_depth" to prefer depth-weighted midpoint as base fair value
    # "black_scholes" - Uses Black-Scholes model with sigma to calculate probability
    # "trade_average" - Uses recent trade average (time-decay/VWAP configurable in WebSocket)
    # "midpoint" - Uses (best_bid + best_ask) / 2 as fair value (now the default)
    # "midpoint_depth" - Uses a distance-decay VWAP across top N levels per side (Method B)
    # "hybrid" - Weighted combination of black_scholes and market fair value (trade_average or midpoint)
    FAIR_VALUE_METHOD: str = os.getenv("FAIR_VALUE_METHOD", "midpoint_depth")  # "black_scholes", "trade_average", "midpoint", "midpoint_depth", or "hybrid"
    # Depth-midpoint settings (used by FAIR_VALUE_METHOD = "midpoint_depth")
    DEPTH_MIDPOINT_TOP_LEVELS: int = int(os.getenv("DEPTH_MIDPOINT_TOP_LEVELS", "5"))
    DEPTH_MIDPOINT_DECAY_EXPONENT: float = float(os.getenv("DEPTH_MIDPOINT_DECAY_EXPONENT", "1.0"))
    DEPTH_MIDPOINT_EPS: float = float(os.getenv("DEPTH_MIDPOINT_EPS", "0.01"))  # minimum distance pct to avoid div-by-zero
    DEPTH_MIDPOINT_MAX_DISTANCE_PCT: float = float(os.getenv("DEPTH_MIDPOINT_MAX_DISTANCE_PCT", "10.0"))
    # Use amplified fair value when evaluating entry thresholds (default: True)
    # Set default to True so amplified fair values are considered for entry decisions.
    USE_AMPLIFIED_FOR_ENTRY: bool = os.getenv("USE_AMPLIFIED_FOR_ENTRY", "true").lower() == "true"
    TRADE_AVG_WINDOW: int = int(os.getenv("TRADE_AVG_WINDOW", "180"))  # seconds for trade average (extended to capture sparse trades)
    TRADE_AVG_MIN_TRADES: int = int(os.getenv("TRADE_AVG_MIN_TRADES", "1"))  # min trades required (always have value if ANY trade exists)
    # Trade-average weighting
    # Default: exponential time-decay with size weighting (recency-weighted VWAP).
    # Most recent TRADE_AVG_HALFLIFE_SECONDS get the highest weight; older trades decay exponentially.
    # Set TRADE_AVG_HALFLIFE_SECONDS=0 to disable decay and use simple SMA.
    TRADE_AVG_WEIGHTING: str = os.getenv("TRADE_AVG_WEIGHTING", "time_x_size")  # "time" or "time_x_size"
    TRADE_AVG_HALFLIFE_SECONDS: float = float(os.getenv("TRADE_AVG_HALFLIFE_SECONDS", "10"))

    # Live trading flag - intentionally opt-in for safety.
    # Set ENABLE_LIVE_TRADING=true (and provide valid CLOB credentials) to enable real order placement.
    ENABLE_LIVE_TRADING: bool = os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true"
    # Sanity: require API credentials to be set when live trading is enabled
    # (CLOB_API_KEY, CLOB_SECRET, CLOB_PASSPHRASE are used by the CLOB client)

    # Binance OFI reporting (report-only independent strategy)
    ENABLE_BINANCE_OFI_REPORTING: bool = os.getenv("ENABLE_BINANCE_OFI_REPORTING", "true").lower() == "true"
    BINANCE_OFI_MAX_DISTANCE_USD: float = float(os.getenv("BINANCE_OFI_MAX_DISTANCE_USD", "50.0"))
    BINANCE_OFI_DEPTH_LIMIT: int = int(os.getenv("BINANCE_OFI_DEPTH_LIMIT", "500"))
    BINANCE_OFI_TTL: float = float(os.getenv("BINANCE_OFI_TTL", "2.0"))  # seconds (cache TTL for REST snapshots)
    BINANCE_OFI_PRINT_RATE_LIMIT: float = float(os.getenv("BINANCE_OFI_PRINT_RATE_LIMIT", "2.0"))  # seconds between printing detail lines
    # When True, Binance OFI will be applied as a normal amplification strategy (affects amp_up/amp_down)
    ENABLE_BINANCE_OFI_APPLY: bool = os.getenv("ENABLE_BINANCE_OFI_APPLY", "true").lower() == "true"

    # Binance OFI sensitivity controls
    # Higher threshold => less sensitive (needs a larger imbalance to activate).
    BINANCE_OFI_IMBALANCE_THRESHOLD_PCT: float = float(os.getenv("BINANCE_OFI_IMBALANCE_THRESHOLD_PCT", "15.0"))
    # Bonus curve:
    # - linear: bonus = (imbalance_pct - threshold) * BINANCE_OFI_BONUS_LINEAR_SLOPE
    # - log:    bonus = BINANCE_OFI_BONUS_LOG_K * log1p(imbalance_pct - threshold)
    # `log` reduces sensitivity to extreme imbalances and has no hard cap.
    BINANCE_OFI_BONUS_MODE: str = os.getenv("BINANCE_OFI_BONUS_MODE", "log")
    BINANCE_OFI_BONUS_LINEAR_SLOPE: float = float(os.getenv("BINANCE_OFI_BONUS_LINEAR_SLOPE", "0.005"))
    BINANCE_OFI_BONUS_LOG_K: float = float(os.getenv("BINANCE_OFI_BONUS_LOG_K", "0.02"))
    # When True, apply AMP_CAP_ORDERBOOK to Binance OFI too (hard cap). Default False.
    BINANCE_OFI_USE_CAP: bool = os.getenv("BINANCE_OFI_USE_CAP", "false").lower() == "true"

    # Orderbook OFI (Polymarket order book) - can be disabled to prefer external sources
    ENABLE_ORDERBOOK_OFI: bool = os.getenv("ENABLE_ORDERBOOK_OFI", "false").lower() == "true"

    # Allowance preflight: when True, the engine will check ERC-20 allowance before BUYs and attempt auto-approve if enabled.
    # Set to False to skip allowance checks entirely (assume on-chain prerequisites are already set). Use with care.
    ALLOWANCE_PREFLIGHT_ENABLED: bool = os.getenv("ALLOWANCE_PREFLIGHT_ENABLED", "false").lower() == "true"

    # Reversal exit feature flag
    # When True, the bot can execute a protective partial exit (50%) when switching sides.
    REVERSAL_EXIT_ENABLED: bool = os.getenv("REVERSAL_EXIT_ENABLED", "true").lower() == "true"
    # Require target-side amplification to be above this percent (e.g., 5.0 => amp > 1.05)
    # before performing the reversal exit.
    REVERSAL_EXIT_MIN_AMP_PCT: float = float(os.getenv("REVERSAL_EXIT_MIN_AMP_PCT", "5.0"))
    # Fallback exit behavior for missing fair values
    # When False (default), the bot will NOT place large passive sells using the current bid
    # as a fallback when fair values are unavailable. If enabled, fallback sells are capped
    # to a conservative percentage of the position (FALLBACK_SELL_MAX_PCT).
    ALLOW_FALLBACK_EXITS: bool = os.getenv("ALLOW_FALLBACK_EXITS", "true").lower() == "true"
    FALLBACK_SELL_MAX_PCT: float = float(os.getenv("FALLBACK_SELL_MAX_PCT", "0.25"))  # Max % of position to sell on fallback (default: 25%)

    HYBRID_BS_WEIGHT: float = float(os.getenv("HYBRID_BS_WEIGHT", "0.5"))  # Black-Scholes weight in hybrid mode
    
    # Rubber Band Mean Reversion Strategy
    RUBBER_BAND_ENABLED: bool = os.getenv("RUBBER_BAND_ENABLED", "true").lower() == "true"
    BB_PERIOD: int = int(os.getenv("BB_PERIOD", "20"))
    BB_STD_DEV: float = float(os.getenv("BB_STD_DEV", "2.0"))
    RSI_PERIOD: int = int(os.getenv("RSI_PERIOD", "14"))
    RSI_OVERSOLD: float = float(os.getenv("RSI_OVERSOLD", "30"))
    RSI_OVERBOUGHT: float = float(os.getenv("RSI_OVERBOUGHT", "70"))
    ATR_PERIOD: int = int(os.getenv("ATR_PERIOD", "14"))
    ATR_MULTIPLIER: float = float(os.getenv("ATR_MULTIPLIER", "1.5"))
    # ADX defaults: increased lookback per user request (14 -> 28)
    # Enforce minimum ADX period of 28 so tests and expected behavior are consistent
    ADX_PERIOD: int = max(28, int(os.getenv("ADX_PERIOD", "28")))
    # Use 3-minute resampled candles by default for ADX calculations
    ADX_TIMEFRAME_MINUTES: int = int(os.getenv("ADX_TIMEFRAME_MINUTES", "3"))
    ADX_THRESHOLD: float = float(os.getenv("ADX_THRESHOLD", "25"))
    VOLUME_SPIKE_MULTIPLIER: float = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))
    RUBBER_BAND_COOLDOWN: float = float(os.getenv("RUBBER_BAND_COOLDOWN", "300"))  # seconds

    # Exhaustion signal gating (setup → confirm)
    # When enabled, an exhaustion signal must be followed by a short-term reversal confirmation
    # (velocity/acceleration) within EXHAUSTION_CONFIRM_WINDOW candles before it is applied.
    EXHAUSTION_CONFIRM_ENABLED: bool = os.getenv("EXHAUSTION_CONFIRM_ENABLED", "true").lower() == "true"
    # Number of candles after a setup where confirmation is allowed.
    # Implementation is inclusive of the setup candle (so window=2 allows setup + next 2 candles).
    EXHAUSTION_CONFIRM_WINDOW: int = int(os.getenv("EXHAUSTION_CONFIRM_WINDOW", "2"))
    # Confirmation thresholds are in percent units (e.g. 0.10 = 0.10%).
    EXHAUSTION_CONFIRM_MIN_VEL_PCT: float = float(os.getenv("EXHAUSTION_CONFIRM_MIN_VEL_PCT", "0.10"))
    EXHAUSTION_CONFIRM_MIN_ACCEL_PCT: float = float(os.getenv("EXHAUSTION_CONFIRM_MIN_ACCEL_PCT", "0.05"))

    # Block counter-trend exhaustion in strong ADX trends
    EXHAUSTION_ADX_BLOCK_THRESHOLD: float = float(os.getenv("EXHAUSTION_ADX_BLOCK_THRESHOLD", "22"))

    # Symmetry / feature flags to control winner-only amplification behaviors
    # When True, volume profile will apply amplification symmetrically (both sides scaled by bias) rather than only amplifying the winner
    VOLUME_PROFILE_SYMMETRIC: bool = os.getenv("VOLUME_PROFILE_SYMMETRIC", "true").lower() == "true"
    # When True, volatility percentile amplification will apply symmetrically (scale both sides by opposite bias)
    VOL_PERCENTILE_SYMMETRIC: bool = os.getenv("VOL_PERCENTILE_SYMMETRIC", "true").lower() == "true"
    # OBV confirmation gating: when True, confirmation boosts require fair_value_x > 0.5
    OBV_CONFIRMATION_REQUIRES_FV: bool = os.getenv("OBV_CONFIRMATION_REQUIRES_FV", "true").lower() == "true"
    
    # ===== AMPLIFICATION STRATEGY CAPS & WEIGHTS =====
    # Fine-tune individual strategy contributions to prevent any single strategy from dominating
    # All values are multipliers (1.0 = 100% of strategy's calculated amp, 0.5 = 50%, etc.)
    
    # Per-Strategy Maximum Caps (absolute max amp any strategy can contribute)
    AMP_CAP_ORDERBOOK: float = float(os.getenv("AMP_CAP_ORDERBOOK", "1.08"))  # OFI max +8% (was uncapped ~15%)
    AMP_CAP_VOLUME_PROFILE: float = float(os.getenv("AMP_CAP_VOLUME_PROFILE", "1.08"))  # Volume max +8% (was uncapped ~15%)
    AMP_CAP_VOL_REGIME: float = float(os.getenv("AMP_CAP_VOL_REGIME", "1.12"))  # Vol regime max ±12% (was ±20%)
    AMP_CAP_PRICE_VELOCITY: float = float(os.getenv("AMP_CAP_PRICE_VELOCITY", "1.08"))  # Velocity max +8% (more conservative)
    AMP_CAP_OBV_DIVERGENCE: float = float(os.getenv("AMP_CAP_OBV_DIVERGENCE", "1.06"))  # OBV div max +6% (already capped)
    AMP_CAP_MOMENTUM: float = float(os.getenv("AMP_CAP_MOMENTUM", "1.12"))  # MACD momentum max +12% (already capped)
    AMP_CAP_VOL_PERCENTILE: float = float(os.getenv("AMP_CAP_VOL_PERCENTILE", "1.10"))  # Vol percentile max +10% (was +12%)
    AMP_CAP_EXHAUSTION: float = float(os.getenv("AMP_CAP_EXHAUSTION", "1.08"))  # Exhaustion max +8% (already capped)
    AMP_CAP_ADX_FILTER: float = float(os.getenv("AMP_CAP_ADX_FILTER", "1.10"))  # ADX max +10% (already capped)

    # Feature flags
    # When False (default), volatility regime is only reported in strategy details
    # and does NOT directly multiply or scale the final amplification values.
    ENABLE_VOL_REGIME_AMPLIFY: bool = os.getenv("ENABLE_VOL_REGIME_AMPLIFY", "false").lower() == "true"
    # When False, disable the volatility percentile regime filter entirely.
    ENABLE_VOL_PERCENTILE: bool = os.getenv("ENABLE_VOL_PERCENTILE", "false").lower() == "true"

    # Live price blending flags for price-velocity amplification
    # When True, velocity calculation may incorporate the current live price (S) blended with candle velocity
    USE_LIVE_PRICE_FOR_VELOCITY: bool = os.getenv("USE_LIVE_PRICE_FOR_VELOCITY", "true").lower() == "true"
    # Maximum age (seconds) of a 'current_price' value to be considered fresh
    LIVE_PRICE_MAX_AGE_SECONDS: int = int(os.getenv("LIVE_PRICE_MAX_AGE_SECONDS", "3"))
    # Minimum price move fraction required for the live price to be considered (to avoid micro-noise)
    LIVE_PRICE_MIN_MOVE_PCT: float = float(os.getenv("LIVE_PRICE_MIN_MOVE_PCT", "0.0003"))  # 0.03%
    # Blend alpha for live price when enabled: blended_velocity = (1-alpha)*candle_velocity + alpha*instant_velocity
    LIVE_PRICE_BLEND_ALPHA: float = float(os.getenv("LIVE_PRICE_BLEND_ALPHA", "0.15"))
    
    # HTF (Higher Timeframe) Trend Filter Settings
    AMP_HTF_TREND_BIAS_MAX: float = float(os.getenv("AMP_HTF_TREND_BIAS_MAX", "0.03"))  # Max HTF bias +3% (was +6%)
    AMP_HTF_MOMENTUM_MULT_MAX: float = float(os.getenv("AMP_HTF_MOMENTUM_MULT_MAX", "1.20"))  # Max momentum boost 1.2x (was 1.3x)
    AMP_HTF_REVERSAL_MULT_MIN: float = float(os.getenv("AMP_HTF_REVERSAL_MULT_MIN", "0.60"))  # Min reversal dampening 0.6x (was 0.5x)
    
    # Global Amplification Limits (final safety caps after all strategies combined)
    AMP_GLOBAL_CAP: float = float(os.getenv("AMP_GLOBAL_CAP", "1.30"))  # Max total amplification +30%
    AMP_GLOBAL_FLOOR: float = float(os.getenv("AMP_GLOBAL_FLOOR", "0.75"))  # Min total amplification -25%
    
    # Final Amplification Multiplier (applied to deviation from 1.0)
    # 1.0 = raw amp (default), 2.0 = double amp, 0.5 = half amp
    # Formula: final_amp = 1.0 + AMP_FINAL_MULTIPLIER * (raw_amp - 1.0)
    AMP_FINAL_MULTIPLIER: float = float(os.getenv("AMP_FINAL_MULTIPLIER", "1.0"))
    
    # A/B Testing Configuration
    AB_TEST_ENABLED: bool = os.getenv("AB_TEST_ENABLED", "false").lower() == "true"
    AB_TEST_SUMMARY_INTERVAL_MINUTES: int = int(os.getenv("AB_TEST_SUMMARY_INTERVAL_MINUTES", "30"))
    AB_TEST_STARTING_BALANCE: float = float(os.getenv("AB_TEST_STARTING_BALANCE", "100.0"))
    AB_TEST_LOSS_ALERT_THRESHOLD: float = float(os.getenv("AB_TEST_LOSS_ALERT_THRESHOLD", "-10.0"))
    AB_TEST_OUTPERFORM_THRESHOLD: float = float(os.getenv("AB_TEST_OUTPERFORM_THRESHOLD", "5.0"))
    AB_TEST_WIN_RATE_LOW: float = float(os.getenv("AB_TEST_WIN_RATE_LOW", "40.0"))
    AB_TEST_WIN_RATE_HIGH: float = float(os.getenv("AB_TEST_WIN_RATE_HIGH", "70.0"))
    
    # File Paths
    HISTORICAL_DATA_PATH: str = "chainlink_btc_history.csv"
    MODEL_PARAMS_PATH: str = "model_parameters.json"
    TRADES_LOG_PATH: str = "trades_log.csv"
    
    # Telegram (Optional)
    TELEGRAM_TOKEN: Optional[str] = os.getenv("TELEGRAM_TOKEN")
    ADMIN_CHAT_ID: Optional[str] = os.getenv("ADMIN_CHAT_ID")
    
    # Market Discovery
    BTC_15MIN_MARKET_SLUG: str = "btc-usd-15m"
    MARKET_POLL_INTERVAL: int = 30  # seconds
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration"""
        required_fields = [
            "OWNER_PRIVATE_KEY",
            "PROXY_ADDRESS",
            "CLOB_API_KEY",
            "CLOB_SECRET",
            "CLOB_PASSPHRASE"
        ]
        
        missing = []
        for field in required_fields:
            value = getattr(cls, field, "")
            if not value:
                missing.append(field)
        
        if missing:
            print(f"❌ Missing required configuration: {', '.join(missing)}")
            print("Please update your .env file")
            return False
        
        # Validate TIF settings
        allowed_tifs = {"FAK", "FOK", "IOC", "GTC"}
        invalid_tifs = []
        for field in ("ORDER_ENTRY_TIF", "ORDER_EXIT_TIF", "STRICT_ENTRY_TIF"):
            value = getattr(cls, field, "").upper()
            if value and value not in allowed_tifs:
                invalid_tifs.append(f"{field}='{value}'")
        if invalid_tifs:
            print(f"❌ Invalid TIF configuration: {', '.join(invalid_tifs)}. Allowed values: {', '.join(sorted(allowed_tifs))}")
            return False

        print("✅ Configuration validated")
        return True
    
    @classmethod
    def display(cls):
        """Display current configuration (hide sensitive data)"""
        print("="*70)
        print("TRADING BOT CONFIGURATION")
        print("="*70)
        
        print(f"\n🌐 Network:")
        print(f"   RPC: {cls.POLYGON_RPC_URL}")
        print(f"   Chain ID: {cls.CHAIN_ID}")
        
        print(f"\n👛 Wallet:")
        print(f"   Private Key: {cls.OWNER_PRIVATE_KEY[:10]}...{cls.OWNER_PRIVATE_KEY[-4:]}")
        print(f"   Proxy: {cls.PROXY_ADDRESS}")
        
        print(f"\n📊 Trading:")
        print(f"   Trade Size: ${cls.TRADE_SIZE}")
        print(f"   Buy Entry Edge (base): {cls.BUY_ENTRY_EDGE*100:.2f}% | Max Block Edge: {cls.MAX_ENTRY_EDGE*100:.2f}%")
        print(f"   Buy Entry Edge: {cls.BUY_ENTRY_EDGE*100:.1f}%")
        print(f"   Taker Fee: {cls.TAKER_FEE*100:.2f}%")
        print(f"   Max Position: ${cls.MAX_POSITION_SIZE}")
        print(f"   Max Daily Trades: {cls.MAX_DAILY_TRADES}")
        print(f"   Default Entry TIF: {cls.ORDER_ENTRY_TIF}")
        print(f"   Default Exit TIF:  {cls.ORDER_EXIT_TIF}")
        print(f"   Strict Entry TIF:  {cls.STRICT_ENTRY_TIF}")
        
        print(f"\n📈 Model:")
        print(f"   Volatility Window: {cls.VOLATILITY_WINDOW} periods (24h)")
        print(f"   Update Interval: {cls.UPDATE_INTERVAL}s")
        # OFI strategy defaults
        print(f"   Polymarket Orderbook OFI: {'ENABLED' if getattr(cls,'ENABLE_ORDERBOOK_OFI', False) else 'DISABLED (default)'}")
        print(f"   Binance OFI reporting: {'ENABLED (default)' if getattr(cls,'ENABLE_BINANCE_OFI_REPORTING', False) else 'DISABLED'}")
        
        if cls.TELEGRAM_TOKEN:
            print(f"\n📱 Telegram: Enabled")
        else:
            print(f"\n📱 Telegram: Disabled")
        
        print("="*70)


# Validate configuration on import
if __name__ == "__main__":
    Config.display()
    Config.validate()
��"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92@file:///c:/Users/rovie%20segubre/btc_15min_options_bot/config.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot