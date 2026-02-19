ÌY"""
Market Data Logger Module
Logs refined OHLCV data and technical indicators to CSV for analysis.
"""

import os
import csv
import pandas as pd
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Any

class MarketDataLogger:
    def __init__(self, output_dir: str = "ab_test_results"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.log_file_1m = os.path.join(self.output_dir, "btc_data_1m.csv")
        self.log_file_1h = os.path.join(self.output_dir, "btc_data_1h.csv")
        self.log_file_votes = os.path.join(self.output_dir, "strategy_votes.csv")
        self.log_file_near_misses = os.path.join(self.output_dir, "ab_test_near_misses.csv")
        
        # Thread lock for safe CSV writing
        self.lock = threading.Lock()
        
        self._init_files()
        
    def _init_files(self):
        """Initialize CSV files with headers if they don't exist."""
        # 1-Minute Data Columns
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
        
        # 1-Hour Data Columns
        cols_1h = [
            "timestamp", "open", "high", "low", "close", "volume",
            "rsi", "macd", "macd_signal", "macd_hist",
            "atr", "adx",
            "trend_regime", "volatility_regime",
            "sigma_realized", "sigma_implied"
        ]

        # Strategy Voting Columns (Every cycle)
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

        # Near-Miss Columns
        cols_near_misses = [
            "timestamp", "config", "side", "edge", "threshold", "btc_price", "market_slug"
        ]
        
        self.file_columns = {
            self.log_file_1m: cols_1m,
            self.log_file_1h: cols_1h,
            self.log_file_votes: cols_votes,
            self.log_file_near_misses: cols_near_misses
        }
        
        self.row_counts = {}

        # Create files if not exists
        for file_path, cols in self.file_columns.items():
            if not os.path.exists(file_path):
                with self.lock:
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(cols)
                self.row_counts[file_path] = 0
            else:
                # Count existing rows
                try:
                    with open(file_path, 'r') as f:
                        self.row_counts[file_path] = sum(1 for _ in f) - 1 # exclude header
                except Exception:
                    self.row_counts[file_path] = 0

    def _rotate_file_if_needed(self, file_path):
        """Rotate file if row limit reached."""
        from config import Config
        limit = getattr(Config, 'CSV_ROTATION_ROW_LIMIT', 50000)
        
        if self.row_counts.get(file_path, 0) >= limit:
            try:
                # Archive name
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dir_name = os.path.dirname(file_path)
                file_name = os.path.basename(file_path)
                base, ext = os.path.splitext(file_name)
                archive_path = os.path.join(dir_name, f"{base}_{timestamp}{ext}")
                
                with self.lock:
                    # Rename current file
                    os.rename(file_path, archive_path)
                    print(f"    [ROTATE] Log file full ({self.row_counts.get(file_path)} rows). Archived to {os.path.basename(archive_path)}")
                    
                    # Create new file with header
                    cols = self.file_columns.get(file_path, [])
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(cols)
                        f.flush()
                        os.fsync(f.fileno())
                        
                    # Reset counter
                    self.row_counts[file_path] = 0
            except Exception as e:
                print(f"    [ERR] Failed to rotate log file {file_path}: {e}")

    def log_1m_candle(self, 
                      candle: pd.Series, 
                      indicators: Dict[str, Any],
                      extra_metrics: Dict[str, Any]):
        """
        Log a finalized 1-minute candle with indicators.
        """
        try:
            row = [
                candle.get('timestamp', datetime.now(timezone.utc).isoformat()),
                candle.get('open'),
                candle.get('high'),
                candle.get('low'),
                candle.get('close'),
                candle.get('volume'),
                
                # Tech Indicators
                indicators.get('rsi'),
                indicators.get('macd'),
                indicators.get('macd_signal'),
                indicators.get('macd_hist'),
                indicators.get('stoch_k'),
                indicators.get('stoch_d'),
                indicators.get('roc'),
                indicators.get('atr'),
                indicators.get('adx'),
                indicators.get('plus_di'),
                indicators.get('minus_di'),
                indicators.get('obv'),
                indicators.get('vwap'),
                indicators.get('bb_upper'),
                indicators.get('bb_middle'),
                indicators.get('bb_lower'),
                
                # Advanced
                extra_metrics.get('velocity'),
                extra_metrics.get('acceleration'),
                extra_metrics.get('binance_ofi'),
                extra_metrics.get('sigma_realized'),
                
                # Context (NEW)
                extra_metrics.get('bid_ask_spread'),
                extra_metrics.get('hour_utc'),
                extra_metrics.get('day_of_week'),
                extra_metrics.get('market_session'),
                
                extra_metrics.get('trade_active', False)
            ]
            
            with self.lock:
                # Rotate if needed
                self._rotate_file_if_needed(self.log_file_1m)
                
                with open(self.log_file_1m, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                    f.flush()
                    os.fsync(f.fileno())
                
                self.row_counts[self.log_file_1m] = self.row_counts.get(self.log_file_1m, 0) + 1
                
        except Exception as e:
            print(f"[WARN] Failed to log 1m candle: {e}")

    def log_1h_candle(self, 
                      candle: pd.Series, 
                      indicators: Dict[str, Any],
                      regimes: Dict[str, Any]):
        """Log a finalized 1-hour candle."""
        try:
            row = [
                candle.get('timestamp', datetime.now(timezone.utc).isoformat()),
                candle.get('open'),
                candle.get('high'),
                candle.get('low'),
                candle.get('close'),
                candle.get('volume'),
                
                indicators.get('rsi'),
                indicators.get('macd'),
                indicators.get('macd_signal'),
                indicators.get('macd_hist'),
                indicators.get('atr'),
                indicators.get('adx'),
                
                regimes.get('trend_regime'),
                regimes.get('volatility_regime'),
                regimes.get('sigma_realized'),
                regimes.get('sigma_implied')
            ]
            
            with self.lock:
                with open(self.log_file_1h, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
                
        except Exception as e:
            print(f"[WARN] Failed to log 1h candle: {e}")

    def log_strategy_votes(self, data: Dict[str, Any]):
        """Log strategy voting/amplification data for every cycle."""
        try:
            with self.lock:
                # Rotate if needed
                self._rotate_file_if_needed(self.log_file_votes)
                
                with open(self.log_file_votes, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                        data.get('btc_price'),
                        data.get('signal'),
                        data.get('mom_up'), data.get('mom_down'),
                        data.get('vel_up'), data.get('vel_down'),
                        data.get('bin_ofi_up'), data.get('bin_ofi_down'),
                        data.get('poly_ofi_up'), data.get('poly_ofi_down'),
                        data.get('vol_prof_up'), data.get('vol_prof_down'),
                        data.get('obv_up'), data.get('obv_down'),
                        data.get('total_up'), data.get('total_down')
                    ])
                    f.flush()
                    os.fsync(f.fileno())
                
                self.row_counts[self.log_file_votes] = self.row_counts.get(self.log_file_votes, 0) + 1
        except Exception as e:
            print(f"[WARN] Failed to log strategy votes: {e}")

    def log_near_miss(self, data: Dict[str, Any]):
        """Log a near-miss entry event."""
        try:
            with self.lock:
                # Rotate if needed
                self._rotate_file_if_needed(self.log_file_near_misses)

                with open(self.log_file_near_misses, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        data.get('timestamp', datetime.now(timezone.utc).isoformat()),
                        data.get('config'),
                        data.get('side'),
                        data.get('edge'),
                        data.get('threshold'),
                        data.get('btc_price'),
                        data.get('market_slug')
                    ])
                    f.flush()
                    os.fsync(f.fileno())
                
                self.row_counts[self.log_file_near_misses] = self.row_counts.get(self.log_file_near_misses, 0) + 1
        except Exception as e:
            print(f"[WARN] Failed to log near miss: {e}")
ÌY"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Lfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/market_data_logger.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot