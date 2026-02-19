ʦdef get_sigma_vw(df, window=400):
    """
    Calculate volume-weighted volatility (sigma_vw) from OHLCV DataFrame.
    window: lookback window for rolling mean/std (default 288 for 24h of 5m data)
    Returns annualized sigma_vw (float)
    """
    if len(df) < window + 2:
        return np.nan
    df = df.copy()
    df['log_return'] = np.log(df['close'] / df['close'].shift(1))
    df['vol_factor'] = df['volume'] / df['volume'].rolling(window=window).mean()
    df['vw_return'] = df['log_return'] * df['vol_factor']
    vw_vol = df['vw_return'].rolling(window=window).std()
    PERIODS_PER_YEAR = 365 * 24
    sigma_vw = vw_vol.iloc[-1] * np.sqrt(PERIODS_PER_YEAR)
    return sigma_vw

def get_sigma_garman_klass(df, window=400, periods_per_year=35040):
    """
    Calculate Garman-Klass volatility (sigma_gk) from OHLCV DataFrame.
    Uses Open, High, Low, Close prices for better efficiency than Close-to-Close.
    window: lookback window for rolling mean (default 400)
    periods_per_year: annualization factor (default 35040 for 15m data)
    Returns annualized sigma_gk (float)
    """
    if len(df) < window + 2:
        return np.nan
    
    df = df.copy()
    log_hl = np.log(df['high'] / df['low']) ** 2
    log_co = np.log(df['close'] / df['open']) ** 2
    
    # Garman-Klass formula: 0.5 * ln(H/L)^2 - (2*ln(2)-1) * ln(C/O)^2
    # 2*ln(2)-1 approx 0.386
    df['gk_var'] = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
    
    # Calculate rolling volatility
    sigma_gk = np.sqrt(df['gk_var'].rolling(window=window).mean().iloc[-1] * periods_per_year)
    return sigma_gk

def calculate_sigma_atr(df, window=2, atr_period=14):
    """
    Calculate ATR-based volatility (sigma_atr) from OHLCV DataFrame.
    Optimized for short-term volatility detection in 1-hour options.
    
    This method provides perfect consistency with ATR baseline comparison.
    
    Args:
        df: OHLCV DataFrame with high, low, close columns
        window: How many recent ATR values to average (default 2 for last 2 hours with 1h candles)
        atr_period: ATR calculation period (default 14, standard setting)
    
    Returns:
        Annualized sigma_atr (float) - ready for Black-Scholes pricing
    
    Example:
        # For 1h candles: last 2 hours of volatility
        sigma_1h = calculate_sigma_atr(df_1h, window=2, atr_period=14)
        
        # For 5m candles: last 1 hour of volatility (12 candles)
        sigma_5m = calculate_sigma_atr(df_5m, window=12, atr_period=14)
    """
    import pandas_ta as ta
    
    # Need at least atr_period + window candles
    min_candles = atr_period + window
    if df is None or len(df) < min_candles:
        return np.nan
    
    try:
        # Calculate ATR using pandas_ta
        atr_values = ta.atr(df['high'], df['low'], df['close'], length=atr_period)
        
        if atr_values is None or len(atr_values) == 0:
            return np.nan
        
        # Get recent ATR using Exponential Moving Average (more weight on recent values)
        # EMA is more responsive to recent volatility changes than simple mean
        recent_atr = atr_values.iloc[-window:].ewm(span=window, adjust=False).mean().iloc[-1]
        
        # Get current price
        current_price = df['close'].iloc[-1]
        
        if current_price == 0 or np.isnan(recent_atr):
            return np.nan
        
        # Convert ATR to percentage of price
        atr_pct = recent_atr / current_price
        
        # Annualize the volatility
        # For crypto (24/7 trading):
        # - 1h candles: 365 * 24 = 8760 periods/year
        # - 5m candles: 365 * 24 * 12 = 105,120 periods/year
        
        # Detect timeframe from index if possible
        try:
            if hasattr(df.index, 'freq'):
                freq_str = str(df.index.freq)
            else:
                # Estimate from time difference between candles
                time_diff = (df.index[-1] - df.index[-2]).total_seconds() / 60  # minutes
                if time_diff < 10:  # 5-minute candles
                    freq_str = '5T'
                elif time_diff < 90:  # 1-hour candles
                    freq_str = '1H'
                else:
                    freq_str = '1H'  # default to 1h
        except:
            freq_str = '1H'  # default
        
        # Determine periods per year based on timeframe
        if '5' in freq_str or '5T' in freq_str or '5min' in freq_str.lower():
            periods_per_year = 365 * 24 * 12  # 5-minute candles
        else:
            periods_per_year = 365 * 24  # 1-hour candles (default)
        
        # Annualize: sigma = atr_pct * sqrt(periods_per_year)
        sigma_atr = atr_pct * np.sqrt(periods_per_year)
        
        # Clamp sigma to reasonable bounds to prevent extreme values
        # Min 0.2 (very calm market), Max 1.5 (very volatile)
        sigma_atr = max(0.2, min(1.5, sigma_atr))
        
        return sigma_atr
    
    except Exception as e:
        print(f"    [WARN] Error calculating ATR sigma: {e}")
        return np.nan

import ccxt
import pandas as pd
import numpy as np
import requests

# Try multiple exchanges in order of preference
EXCHANGES_TO_TRY = [
    'binance',      # Primary
    'coinbasepro',  # Alternative 1
    'kraken',       # Alternative 2
    'bitfinex',     # Alternative 3
    'okx',          # Alternative 4
]

BINANCE_SYMBOL = 'BTC/USDT'
OHLCV_TIMEFRAME = '15m'
OHLCV_LIMIT = 600

def fetch_ohlcv_for_timeframe(timeframe, limit=None):
    if limit is None:
        limit = OHLCV_LIMIT

    # Check 5m cache first (optimization - saves 100-200ms)
    if timeframe == '5m':
        current_time = time.time()
        if (_candle_5m_cache['data'] is not None and 
            current_time - _candle_5m_cache['timestamp'] < _candle_5m_cache['ttl']):
            return _candle_5m_cache['data'].copy()

    last_error = None

    # Try each exchange until one works
    for exchange_name in EXCHANGES_TO_TRY:
        try:
            print(f"    Trying {exchange_name} for OHLCV data...")
            exchange_class = getattr(ccxt, exchange_name)
            exchange = exchange_class()

            # Set symbol based on exchange
            symbol = BINANCE_SYMBOL
            if exchange_name == 'coinbasepro':
                symbol = 'BTC/USD'
            elif exchange_name == 'kraken':
                symbol = 'BTC/USD'
            elif exchange_name == 'bitfinex':
                symbol = 'BTC/USD'
            elif exchange_name == 'okx':
                symbol = 'BTC/USDT'

            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            # Cache 5m candles (optimization)
            if timeframe == '5m':
                _candle_5m_cache['data'] = df.copy()
                _candle_5m_cache['timestamp'] = time.time()

            print(f"    [OK] Successfully fetched data from {exchange_name}")
            return df

        except Exception as e:
            print(f"    [ERR] {exchange_name} failed: {str(e)[:100]}...")
            last_error = e
            continue

    # If all exchanges failed, raise the last error
    print(f"    [ERR] All exchanges failed. Last error: {last_error}")
    raise last_error

def fetch_ohlcv_dataframe():
    return fetch_ohlcv_for_timeframe(OHLCV_TIMEFRAME)


# ============================================================================
# RUBBER BAND MEAN REVERSION STRATEGY
# ============================================================================

import time
import pandas_ta as ta

# Cache for 1-minute candles (candle-aligned)
_candle_1m_cache = {
    'data': None,
    'last_candle_time': None,  # Track last candle timestamp for candle-aligned refresh
    'timestamp': 0,
    'ttl': 60  # Fallback TTL if candle check fails
}

# Cache for 5-minute candles (candle-aligned)
_candle_5m_cache = {
    'data': None,
    'last_candle_time': None,
    'timestamp': 0,
    'ttl': 60
}

# Cache for 1-hour candles (candle-aligned)
_candle_1h_cache = {
    'data': None,
    'last_candle_time': None,
    'timestamp': 0,
    'ttl': 3600
}

# Cache for ATR metrics (recalculate when 1h candles update)
_atr_metrics_cache = {
    'data': None,
    'candle_count': 0,
    'last_candle_time': None,  # Track for candle-aligned refresh
    'timestamp': 0,
    'ttl': 3600
}

# Spam control for warnings (print once per minute)
_last_warning_time = {
    'reduced_indicators': 0,
    'atr_metrics': 0
}
_warning_cooldown = 60  # seconds

# ADX error throttling defaults
_last_adx_error_time = 0.0
_adx_error_cooldown = 60.0


def fetch_1m_candles(limit=100):
    """
    Fetch 1-minute candles with candle-aligned caching.
    Only fetches new data when a new candle has formed.
    
    Args:
        limit: Number of candles to fetch (default 100 for indicators)
    
    Returns:
        DataFrame with OHLCV data indexed by timestamp
    """
    global _candle_1m_cache
    
    current_time = time.time()
    
    # Quick check: if we have cached data and it's within the same minute, return it
    # This avoids unnecessary API calls mid-candle
    if _candle_1m_cache['data'] is not None and _candle_1m_cache['last_candle_time'] is not None:
        # Calculate expected next candle time (current candle close + 60 seconds)
        last_candle_ts = _candle_1m_cache['last_candle_time']
        if hasattr(last_candle_ts, 'timestamp'):
            last_candle_unix = last_candle_ts.timestamp()
        else:
            last_candle_unix = float(last_candle_ts) / 1000 if last_candle_ts > 1e12 else float(last_candle_ts)
        
        # If current time is still within the current candle period, use cache
        next_candle_time = last_candle_unix + 60  # 1-minute candles
        if current_time < next_candle_time:
            return _candle_1m_cache['data']
    
    # Fetch fresh data (either first fetch or new candle expected)
    try:
        df = fetch_ohlcv_for_timeframe('1m', limit=limit)
        
        if df is None or len(df) == 0:
            print(f"    [WARN] fetch_ohlcv_for_timeframe returned empty data")
            if _candle_1m_cache['data'] is not None:
                return _candle_1m_cache['data']
            return None
        
        # Check if this is actually a new candle
        new_candle_time = df.index[-1]
        if (_candle_1m_cache['last_candle_time'] is not None and 
            new_candle_time == _candle_1m_cache['last_candle_time']):
            # Same candle, just update timestamp
            _candle_1m_cache['timestamp'] = current_time
            return _candle_1m_cache['data']
        
        # New candle! Update cache
        _candle_1m_cache['data'] = df
        _candle_1m_cache['last_candle_time'] = new_candle_time
        _candle_1m_cache['timestamp'] = current_time
        
        return df
    
    except Exception as e:
        print(f"    [ERR] Failed to fetch 1m candles: {e}")
        if _candle_1m_cache['data'] is not None:
            return _candle_1m_cache['data']
        return None


def fetch_1h_candles(limit=50):
    """
    Fetch 1-hour candles with candle-aligned caching.
    Only fetches new data when a new hourly candle has formed.
    
    Args:
        limit: Number of candles to fetch (default 50 for ATR calculation)
    
    Returns:
        DataFrame with OHLCV data indexed by timestamp
    """
    global _candle_1h_cache
    
    current_time = time.time()
    
    # Quick check: if we have cached data and it's within the same hour, return it
    if _candle_1h_cache['data'] is not None and _candle_1h_cache['last_candle_time'] is not None:
        last_candle_ts = _candle_1h_cache['last_candle_time']
        if hasattr(last_candle_ts, 'timestamp'):
            last_candle_unix = last_candle_ts.timestamp()
        else:
            last_candle_unix = float(last_candle_ts) / 1000 if last_candle_ts > 1e12 else float(last_candle_ts)
        
        # If current time is still within the current candle period, use cache
        next_candle_time = last_candle_unix + 3600  # 1-hour candles
        if current_time < next_candle_time:
            return _candle_1h_cache['data']
    
    # Fetch fresh data
    try:
        df = fetch_ohlcv_for_timeframe('1h', limit=limit)
        
        if df is None or len(df) == 0:
            print(f"    [WARN] fetch_ohlcv_for_timeframe('1h') returned empty data")
            if _candle_1h_cache['data'] is not None:
                return _candle_1h_cache['data']
            return None
        
        # Check if this is actually a new candle
        new_candle_time = df.index[-1]
        if (_candle_1h_cache['last_candle_time'] is not None and 
            new_candle_time == _candle_1h_cache['last_candle_time']):
            # Same candle, just update timestamp
            _candle_1h_cache['timestamp'] = current_time
            return _candle_1h_cache['data']
        
        # New candle! Update cache
        _candle_1h_cache['data'] = df
        _candle_1h_cache['last_candle_time'] = new_candle_time
        _candle_1h_cache['timestamp'] = current_time
        print(f"    [INFO] New 1h candle detected - refreshed cache ({len(df)} candles)")
        
        return df
    
    except Exception as e:
        print(f"    [ERR] Failed to fetch 1h candles: {e}")
        if _candle_1h_cache['data'] is not None:
            return _candle_1h_cache['data']
        return None


def calculate_atr_metrics(
    df_1h: pd.DataFrame,
    current_price: float,
    lookback_candles: int = 14,
    atr_period: int = 14
) -> dict:
    """
    Calculate ATR metrics from 1-hour candles for volatility regime detection.
    Returns current ATR%, baseline ATR% (14-hour average), ratio, and regime classification.
    
    Args:
        df_1h: DataFrame with 1-hour OHLCV candles
        current_price: Current BTC price
        lookback_candles: Number of candles for baseline (default 14 = 14 hours)
        atr_period: ATR calculation period (default 14)
    
    Returns:
        dict: {
            'current_atr_pct': float,  # Current ATR as % of price
            'baseline_atr_pct': float,  # Baseline (7hr avg) ATR as % of price
            'vol_ratio': float,  # current / baseline
            'deviation_pct': float,  # Absolute deviation percentage
            'regime': str,  # 'HIGH_VOL', 'LOW_VOL', or 'NORMAL_VOL'
            'raw_current_atr': float,  # Raw ATR value
            'raw_baseline_atr': float  # Raw baseline ATR
        }
    """
    global _atr_metrics_cache
    
    current_time = time.time()
    
    # Check if cache is valid (same candle count + within TTL)
    # Using candle count as a proxy for "has new data arrived"
    if df_1h is not None and (_atr_metrics_cache['data'] is not None and
        _atr_metrics_cache['candle_count'] == len(df_1h) and
        current_time - _atr_metrics_cache['timestamp'] < _atr_metrics_cache['ttl']):
        # Cached - return immediately without recalculating
        return _atr_metrics_cache['data']
    
    try:
        if df_1h is None or len(df_1h) < atr_period + lookback_candles:
            return {
                'current_atr_pct': 0.0,
                'baseline_atr_pct': 0.0,
                'vol_ratio': 1.0,
                'deviation_pct': 0.0,
                'regime': 'NORMAL_VOL',
                'raw_current_atr': 0.0,
                'raw_baseline_atr': 0.0,
                'error': f'Insufficient data: {len(df_1h) if df_1h is not None else 0} candles'
            }
        
        # Calculate ATR using pandas_ta (14-period by default)
        high = df_1h['high']
        low = df_1h['low']
        close = df_1h['close']
        
        atr_values = ta.atr(high, low, close, length=atr_period)
        
        if atr_values is None or len(atr_values) == 0:
            return {
                'current_atr_pct': 0.0,
                'baseline_atr_pct': 0.0,
                'vol_ratio': 1.0,
                'deviation_pct': 0.0,
                'regime': 'NORMAL_VOL',
                'raw_current_atr': 0.0,
                'raw_baseline_atr': 0.0,
                'error': 'ATR calculation failed'
            }
        
        # Current ATR (most recent value)
        current_atr = atr_values.iloc[-1]
        
        # Baseline ATR: average of last N candles
        baseline_atr = atr_values.iloc[-lookback_candles:].mean()
        
        # Convert to percentages of price (no annualization needed for ratios)
        current_atr_pct = (current_atr / current_price) * 100
        baseline_atr_pct = (baseline_atr / current_price) * 100
        
        # Calculate ratio and deviation
        if baseline_atr_pct > 0:
            vol_ratio = current_atr_pct / baseline_atr_pct
            deviation_pct = abs(vol_ratio - 1.0) * 100
        else:
            vol_ratio = 1.0
            deviation_pct = 0.0
        
        # Classify regime (using 10% threshold like volatility regime strategy)
        if deviation_pct < 10:
            regime = 'NORMAL_VOL'
        elif vol_ratio < 1.0:
            regime = 'LOW_VOL'
        else:
            regime = 'HIGH_VOL'
        
        result = {
            'current_atr_pct': current_atr_pct,
            'baseline_atr_pct': baseline_atr_pct,
            'vol_ratio': vol_ratio,
            'deviation_pct': deviation_pct,
            'regime': regime,
            'raw_current_atr': current_atr,
            'raw_baseline_atr': baseline_atr
        }
        
        # Update cache
        _atr_metrics_cache['data'] = result
        _atr_metrics_cache['candle_count'] = len(df_1h)
        _atr_metrics_cache['timestamp'] = current_time
        
        return result
    
    except Exception as e:
        print(f"    [WARN] Error calculating ATR sigma: {e}")
        return {
            'current_atr_pct': 0.0,
            'baseline_atr_pct': 0.0,
            'vol_ratio': 1.0,
            'deviation_pct': 0.0,
            'regime': 'NORMAL_VOL',
            'raw_current_atr': 0.0,
            'raw_baseline_atr': 0.0,
            'error': str(e)
        }


def calculate_rubber_band_amplification(
    current_price: float,
    last_signal_time: float,
    bb_period: int = 20,
    bb_std: float = 2.0,
    rsi_period: int = 14,
    rsi_oversold: float = 30.0,
    rsi_overbought: float = 70.0,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
    adx_period: int = 14,
    adx_threshold: float = 25.0,
    volume_spike_multiplier: float = 2.0,
    cooldown_seconds: float = 300.0
) -> dict:
    """
    Calculate mean reversion amplification with price velocity and safety filters
    
    Strategy (ALL conditions required):
    - OVERSOLD: Price in lower 20% of BB range + RSI < 30 + Negative velocity decelerating → Amplify UP 10%
    - OVERBOUGHT: Price in upper 20% of BB range + RSI > 70 + Positive velocity decelerating → Amplify DOWN 10%
    
    Price Velocity:
    - 5-minute velocity lookback
    - Requires momentum exhaustion (deceleration)
    - Min velocity: 0.2%, Min acceleration change: 0.1%
    
    Safety Filters (need 3 out of 4):
    1. ATR: Skip if volatility > 1.5x average (trending market)
    2. Cooldown: Skip if < 5 min since last signal
    3. ADX: Skip if > 25 (strong trend)
    4. Volume: Skip if > 2x average (panic/FOMO)
    
    Args:
        current_price: Current BTC price
        last_signal_time: Timestamp of last rubber band signal
        bb_period: Bollinger Bands period (default 20)
        bb_std: Bollinger Bands standard deviation (default 2.0)
        rsi_period: RSI period (default 14)
        rsi_oversold: RSI oversold threshold (default 30)
        rsi_overbought: RSI overbought threshold (default 70)
        atr_period: ATR period (default 14)
        atr_multiplier: ATR threshold multiplier (default 1.5)
        adx_period: ADX period (default 14)
        adx_threshold: ADX trend strength threshold (default 25)
        volume_spike_multiplier: Volume spike threshold (default 2.0)
        cooldown_seconds: Cooldown period between signals (default 300)
    
    Returns:
        dict: {
            'amp_up': float (1.0 - unlimited),
            'amp_down': float (1.0 - unlimited),
            'signal': str ('OVERSOLD', 'OVERBOUGHT', 'NEUTRAL', 'FILTERED'),
            'reason': str (human-readable explanation),
            'filters': dict (filter statuses),
            'indicators': dict (indicator values)
        }
    """
    try:
        # PRE-CHECK: Quick price range analysis to skip expensive calculation
        # Only do full calculation if price is near extremes (top/bottom 30% of recent range)
        df_quick = fetch_1m_candles(limit=20)  # Lightweight check with fewer candles
        if df_quick is not None and len(df_quick) >= 20:
            recent_high = df_quick['high'].max()
            recent_low = df_quick['low'].min()
            price_range = recent_high - recent_low
            
            if price_range > 0:
                # Calculate where current price sits in the range (0 = bottom, 1 = top)
                price_position = (current_price - recent_low) / price_range
                
                # If price is in middle 40% of range (0.3 to 0.7), likely neutral
                if 0.3 < price_position < 0.7:
                    return {
                        'amp_up': 1.0,
                        'amp_down': 1.0,
                        'signal': 'NEUTRAL',
                        'reason': f'Price in neutral zone ({price_position*100:.1f}% of recent range)',
                        'filters': {},
                        'indicators': {'price_position': price_position}
                    }
        
        # Fetch full 1-minute candles for detailed analysis
        df = fetch_1m_candles(limit=100)
        
        min_required = max(bb_period, rsi_period, atr_period, adx_period) + 2  # Reduced buffer
        if df is None:
            return {
                'amp_up': 1.0,
                'amp_down': 1.0,
                'signal': 'NEUTRAL',
                'reason': 'Failed to fetch 1m candle data (API issue)',
                'filters': {},
                'indicators': {}
            }
        
        # ADAPTIVE FALLBACK: Use what we have if close enough
        if len(df) < min_required:
            # If we have at least 15 candles, use reduced periods
            if len(df) >= 15:
                # Only print warning once per minute to reduce log spam
                global _last_warning_time, _warning_cooldown
                current_time = time.time()
                if current_time - _last_warning_time.get('reduced_indicators', 0) >= _warning_cooldown:
                    print(f"    [WARN] Using reduced indicator periods (have {len(df)} candles)")
                    _last_warning_time['reduced_indicators'] = current_time
                bb_period = min(bb_period, len(df) - 2)
                rsi_period = min(rsi_period, len(df) - 2)
                atr_period = min(atr_period, len(df) - 2)
                adx_period = min(adx_period, len(df) - 2)
            else:
                return {
                    'amp_up': 1.0,
                    'amp_down': 1.0,
                    'signal': 'NEUTRAL',
                    'reason': f'Insufficient candles: {len(df)}/{min_required} required (need at least 15)',
                    'filters': {},
                    'indicators': {}
                }
        
        # Calculate indicators using pandas_ta
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Bollinger Bands
        bb = ta.bbands(close, length=bb_period, std=bb_std)
        
        # Get actual column names (pandas_ta might use different naming)
        # Column format is usually: BBL_period_std, BBM_period_std, BBU_period_std, BBB_period_std, BBP_period_std
        bb_cols = bb.columns.tolist()
        
        # Find the upper, middle, lower columns (they start with BBU, BBM, BBL)
        bb_upper_col = [col for col in bb_cols if col.startswith('BBU_')][0]
        bb_middle_col = [col for col in bb_cols if col.startswith('BBM_')][0]
        bb_lower_col = [col for col in bb_cols if col.startswith('BBL_')][0]
        
        bb_upper = bb[bb_upper_col].iloc[-1]
        bb_middle = bb[bb_middle_col].iloc[-1]
        bb_lower = bb[bb_lower_col].iloc[-1]
        
        # RSI
        rsi_values = ta.rsi(close, length=rsi_period)
        rsi = rsi_values.iloc[-1]
        
        # ATR
        atr_values = ta.atr(high, low, close, length=atr_period)
        current_atr = atr_values.iloc[-1]
        avg_atr = atr_values.mean()
        
        # MACD (12, 26, 9)
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None:
             # Columns are usually MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
             # Map to standard names
             macd_col = [c for c in macd_df.columns if c.startswith('MACD_')][0]
             macd_sig_col = [c for c in macd_df.columns if c.startswith('MACDs_')][0]
             macd_hist_col = [c for c in macd_df.columns if c.startswith('MACDh_')][0]
             macd_val = macd_df[macd_col].iloc[-1]
             macd_sig = macd_df[macd_sig_col].iloc[-1]
             macd_hist = macd_df[macd_hist_col].iloc[-1]
        else:
             macd_val, macd_sig, macd_hist = 0.0, 0.0, 0.0
             
        # Stochastic (14, 3, 3)
        stoch_df = ta.stoch(high, low, close, k=14, d=3, smooth_k=3)
        if stoch_df is not None:
             stoch_k_col = [c for c in stoch_df.columns if c.startswith('STOCHk_')][0]
             stoch_d_col = [c for c in stoch_df.columns if c.startswith('STOCHd_')][0]
             stoch_k = stoch_df[stoch_k_col].iloc[-1]
             stoch_d = stoch_df[stoch_d_col].iloc[-1]
        else:
             stoch_k, stoch_d = 0.0, 0.0
             
        # ROC (Rate of Change) - 9 period
        roc_series = ta.roc(close, length=9)
        roc_val = roc_series.iloc[-1] if roc_series is not None else 0.0
        
        # ADX - Prefer resampled short timeframe (3-minute) using configured ADX period
        try:
            from config import Config
            configured_period = getattr(Config, 'ADX_PERIOD', adx_period)
            timeframe_min = getattr(Config, 'ADX_TIMEFRAME_MINUTES', 3)
        except Exception:
            configured_period = adx_period
            timeframe_min = 3

        # Resample 1m candles to 3m and use ADX on resampled if enough candles exist
        adx = 0.0
        try:
            df_resampled = df.resample(f"{timeframe_min}min").agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()

            # Use cleaned resampled series (drop NaNs) and ensure we have enough rows
            adx_values = None
            if df_resampled is not None:
                df_clean = df_resampled[['high', 'low', 'close']].dropna()
                if len(df_clean) >= configured_period + 2:
                    adx_values = ta.adx(df_clean['high'], df_clean['low'], df_clean['close'], length=configured_period)
            # If resampled not usable, try raw 1-minute candles
            if adx_values is None:
                df_clean_1m = pd.concat([high, low, close], axis=1).dropna()
                if len(df_clean_1m) >= configured_period + 2:
                    adx_values = ta.adx(df_clean_1m['high'], df_clean_1m['low'], df_clean_1m['close'], length=configured_period)

            # Defensive checks: some pandas-ta versions or bad input can return None or missing columns
            if adx_values is None or f'ADX_{configured_period}' not in getattr(adx_values, 'columns', []):
                raise ValueError('ADX calculation returned invalid result')

            adx = float(adx_values[f'ADX_{configured_period}'].iloc[-1])
        except Exception as e:
            # Throttle repeated ADX error logs to avoid noisy logs in production
            global _last_adx_error_time, _adx_error_cooldown

            now = time.time()
            if now - _last_adx_error_time >= _adx_error_cooldown:
                print(f"    [ERR] ADX calculation failed: {e} (len(df)={len(df)}, len(df_resampled)={len(df_resampled) if 'df_resampled' in locals() else 'NA'})")
                _last_adx_error_time = now

            # Best-effort fallback and safe default
            try:
                df_clean_1m = pd.concat([high, low, close], axis=1).dropna()
                if len(df_clean_1m) >= configured_period + 2:
                    adx_values = ta.adx(df_clean_1m['high'], df_clean_1m['low'], df_clean_1m['close'], length=configured_period)
                    if adx_values is not None and f'ADX_{configured_period}' in getattr(adx_values, 'columns', []):
                        adx = float(adx_values[f'ADX_{configured_period}'].iloc[-1])
                    else:
                        adx = 0.0
                else:
                    adx = 0.0
            except Exception:
                adx = 0.0
        
        # Volume
        avg_volume = volume.rolling(window=20).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # ===== SAFETY FILTERS =====
        
        # Filter 1: ATR (Volatility)
        atr_ok = current_atr <= (avg_atr * atr_multiplier)
        
        # Filter 2: Cooldown
        current_time = time.time()
        cooldown_ok = (current_time - last_signal_time) >= cooldown_seconds
        
        # Filter 3: ADX (Trend Strength)
        adx_ok = bool(adx <= adx_threshold)
        
        # Filter 4: Volume Spike
        volume_ok = volume_ratio <= volume_spike_multiplier
        
        # Check if filters pass: Allow 1 filter to fail (need at least 3 out of 4 passing)
        filter_results = [atr_ok, cooldown_ok, adx_ok, volume_ok]
        passed_filters = sum(filter_results)
        all_filters_pass = passed_filters >= 3  # Need at least 3 out of 4 filters to pass
        
        # ===== PRICE VELOCITY CALCULATION =====
        # Calculate velocity (rate of change) and acceleration over 5 minutes
        lookback = 5  # 5-minute velocity lookback
        
        if len(close) >= lookback * 2:
            # Current velocity (last 5 minutes): % change per period
            velocity_now = ((close.iloc[-1] - close.iloc[-lookback]) / close.iloc[-lookback]) * 100
            
            # Previous velocity (5-10 minutes ago)
            velocity_prev = ((close.iloc[-lookback] - close.iloc[-lookback*2]) / close.iloc[-lookback*2]) * 100
            
            # Acceleration = change in velocity (positive = accelerating, negative = decelerating)
            acceleration = velocity_now - velocity_prev
        else:
            velocity_now = 0.0
            acceleration = 0.0
        
        # Velocity thresholds for meaningful signals
        min_velocity = 0.2  # Minimum 0.2% move to consider
        min_acceleration = 0.1  # Minimum 0.1% change in velocity
        
        # ===== SIGNAL DETECTION WITH PRICE VELOCITY =====
        
        signal = 'NEUTRAL'
        reason = ''
        amp_up = 1.0
        amp_down = 1.0
        
        # Calculate BB range position (0 = lower band, 0.5 = middle, 1 = upper band)
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_position = (current_price - bb_lower) / bb_range
        else:
            bb_position = 0.5
        
        # OVERSOLD condition (Amplify UP)
        # Requires: RSI < 30 + Negative velocity decelerating (BB position check REMOVED - works at any level)
        if rsi < rsi_oversold:
            # Check velocity: Must be falling (negative) AND decelerating (positive acceleration)
            velocity_confirms = (velocity_now < -min_velocity and acceleration > min_acceleration)
            
            if velocity_confirms:
                if all_filters_pass:
                    # Fixed 8% amplification (more conservative)
                    amp_up = 1.08
                    signal = 'OVERSOLD'
                    reason = f'OVERSOLD BOUNCE (BB_Pos={bb_position*100:.1f}%, RSI={rsi:.1f}, Vel={velocity_now:+.2f}% decelerating)'
                else:
                    signal = 'FILTERED'
                    reason = f'OVERSOLD+VELOCITY detected but FILTERED ('
                    if not atr_ok:
                        reason += f'High volatility: ATR={current_atr:.1f} > {avg_atr*atr_multiplier:.1f}, '
                    if not cooldown_ok:
                        reason += f'Cooldown: {(current_time - last_signal_time):.0f}s < {cooldown_seconds:.0f}s, '
                    if not adx_ok:
                        reason += f'Strong trend: ADX={adx:.1f} > {adx_threshold:.1f}, '
                    if not volume_ok:
                        reason += f'Volume spike: {volume_ratio:.1f}x > {volume_spike_multiplier:.1f}x, '
                    reason = reason.rstrip(', ') + ')'
            else:
                reason = f'OVERSOLD but no velocity confirmation (BB_Pos={bb_position*100:.1f}%, RSI={rsi:.1f}, Vel={velocity_now:+.2f}%, Accel={acceleration:+.2f}%)'
        
        # OVERBOUGHT condition (Amplify DOWN)
        # Requires: RSI > 70 + Positive velocity decelerating (BB position check REMOVED - works at any level)
        elif rsi > rsi_overbought:
            # Check velocity: Must be rising (positive) AND decelerating (negative acceleration)
            velocity_confirms = (velocity_now > min_velocity and acceleration < -min_acceleration)
            
            if velocity_confirms:
                if all_filters_pass:
                    # Fixed 8% amplification (more conservative)
                    amp_down = 1.08
                    signal = 'OVERBOUGHT'
                    reason = f'OVERBOUGHT DROP (BB_Pos={bb_position*100:.1f}%, RSI={rsi:.1f}, Vel={velocity_now:+.2f}% decelerating)'
                else:
                    signal = 'FILTERED'
                    reason = f'OVERBOUGHT+VELOCITY detected but FILTERED ('
                    if not atr_ok:
                        reason += f'High volatility: ATR={current_atr:.1f} > {avg_atr*atr_multiplier:.1f}, '
                    if not cooldown_ok:
                        reason += f'Cooldown: {(current_time - last_signal_time):.0f}s < {cooldown_seconds:.0f}s, '
                    if not adx_ok:
                        reason += f'Strong trend: ADX={adx:.1f} > {adx_threshold:.1f}, '
                    if not volume_ok:
                        reason += f'Volume spike: {volume_ratio:.1f}x > {volume_spike_multiplier:.1f}x, '
                    reason = reason.rstrip(', ') + ')'
            else:
                reason = f'OVERBOUGHT but no velocity confirmation (BB_Pos={bb_position*100:.1f}%, RSI={rsi:.1f}, Vel={velocity_now:+.2f}%, Accel={acceleration:+.2f}%)'
        
        # NEUTRAL condition
        else:
            if 0.2 < bb_position < 0.8:
                reason = f'NEUTRAL (BB_Pos={bb_position*100:.1f}%, RSI={rsi:.1f})'
            else:
                reason = f'No signal (BB_Pos={bb_position*100:.1f}%, RSI={rsi:.1f}, need both extreme position + RSI + velocity)'
        
        return {
            'amp_up': amp_up,
            'amp_down': amp_down,
            'signal': signal,
            'reason': reason,
            'filters': {
                'atr_ok': atr_ok,
                'cooldown_ok': cooldown_ok,
                'adx_ok': adx_ok,
                'volume_ok': volume_ok
            },
            'indicators': {
                'bb_upper': bb_upper,
                'bb_middle': bb_middle,
                'bb_lower': bb_lower,
                'bb_position': bb_position,
                'rsi': rsi,
                'atr': current_atr,
                'atr_avg': avg_atr,
                'adx': adx,
                'volume_ratio': volume_ratio,
                'velocity': velocity_now,
                'acceleration': acceleration,
                'macd': macd_val,
                'macd_signal': macd_sig,
                'macd_hist': macd_hist,
                'stoch_k': stoch_k,
                'stoch_d': stoch_d,
                'roc': roc_val
            }
        }
    
    except Exception as e:
        print(f"    [ERR] Error calculating rubber band amplification: {e}")
        import traceback
        traceback.print_exc()
        return {
            'amp_up': 1.0,
            'amp_down': 1.0,
            'signal': 'ERROR',
            'reason': f'Calculation error: {str(e)[:100]}',
            'filters': {},
            'indicators': {}
        }
ʦ"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Kfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/indicator_filters.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot