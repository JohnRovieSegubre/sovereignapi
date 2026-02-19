Ö!
import os
import csv
from datetime import datetime

OUTPUT_DIR = "ab_test_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def reset_file(filename, headers):
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        print(f"[OK] Reset {filename}")
    except Exception as e:
        print(f"[ERR] Failed to reset {filename}: {e}")

# --- Market Data Logger Headers ---
cols_1m = [
    "timestamp", "open", "high", "low", "close", "volume",
    "rsi", "macd", "macd_signal", "macd_hist",
    "stoch_k", "stoch_d", "roc",
    "atr", "adx", "plus_di", "minus_di",
    "obv", "vwap", 
    "bb_upper", "bb_middle", "bb_lower",
    "velocity", "acceleration",
    "binance_ofi", "sigma_realized", 
    "bid_ask_spread", "hour_utc", "day_of_week", "market_session",
    "trade_active"
]

cols_1h = [
    "timestamp", "open", "high", "low", "close", "volume",
    "rsi", "macd", "macd_signal", "macd_hist",
    "atr", "adx",
    "trend_regime", "volatility_regime",
    "sigma_realized", "sigma_implied"
]

cols_votes = [
    "timestamp", "btc_price", "signal", 
    "momentum_amp_up", "momentum_amp_down",
    "velocity_amp_up", "velocity_amp_down",
    "binance_ofi_amp_up", "binance_ofi_amp_down",
    "polymarket_ofi_amp_up", "polymarket_ofi_amp_down",
    "volume_profile_amp_up", "volume_profile_amp_down",
    "obv_divergence_amp_up", "obv_divergence_amp_down",
    "total_amp_up", "total_amp_down"
]

cols_near_misses = [
    "timestamp", "config", "side", "edge", "threshold", "btc_price", "market_slug"
]

# --- Strategy AB Tester Headers ---
cols_ab_trades = [
    "timestamp", "config", "signal", "side", "entry_price", 
    "exit_price", "shares", "pnl", "pnl_pct", "btc_price",
    "amp_up", "amp_down", "market_slug", "status", "exit_reason"
]

cols_ab_summary = [
    "timestamp", "config", "balance", "total_pnl", "total_trades",
    "winning_trades", "losing_trades", "win_rate", "current_equity"
]

# Dynamic Strategy Votes Header (must match strategy_ab_tester.py logic)
vote_keys = sorted([
    "momentum", "price_velocity", "binance_ofi", "polymarket_ofi", 
    "volume_profile", "obv_divergence", "vol_regime", "vol_percentile",
    "orderbook", "adx_filter", "htf_filter", "exhaustion", "cooldown"
])

cols_ab_votes = ["timestamp", "market_slug", "btc_price", "config", "final_vote", "signal"]
for key in vote_keys:
    cols_ab_votes.append(f"{key}_amp")

# --- Execute Reset ---
if __name__ == "__main__":
    print(f"Resetting CSV logs in {OUTPUT_DIR}...")
    
    # reset_file("btc_data_1m.csv", cols_1m)
    # reset_file("btc_data_1h.csv", cols_1h)
    
    # Note: market_data_logger.py also has 'strategy_votes.csv' but seemingly simpler structure?
    # Wait, market_data_logger.py has `log_file_votes` = "strategy_votes.csv"
    # AND strategy_ab_tester.py has `votes_csv_path` = "strategy_votes.csv"
    # THEY MIGHT BE CONFLICTING if they write to same file!
    # Checking lines 20 of market_data_logger and 760 of strategy_ab_tester
    # market_data_logger: self.log_file_votes = os.path.join(self.output_dir, "strategy_votes.csv")
    # strategy_ab_tester: self.votes_csv_path = os.path.join(self.output_dir, "strategy_votes.csv")
    
    # Checking content:
    # market_data_logger writes: timestamp, btc_price, signal, mom_up... (fixed list)
    # strategy_ab_tester writes: timestamp, market_slug... (dynamic list)
    
    # MAJOR CONFLICT DETECTED if both run. 
    # Logic suggests MarketDataLogger logic might be legacy/old if AB tester is active.
    # User is running "run_ab_test.bat" which uses "strategy_ab_tester".
    # I should prioritize the strategy_ab_tester structure for 'strategy_votes.csv'.
    
    reset_file("btc_data_1m.csv", cols_1m)
    reset_file("btc_data_1h.csv", cols_1h)
    reset_file("ab_test_near_misses.csv", cols_near_misses)
    
    reset_file("ab_test_trades.csv", cols_ab_trades)
    reset_file("ab_test_summary.csv", cols_ab_summary)
    
    # Use AB Tester version for votes as it is the active one in AB mode
    reset_file("strategy_votes.csv", cols_ab_votes)
    
    print("Done.")
Ö!"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Dfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/reset_logs.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot