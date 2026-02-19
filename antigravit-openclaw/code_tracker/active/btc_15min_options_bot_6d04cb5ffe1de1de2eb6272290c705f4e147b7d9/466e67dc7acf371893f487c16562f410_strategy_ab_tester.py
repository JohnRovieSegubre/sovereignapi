èÊ"""
Strategy A/B Testing Module
Tests 26 different strategy configurations simultaneously in virtual portfolios.

Each configuration tracks its own:
- Virtual balance ($100 starting)
- Open positions
- Trade history
- P&L metrics

Results are logged to JSON/CSV for analysis in NotebookLM or other tools.
"""

import os
import json
import csv
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from config import Config


# ============================================================================
# CONFIGURATION DEFINITIONS (26 total)
# ============================================================================

# Tier 1: Strategy Isolation (8 configs)
STRATEGY_CONFIGS = {
    # Control - no amplification
    "baseline": {
        "description": "No amplification strategies (control)",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    # Individual strategy tests
    "momentum_only": {
        "description": "Only momentum strategy (MACD + Stochastic + ROC)",
        "strategies": {
            "momentum": True,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "velocity_only": {
        "description": "Only price velocity strategy",
        "strategies": {
            "momentum": False,
            "price_velocity": True,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "binance_ofi_only": {
        "description": "Only Binance order flow imbalance",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "polymarket_ofi_only": {
        "description": "Only Polymarket order book OFI (currently disabled in prod)",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": True,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "volume_profile_only": {
        "description": "Only volume profile strategy",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "obv_only": {
        "description": "Only OBV divergence (fakeout detector)",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "all_strategies": {
        "description": "All strategies enabled (current production)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,  # Disabled in prod
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,  # Report only in prod
            "vol_percentile": False,  # Disabled in prod
        },
        "params": {}
    },
    
    # Tier 2: Strategy Combinations (6 configs)
    "momentum_plus_obv": {
        "description": "Momentum + OBV (trend-following combo)",
        "strategies": {
            "momentum": True,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "velocity_plus_binance_ofi": {
        "description": "Velocity + Binance OFI (speed + order flow)",
        "strategies": {
            "momentum": False,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "top_three_likely": {
        "description": "Momentum + Velocity + Binance OFI (likely top performers)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "ofi_plus_obv": {
        "description": "Binance OFI + OBV (order flow + fakeout detection)",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "volume_plus_velocity": {
        "description": "Volume Profile + Velocity (conviction + speed)",
        "strategies": {
            "momentum": False,
            "price_velocity": True,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    "all_except_binance_ofi": {
        "description": "All strategies except Binance OFI",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {}
    },
    
    # Tier 3: Entry Parameter Tuning (5 configs)
    "conservative_entries": {
        "description": "Higher entry thresholds (fewer, higher-quality trades)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.01,
            "ENTRY_AMP_THRESHOLD": 1.08,
            "AMP_FINAL_MULTIPLIER": 0.5,
        }
    },
    
    "aggressive_entries": {
        "description": "Lower entry thresholds (more trades)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.005,
            "ENTRY_AMP_THRESHOLD": 1.03,
            "AMP_FINAL_MULTIPLIER": 1.5,
        }
    },
    
    "tight_max_edge": {
        "description": "Tighter max edge to avoid bad fills",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "MAX_ENTRY_EDGE": 0.012,
            "MAX_ENTRY_EDGE_AMP_CAP": 0.02,
        }
    },
    
    "loose_max_edge": {
        "description": "Looser max edge for more opportunities",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "MAX_ENTRY_EDGE": 0.02,
            "MAX_ENTRY_EDGE_AMP_CAP": 0.035,
        }
    },
    
    "stronger_amp_required": {
        "description": "Require stronger amplification to enter",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "ENTRY_REQUIRE_ACTIVE_AMP": True,
            "ENTRY_AMP_ACTIVE_EPS": 0.03,
        }
    },
    
    # Tier 4: Exit Parameter Tuning (4 configs)
    "quick_profits": {
        "description": "Take profits earlier",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "TAKE_PROFIT_1": 8.0,
            "TAKE_PROFIT_2": 12.0,
            "TAKE_PROFIT_3": 15.0,
        }
    },
    
    "let_winners_run": {
        "description": "Higher profit targets",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "TAKE_PROFIT_1": 15.0,
            "TAKE_PROFIT_2": 20.0,
            "TAKE_PROFIT_3": 30.0,
        }
    },
    
    "tighter_stops": {
        "description": "Cut losses faster",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "STOP_LOSS_PCT": -20.0,
            "TRAILING_STOP_DISTANCE": 3.0,
        }
    },
    
    "wider_stops": {
        "description": "Avoid shakeouts with wider stops",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "STOP_LOSS_PCT": -40.0,
            "TRAILING_STOP_DISTANCE": 8.0,
        }
    },
    
    # Tier 5: Binance OFI Sensitivity (3 configs)
    "binance_ofi_less_sensitive": {
        "description": "Less sensitive OFI (fewer signals)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "BINANCE_OFI_IMBALANCE_THRESHOLD_PCT": 20.0,
            "BINANCE_OFI_BONUS_LOG_K": 0.015,
        }
    },
    
    "binance_ofi_more_sensitive": {
        "description": "More sensitive OFI (more signals)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "BINANCE_OFI_IMBALANCE_THRESHOLD_PCT": 10.0,
            "BINANCE_OFI_BONUS_LOG_K": 0.03,
        }
    },
    
    "binance_ofi_capped": {
        "description": "OFI with hard cap to prevent over-amplification",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "BINANCE_OFI_USE_CAP": True,
            "AMP_CAP_ORDERBOOK": 1.08,
        }
    },
    
    # Tier 6: The Archetypes (New Strategic Combos)
    "whale_watcher": {
        "description": "OFI + Volume Profile (Sniper Mode)",
        "strategies": {
            "momentum": False,
            "price_velocity": False,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "ENTRY_AMP_THRESHOLD": 1.15,
            "MAX_ENTRY_EDGE": 0.02,
            "STOP_LOSS_PCT": -15.0,
        }
    },
    
    "scalper_combo": {
        "description": "Velocity + OFI (Speed Demon)",
        "strategies": {
            "momentum": False,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.008,  # Increased from 0.005 to filter noise
            "MAX_ENTRY_EDGE": 0.035,
            "TAKE_PROFIT_1": 8.0,
        }
    },
    
    "trend_hunter": {
        "description": "Momentum + OBV (Home Run Hitter)",
        "strategies": {
            "momentum": True,
            "price_velocity": False,
            "binance_ofi": False,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "STOP_LOSS_PCT": -60.0,
            "TAKE_PROFIT_1": 40.0,
            "TRAILING_STOP_DISTANCE": 15.0,
        }
    },
    
    # Tier 7: Exit Strategy Tests
    "trailing_stop_tight": {
        "description": "All strategies + Tight Trailing Stop (5% activation, 3% trail)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "TRAILING_STOP_ACTIVATION": 5.0,
            "TRAILING_STOP_DISTANCE": 3.0,
            "TAKE_PROFIT_1": 50.0,  # High TP so trailing does the work
        }
    },
    
    "trailing_stop_loose": {
        "description": "All strategies + Loose Trailing Stop (10% activation, 8% trail)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "TRAILING_STOP_ACTIVATION": 10.0,
            "TRAILING_STOP_DISTANCE": 8.0,
            "TAKE_PROFIT_1": 50.0,
        }
    },
    
    "fv_reversion_exit": {
        "description": "Exit when Fair Value reverses against position",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "FV_REVERSION_EXIT": True,
            "STOP_LOSS_PCT": -40.0,  # Wider stop since FV exit should trigger first
        }
    },
    
    "hybrid_exits": {
        "description": "Trailing Stop + FV Reversion (best of both)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": False,
            "vol_percentile": False,
        },
        "params": {
            "TRAILING_STOP_ACTIVATION": 8.0,
            "TRAILING_STOP_DISTANCE": 5.0,
            "FV_REVERSION_EXIT": False,  # FIXED: Was True, caused 5.7% WR (NotebookLM analysis)
            "TAKE_PROFIT_1": 50.0,
        }
    },
    
    # Tier 8: NotebookLM Optimized Configs (Added 2026-01-30)
    "velocity_trend_rider": {
        "description": "Velocity + OFI + Vol Regime (NotebookLM Optimal)",
        "strategies": {
            "momentum": False,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": True,  # Safety filter for choppy markets
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.008,        # 0.8% edge filters noise
            "ENTRY_AMP_THRESHOLD": 1.04,    # Require ~4% conviction
            "MAX_ENTRY_EDGE": 0.025,        # Pay spread for velocity moves
            "TAKE_PROFIT_1": 15.0,          # Capture fat tail
            "TAKE_PROFIT_2": 25.0,
            "TAKE_PROFIT_3": 35.0,
            "STOP_LOSS_PCT": -25.0,         # Wide stop to avoid noise
            "FV_REVERSION_EXIT": False,     # CRITICAL: Disable panic exits
        }
    },

    # Tier 9: Phase 2 "Chop Survival" Hybrids (Added 2026-02-03)
    "scalp_hybrid": {
        "description": "OFI Scalper + Mean Reversion Targets (Phase 2)",
        "strategies": {
            "momentum": False,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": True,
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.008,
            "TAKE_PROFIT_1": 6.0,      # Bank early for chop
            "TAKE_PROFIT_2": 10.0,
            "FV_REVERSION_EXIT": True, # Re-enable for mean reversion logic
            "STOP_LOSS_PCT": -15.0,    # Tighter stop
        }
    },

    "filtered_trend_rider": {
        "description": "High Barrier Entry + Tight Trail (Phase 2)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": True,
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.012,     # 1.2% Edge (Very High)
            "ENTRY_AMP_THRESHOLD": 1.06, # High Conviction
            "TRAILING_STOP_ACTIVATION": 4.0,
            "TRAILING_STOP_DISTANCE": 3.0,
            "TAKE_PROFIT_1": 20.0,
        }
    },

    # Tier 10: Final "Best of Breed" (Added 2026-02-04)
    "trend_sniper": {
        "description": "Scalper Entry + Trend Exit (Final Hybrid)",
        "strategies": {
            "momentum": False,
            "price_velocity": True,   # Scalper Entry
            "binance_ofi": True,      # Scalper Entry
            "polymarket_ofi": False,
            "volume_profile": False,
            "obv_divergence": False,
            "vol_regime": True,       # Safety
            "vol_percentile": False,
        },
        "params": {
            "BUY_ENTRY_EDGE": 0.008,     # 0.8% High Conviction
            "TAKE_PROFIT_1": 15.0,       # Trend Exit (Capture Fat Tail)
            "TAKE_PROFIT_2": 25.0,
            "STOP_LOSS_PCT": -25.0,      # Wide Stop (No Noise Exit)
            "FV_REVERSION_EXIT": False,  # No Panic Exits
        }
    },

    "pure_trend_v2": {
        "description": "Let Winners Run + Vol Regime (Optimized Trend)",
        "strategies": {
            "momentum": True,
            "price_velocity": True,
            "binance_ofi": True,
            "polymarket_ofi": False,
            "volume_profile": True,
            "obv_divergence": True,
            "vol_regime": True,       # ADDED: Volatility Filter
            "vol_percentile": False,
        },
        "params": {
            "TAKE_PROFIT_1": 15.0,
            "TAKE_PROFIT_2": 20.0,
            "TAKE_PROFIT_3": 30.0,
        }
    },
}


# ============================================================================
# ALERT THRESHOLDS
# ============================================================================

ALERT_THRESHOLDS = {
    "loss_threshold": -10.0,      # Alert if config loses more than $10
    "outperform_threshold": 5.0,  # Alert if config beats baseline by $5
    "win_rate_low": 40.0,         # Alert if win rate drops below 40%
    "win_rate_high": 70.0,        # Alert if win rate exceeds 70%
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class VirtualTrade:
    """Represents a single virtual trade."""
    timestamp: str
    config_name: str
    signal: str  # BUY_UP, BUY_DOWN, HOLD
    side: str    # UP, DOWN, NONE
    entry_price: float
    exit_price: Optional[float] = None
    shares: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    btc_price: float = 0.0
    amp_up: float = 1.0
    amp_down: float = 1.0
    market_slug: str = ""
    status: str = "open"  # open, closed, expired
    exit_reason: str = ""
    exit_timestamp: Optional[str] = None


@dataclass
class VirtualPortfolio:
    """Tracks virtual portfolio for a single configuration."""
    config_name: str
    starting_balance: float = 100.0
    balance: float = 100.0
    positions: Dict[str, Dict] = field(default_factory=dict)  # side -> {shares, entry_price}
    trades: List[VirtualTrade] = field(default_factory=list)
    closed_trades: List[VirtualTrade] = field(default_factory=list)
    total_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def current_equity(self) -> float:
        """Calculate current equity (balance + open position value)."""
        return self.balance + sum(
            pos.get('shares', 0) * pos.get('current_price', pos.get('entry_price', 0))
            for pos in self.positions.values()
        )


# ============================================================================
# A/B TESTER CLASS
# ============================================================================

class StrategyABTester:
    """
    A/B testing framework for comparing strategy configurations.
    
    Tracks 26 virtual portfolios simultaneously, logging all decisions
    and generating comparison reports.
    """
    
    def __init__(
        self,
        output_dir: str = "ab_test_results",
        starting_balance: float = 100.0,
        trade_size: float = 2.0,
        summary_interval_minutes: int = 30,
    ):
        self.output_dir = output_dir
        self.starting_balance = starting_balance
        self.trade_size = trade_size
        self.summary_interval_minutes = summary_interval_minutes
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize portfolios for each config
        self.portfolios: Dict[str, VirtualPortfolio] = {}
        for config_name in STRATEGY_CONFIGS:
            self.portfolios[config_name] = VirtualPortfolio(
                config_name=config_name,
                starting_balance=starting_balance,
                balance=starting_balance,
            )
        
        # Tracking
        self.session_start = datetime.now(timezone.utc)
        self.last_summary_time = self.session_start
        self.evaluation_count = 0
        self.alerts_triggered: List[Dict] = []
        
        # Log file handles
        self._init_log_files()
        
        # Export config definitions
        self._export_config_definitions()
        
        print(f"\n{'='*70}")
        print(f"A/B TESTING FRAMEWORK INITIALIZED")
        print(f"{'='*70}")
        print(f"Configurations: {len(STRATEGY_CONFIGS)}")
        print(f"Starting balance per config: ${starting_balance:.2f}")
        print(f"Virtual trade size: ${trade_size:.2f}")
        print(f"Summary interval: {summary_interval_minutes} minutes")
        print(f"Output directory: {self.output_dir}")
        print(f"{'='*70}\n")
    
    def _init_log_files(self):
        """Initialize log files with headers."""
        # JSON log (will be written incrementally)
        self.json_log_path = os.path.join(self.output_dir, "ab_test_log.json")
        self.json_log = {
            "session_start": self.session_start.isoformat(),
            "configs": list(STRATEGY_CONFIGS.keys()),
            "starting_balance": self.starting_balance,
            "trade_size": self.trade_size,
            "evaluations": [],
        }
        
        # CSV log
        self.csv_log_path = os.path.join(self.output_dir, "ab_test_trades.csv")
        with open(self.csv_log_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "config", "signal", "side", "entry_price", 
                "exit_price", "shares", "pnl", "pnl_pct", "btc_price",
                "amp_up", "amp_down", "market_slug", "status", "exit_reason"
            ])
        
        # Summary CSV
        self.summary_csv_path = os.path.join(self.output_dir, "ab_test_summary.csv")
        with open(self.summary_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "config", "balance", "total_pnl", "total_trades",
                "winning_trades", "losing_trades", "win_rate", "current_equity"
            ])
            
        # Strategy Votes CSV (Granular Multipliers)
        self.votes_csv_path = os.path.join(self.output_dir, "strategy_votes.csv")
        
        # Dynamic Header Generation: Extract all unique keys from a sample config
        # We assume the keys like 'momentum', 'price_velocity' are consistent across configs or at least known
        # Based on amplification_strategies.py, these are the standard keys in strategy_details
        self.vote_keys = sorted([
            "momentum", "price_velocity", "binance_ofi", "polymarket_ofi", 
            "volume_profile", "obv_divergence", "vol_regime", "vol_percentile",
            "orderbook", "adx_filter", "htf_filter", "exhaustion", "cooldown"
        ])
        
        vote_header = ["timestamp", "market_slug", "btc_price", "config", "final_vote", "signal"]
        # Add multiplier columns for each strategy key
        for key in self.vote_keys:
            vote_header.append(f"{key}_amp")
            
        with open(self.votes_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(vote_header)
            
        # Row counts for rotation
        self.row_counts = {
            self.csv_log_path: 0,
            self.summary_csv_path: 0,
            self.votes_csv_path: 0
        }
        
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
                
                # Retrieve header columns (simple heuristic: read first line of current file)
                # Since we just wrote it or it exists, reading it is safe.
                header = []
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        header = next(csv.reader(f))
                
                # Rename current file
                os.rename(file_path, archive_path)
                print(f"    [ROTATE] A/B Log file full ({self.row_counts.get(file_path)} rows). Archived to {os.path.basename(archive_path)}")
                
                # Create new file with header
                with open(file_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    if header:
                        writer.writerow(header)
                    f.flush()
                    os.fsync(f.fileno())
                    
                # Reset counter
                self.row_counts[file_path] = 0
            except Exception as e:
                print(f"    [ERR] Failed to rotate A/B log file {file_path}: {e}")
            
    def _export_config_definitions(self):
        """Export config definitions to CSV for reference."""
        path = os.path.join(self.output_dir, "ab_test_config_definitions.csv")
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["config_name", "description", "enabled_strategies", "param_overrides"])
            
            for name, cfg in STRATEGY_CONFIGS.items():
                strategies = [k for k, v in cfg['strategies'].items() if v]
                params = [f"{k}={v}" for k, v in cfg.get('params', {}).items()]
                
                writer.writerow([
                    name, 
                    cfg['description'], 
                    ", ".join(strategies), 
                    "; ".join(params)
                ])
    
    def evaluate_all_strategies(
        self,
        market_data: Dict,
        base_fair_values: Dict,
        market_prices: Dict,
        combined_amp: Dict,
        df_1m: Any = None,
        atr_metrics: Optional[Dict] = None,
        order_book: Optional[Dict] = None,
    ) -> Dict[str, Dict]:
        """
        Evaluate all strategy configurations for a single market opportunity.
        
        Args:
            market_data: Dict with btc_price, market_slug, minutes_until_end, etc.
            base_fair_values: Dict with fair_value_up, fair_value_down (unamplified)
            market_prices: Dict with best_ask_up, best_ask_down, best_bid_up, best_bid_down
            combined_amp: Full amplification result from calculate_combined_amplification()
            df_1m: 1-minute candle DataFrame (for per-strategy recalculation)
            atr_metrics: ATR metrics dict
            order_book: Order book data
        
        Returns:
            Dict mapping config_name -> evaluation result
        """
        self.evaluation_count += 1
        timestamp = datetime.now(timezone.utc).isoformat()
        
        results = {}
        evaluation_record = {
            "timestamp": timestamp,
            "btc_price": market_data.get("btc_price", 0),
            "market_slug": market_data.get("market_slug", ""),
            "minutes_until_end": market_data.get("minutes_until_end", 0),
            "base_fair_values": base_fair_values,
            "market_prices": market_prices,
            "strategies": {},
        }
        
        for config_name, config in STRATEGY_CONFIGS.items():
            result = self._evaluate_single_config(
                config_name=config_name,
                config=config,
                market_data=market_data,
                base_fair_values=base_fair_values,
                market_prices=market_prices,
                combined_amp=combined_amp,
                df_1m=df_1m,
                atr_metrics=atr_metrics,
                order_book=order_book,
                timestamp=timestamp,
            )
            results[config_name] = result
            evaluation_record["strategies"][config_name] = {
                "signal": result["signal"],
                "amp_up": result["amp_up"],
                "amp_down": result["amp_down"],
                "edge_up": result.get("edge_up", 0),
                "edge_down": result.get("edge_down", 0),
                "would_trade": result["would_trade"],
            }
            
            # --- GRANULAR LOGGING TO STRATEGY_VOTES.CSV ---
            # Log the detailed multipliers for this specific config evaluation
            # Only log if it's a significant vote (e.g. signal != HOLD or purely for frequency sampling)
            # For now, we log every evaluation to give full visibility as requested
            
            row = [
                timestamp,
                market_data.get("market_slug", ""),
                market_data.get("btc_price", 0),
                config_name,
                result.get("amp_up", 1.0) if result.get("signal") == "BUY_UP" else result.get("amp_down", 1.0),
                result.get("signal", "HOLD")
            ]
            
            # Extract multipliers from the combined_amp['strategy_details']
            # Note: Strategy details are global inputs, BUT some configs might disable them.
            # However, the *values* exist in the input 'combined_amp'. 
            # We log the raw signal availability.
            strategy_details = combined_amp.get('strategy_details', {})
            
            for key in self.vote_keys:
                # Default to 1.0 (neutral) if key missing
                val = 1.0
                detail = strategy_details.get(key)
                
                # Determine relevant direction based on the FINAL signal for this config
                # If signal is BUY_UP, we want amp_up. If BUY_DOWN, amp_down.
                # If HOLD, we might default to amp_up or max deviation.
                # Let's align with the final_vote: if final > 1, it's usually UP driven.
                
                target_direction = result.get("signal", "HOLD")
                
                if isinstance(detail, dict):
                    if target_direction == "BUY_UP":
                        val = detail.get("amp_up", 1.0)
                    elif target_direction == "BUY_DOWN":
                        val = detail.get("amp_down", 1.0)
                    else:
                        # For HOLD, log the one with higher deviation from 1.0 for visibility
                        up = detail.get("amp_up", 1.0)
                        down = detail.get("amp_down", 1.0)
                        val = up if abs(up - 1.0) > abs(down - 1.0) else down
                
                row.append(val)
            
            # Append to file immediately (or batch if perf is issue, but file I/O is usually fine here)
            # Rotate if needed
            self._rotate_file_if_needed(self.votes_csv_path)
            
            with open(self.votes_csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
                f.flush()
                os.fsync(f.fileno())
            
            self.row_counts[self.votes_csv_path] = self.row_counts.get(self.votes_csv_path, 0) + 1
        
        # Store evaluation
        self.json_log["evaluations"].append(evaluation_record)
        
        # Check if summary is due
        now = datetime.now(timezone.utc)
        if (now - self.last_summary_time).total_seconds() >= self.summary_interval_minutes * 60:
            self.print_summary()
            self.last_summary_time = now
        
        # Check alerts
        self._check_alerts()
        
        return results
    
    def _evaluate_single_config(
        self,
        config_name: str,
        config: Dict,
        market_data: Dict,
        base_fair_values: Dict,
        market_prices: Dict,
        combined_amp: Dict,
        df_1m: Any,
        atr_metrics: Optional[Dict],
        order_book: Optional[Dict],
        timestamp: str,
    ) -> Dict:
        """Evaluate a single configuration and update its virtual portfolio."""
        
        portfolio = self.portfolios[config_name]
        strategies = config["strategies"]
        params = config.get("params", {})
        
        # Calculate amplification for this config
        amp_up, amp_down = self._calculate_config_amplification(
            strategies=strategies,
            combined_amp=combined_amp,
        )
        
        # Apply config-specific parameter overrides
        buy_entry_edge = params.get("BUY_ENTRY_EDGE", Config.BUY_ENTRY_EDGE)
        max_entry_edge = params.get("MAX_ENTRY_EDGE", Config.MAX_ENTRY_EDGE)
        amp_threshold = params.get("ENTRY_AMP_THRESHOLD", Config.ENTRY_AMP_THRESHOLD)
        amp_multiplier = params.get("AMP_FINAL_MULTIPLIER", Config.AMP_FINAL_MULTIPLIER)
        
        # Apply final multiplier
        final_amp_up = 1.0 + amp_multiplier * (amp_up - 1.0)
        final_amp_down = 1.0 + amp_multiplier * (amp_down - 1.0)
        
        # Calculate amplified fair values
        fv_up = base_fair_values.get("fair_value_up", 0.5) * final_amp_up
        fv_down = base_fair_values.get("fair_value_down", 0.5) * final_amp_down
        
        # Normalize to sum to 1
        fv_sum = fv_up + fv_down
        if fv_sum > 0:
            fv_up /= fv_sum
            fv_down /= fv_sum
        
        # Get market prices
        ask_up = market_prices.get("best_ask_up", 0.5)
        ask_down = market_prices.get("best_ask_down", 0.5)
        
        # Calculate edges
        edge_up = fv_up - ask_up
        edge_down = fv_down - ask_down
        
        # Determine signal
        signal = "HOLD"
        would_trade = False
        trade_side = "NONE"
        near_miss = None
        
        # Check UP signal
        if (edge_up >= buy_entry_edge and 
            edge_up < max_entry_edge and 
            final_amp_up >= amp_threshold):
            signal = "BUY_UP"
            would_trade = True
            trade_side = "UP"
        elif edge_up > 0 and edge_up >= buy_entry_edge * 0.9 and final_amp_up >= amp_threshold * 0.9:
            near_miss = {"side": "UP", "edge": edge_up, "threshold": buy_entry_edge}
        
        # Check DOWN signal
        if not would_trade:
            if (edge_down >= buy_entry_edge and 
                  edge_down < max_entry_edge and 
                  final_amp_down >= amp_threshold):
                signal = "BUY_DOWN"
                would_trade = True
                trade_side = "DOWN"
            elif edge_down > 0 and edge_down >= buy_entry_edge * 0.9 and final_amp_down >= amp_threshold * 0.9:
                near_miss = {"side": "DOWN", "edge": edge_down, "threshold": buy_entry_edge}
        
        # Execute virtual trade if signaled and no existing position
        if would_trade and trade_side not in portfolio.positions:
            self._execute_virtual_trade(
                portfolio=portfolio,
                side=trade_side,

                entry_price=(ask_up * 1.0005) if trade_side == "UP" else (ask_down * 0.9995), # Simulated 0.05% Slippage Penalty (Worsened Entry)
                btc_price=market_data.get("btc_price", 0),
                amp_up=final_amp_up,
                amp_down=final_amp_down,
                entry_threshold=amp_threshold,
                market_slug=market_data.get("market_slug", ""),
                timestamp=timestamp,
            )
        
        # Check exits for open positions
        self._check_virtual_exits(
            portfolio=portfolio,
            market_data=market_data,
            market_prices=market_prices,
            fv_up=fv_up,
            fv_down=fv_down,
            params=params,
            timestamp=timestamp,
        )
        
        return {
            "signal": signal,
            "would_trade": would_trade,
            "amp_up": final_amp_up,
            "amp_down": final_amp_down,
            "edge_up": edge_up,
            "edge_down": edge_down,
            "fv_up": fv_up,
            "fv_down": fv_down,
            "near_miss": near_miss
        }
    
    def _calculate_config_amplification(
        self,
        strategies: Dict[str, bool],
        combined_amp: Dict,
    ) -> tuple:
        """Calculate amplification using only enabled strategies for this config."""
        
        amp_up = 1.0
        amp_down = 1.0
        
        strategy_details = combined_amp.get("strategy_details", {})
        
        # Map config strategy names to combined_amp keys
        strategy_mapping = {
            "momentum": "momentum",
            "price_velocity": "price_velocity",
            "binance_ofi": "binance_ofi",
            "polymarket_ofi": "orderbook",
            "volume_profile": "volume_profile",
            "obv_divergence": "obv_divergence",
            "vol_regime": "vol_regime",
            "vol_percentile": "vol_percentile",
        }
        
        for strategy_name, enabled in strategies.items():
            if not enabled:
                continue
            
            amp_key = strategy_mapping.get(strategy_name)
            if not amp_key or amp_key not in strategy_details:
                continue
            
            strategy_data = strategy_details[amp_key]
            if not strategy_data.get("active", False):
                continue
            
            # Get the strategy's amplification
            strat_amp_up = strategy_data.get("amp_up", 1.0)
            strat_amp_down = strategy_data.get("amp_down", 1.0)
            
            # Multiply into cumulative amp
            amp_up *= strat_amp_up
            amp_down *= strat_amp_down
        
        return amp_up, amp_down
    
    def _execute_virtual_trade(
        self,
        portfolio: VirtualPortfolio,
        side: str,
        entry_price: float,
        btc_price: float,
        amp_up: float,
        amp_down: float,
        entry_threshold: float,
        market_slug: str,
        timestamp: str,
    ):
        """Execute a virtual trade for a portfolio."""
        if entry_price <= 0:
            return
        
        # Confidence-based position sizing (Relative)
        # Use $6 for confident signals (amp >= entry + 0.03), $2 for neutral
        relevant_amp = amp_up if side == "UP" else amp_down
        
        if relevant_amp >= (entry_threshold + 0.03):
            trade_size = 6.0  # Confident bet
        else:
            trade_size = 2.0  # Neutral bet
        
        shares = trade_size / entry_price
        
        # Create trade record
        trade = VirtualTrade(
            timestamp=timestamp,
            config_name=portfolio.config_name,
            signal=f"BUY_{side}",
            side=side,
            entry_price=entry_price,
            shares=shares,
            btc_price=btc_price,
            amp_up=amp_up,
            amp_down=amp_down,
            market_slug=market_slug,
            status="open",
        )
        
        # Update portfolio
        portfolio.positions[side] = {
            "shares": shares,
            "entry_price": entry_price,
            "current_price": entry_price,
            "trade": trade,
        }
        portfolio.trades.append(trade)
        portfolio.balance -= trade_size
        
        # Log to CSV
        self._log_trade_csv(trade)
    
    def _check_virtual_exits(
        self,
        portfolio: VirtualPortfolio,
        market_data: Dict,
        market_prices: Dict,
        fv_up: float,
        fv_down: float,
        params: Dict,
        timestamp: str,
    ):
        """Check and execute exits for open positions."""
        
        # Get exit params
        stop_loss_pct = params.get("STOP_LOSS_PCT", Config.STOP_LOSS_PCT)
        take_profit_1 = params.get("TAKE_PROFIT_1", Config.TAKE_PROFIT_1)
        trailing_activation = params.get("TRAILING_STOP_ACTIVATION", Config.TRAILING_STOP_ACTIVATION)
        trailing_distance = params.get("TRAILING_STOP_DISTANCE", Config.TRAILING_STOP_DISTANCE)
        fv_reversion_enabled = params.get("FV_REVERSION_EXIT", False)
        
        positions_to_close = []
        
        for side, pos in portfolio.positions.items():
            entry_price = pos["entry_price"]
            shares = pos["shares"]
            trade = pos["trade"]
            
            # Get current price with 0.05% SLIPPAGE PENALTY (Exit)
            if side == "UP":
                raw_bid = market_prices.get("best_bid_up", entry_price)
                current_price = raw_bid * 0.9995  # Sell into bid - 0.05% slippage
                current_fv = fv_up
            else:
                raw_bid = market_prices.get("best_bid_down", entry_price)
                current_price = raw_bid * 0.9995  # Sell into bid - 0.05% slippage
                current_fv = fv_down
            
            pos["current_price"] = current_price
            
            # Calculate P&L %
            pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            # Track peak P&L for trailing stop
            peak_pnl = pos.get("peak_pnl", pnl_pct)
            if pnl_pct > peak_pnl:
                pos["peak_pnl"] = pnl_pct
                peak_pnl = pnl_pct
            
            exit_reason = None
            
            # Check stop loss
            if pnl_pct <= stop_loss_pct:
                exit_reason = "stop_loss"
            
            # Check take profit
            elif pnl_pct >= take_profit_1:
                exit_reason = "take_profit"
            
            # Check trailing stop (activates after +X%, triggers when drops Y% from peak)
            elif peak_pnl >= trailing_activation and pnl_pct <= (peak_pnl - trailing_distance):
                exit_reason = "trailing_stop"
            
            # Check FV reversion (exit when fair value flips against position)
            elif fv_reversion_enabled:
                if side == "UP" and current_fv < 0.48:  # FV reverted to favor DOWN
                    exit_reason = "fv_reversion"
                elif side == "DOWN" and current_fv < 0.48:  # FV reverted to favor UP
                    exit_reason = "fv_reversion"
            
            # Check market expiry (force exit at t-5 min)
            minutes_left = market_data.get("minutes_until_end", 60)
            if minutes_left <= 5:
                exit_reason = "near_expiry"
            
            if exit_reason:
                positions_to_close.append((side, current_price, pnl_pct, exit_reason))
        
        # Close positions
        for side, exit_price, pnl_pct, exit_reason in positions_to_close:
            self._close_virtual_position(
                portfolio=portfolio,
                side=side,
                exit_price=exit_price,
                pnl_pct=pnl_pct,
                exit_reason=exit_reason,
                timestamp=timestamp,
            )
    
    def _close_virtual_position(
        self,
        portfolio: VirtualPortfolio,
        side: str,
        exit_price: float,
        pnl_pct: float,
        exit_reason: str,
        timestamp: str,
    ):
        """Close a virtual position."""
        if side not in portfolio.positions:
            return
        
        pos = portfolio.positions[side]
        trade = pos["trade"]
        shares = pos["shares"]
        entry_price = pos["entry_price"]
        
        # Calculate P&L
        pnl = (exit_price - entry_price) * shares
        
        # Update trade record
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.pnl_pct = pnl_pct
        trade.status = "closed"
        trade.exit_reason = exit_reason
        trade.exit_timestamp = timestamp
        
        # Update portfolio
        portfolio.balance += (exit_price * shares)
        portfolio.total_pnl += pnl
        portfolio.total_trades += 1
        if pnl > 0:
            portfolio.winning_trades += 1
        else:
            portfolio.losing_trades += 1
        
        portfolio.closed_trades.append(trade)
        del portfolio.positions[side]
        
        # Log to CSV
        self._log_trade_csv(trade)
    
    def _log_trade_csv(self, trade: VirtualTrade):
        """Append trade to CSV log."""
        # Rotate if needed
        self._rotate_file_if_needed(self.csv_log_path)
        
        with open(self.csv_log_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                trade.timestamp,
                trade.config_name,
                trade.signal,
                trade.side,
                trade.entry_price,
                trade.exit_price or "",
                trade.shares,
                trade.pnl,
                trade.pnl_pct,
                trade.btc_price,
                trade.amp_up,
                trade.amp_down,
                trade.market_slug,
                trade.status,
                trade.exit_reason,
            ])
            self.row_counts[self.csv_log_path] = self.row_counts.get(self.csv_log_path, 0) + 1
    
    def _check_alerts(self):
        """Check for alert conditions."""
        baseline_pnl = self.portfolios["baseline"].total_pnl
        
        for config_name, portfolio in self.portfolios.items():
            # Loss alert
            if portfolio.total_pnl <= ALERT_THRESHOLDS["loss_threshold"]:
                self._trigger_alert(
                    config_name=config_name,
                    alert_type="LOSS",
                    message=f"Lost ${abs(portfolio.total_pnl):.2f} (threshold: ${abs(ALERT_THRESHOLDS['loss_threshold']):.2f})",
                )
            
            # Outperformance alert
            if config_name != "baseline":
                outperformance = portfolio.total_pnl - baseline_pnl
                if outperformance >= ALERT_THRESHOLDS["outperform_threshold"]:
                    self._trigger_alert(
                        config_name=config_name,
                        alert_type="OUTPERFORM",
                        message=f"Beating baseline by ${outperformance:.2f}",
                    )
            
            # Win rate alerts
            if portfolio.total_trades >= 5:  # Need minimum trades
                if portfolio.win_rate <= ALERT_THRESHOLDS["win_rate_low"]:
                    self._trigger_alert(
                        config_name=config_name,
                        alert_type="LOW_WIN_RATE",
                        message=f"Win rate {portfolio.win_rate:.1f}% (threshold: {ALERT_THRESHOLDS['win_rate_low']}%)",
                    )
                elif portfolio.win_rate >= ALERT_THRESHOLDS["win_rate_high"]:
                    self._trigger_alert(
                        config_name=config_name,
                        alert_type="HIGH_WIN_RATE",
                        message=f"Win rate {portfolio.win_rate:.1f}% (threshold: {ALERT_THRESHOLDS['win_rate_high']}%)",
                    )
    
    def _trigger_alert(self, config_name: str, alert_type: str, message: str):
        """Trigger and log an alert."""
        alert = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": config_name,
            "type": alert_type,
            "message": message,
        }
        
        # Avoid duplicate alerts within 30 min
        for existing in self.alerts_triggered[-20:]:  # Check last 20
            if (existing["config"] == config_name and 
                existing["type"] == alert_type):
                return
        
        self.alerts_triggered.append(alert)
        
        # Print alert
        icon = {"LOSS": "üî¥", "OUTPERFORM": "üü¢", "LOW_WIN_RATE": "üü°", "HIGH_WIN_RATE": "üü¢"}.get(alert_type, "‚ö†Ô∏è")
        print(f"\n{icon} ALERT [{alert_type}] {config_name}: {message}")
    
    def print_summary(self):
        """Print summary of all configurations."""
        now = datetime.now(timezone.utc)
        elapsed = now - self.session_start
        elapsed_hours = elapsed.total_seconds() / 3600
        
        print(f"\n{'='*80}")
        print(f"A/B TEST SUMMARY | Elapsed: {elapsed_hours:.1f}h | Evaluations: {self.evaluation_count}")
        print(f"{'='*80}")
        
        # Sort by total P&L
        sorted_portfolios = sorted(
            self.portfolios.items(),
            key=lambda x: x[1].total_pnl,
            reverse=True
        )
        
        print(f"{'Config':<30} | {'Trades':>6} | {'Win%':>6} | {'P&L':>10} | {'Balance':>10}")
        print(f"{'-'*30}-+-{'-'*6}-+-{'-'*6}-+-{'-'*10}-+-{'-'*10}")
        
        for config_name, portfolio in sorted_portfolios:
            pnl_str = f"${portfolio.total_pnl:+.2f}"
            bal_str = f"${portfolio.balance:.2f}"
            win_str = f"{portfolio.win_rate:.1f}%" if portfolio.total_trades > 0 else "N/A"
            
            # Highlight top 3 and bottom 3
            if sorted_portfolios.index((config_name, portfolio)) < 3:
                marker = " ‚òÖ"
            elif sorted_portfolios.index((config_name, portfolio)) >= len(sorted_portfolios) - 3:
                marker = " ‚úó"
            else:
                marker = ""
            
            print(f"{config_name:<30} | {portfolio.total_trades:>6} | {win_str:>6} | {pnl_str:>10} | {bal_str:>10}{marker}")
        
        print(f"{'='*80}")
        
        # Log to summary CSV
        # Rotate if needed
        self._rotate_file_if_needed(self.summary_csv_path)
        
        with open(self.summary_csv_path, 'a', newline='') as f:
            writer = csv.writer(f)
            for config_name, portfolio in self.portfolios.items():
                writer.writerow([
                    now.isoformat(),
                    config_name,
                    portfolio.balance,
                    portfolio.total_pnl,
                    portfolio.total_trades,
                    portfolio.winning_trades,
                    portfolio.losing_trades,
                    portfolio.win_rate,
                    portfolio.current_equity,
                ])
                self.row_counts[self.summary_csv_path] = self.row_counts.get(self.summary_csv_path, 0) + 1
    
    def save_logs(self):
        """Save all logs to disk."""
        # Save JSON log
        with open(self.json_log_path, 'w') as f:
            json.dump(self.json_log, f, indent=2, default=str)
        
        print(f"\n[LOG] Saved logs to {self.output_dir}/")
    
    def generate_final_report(self) -> str:
        """Generate final markdown report with rankings and recommendations."""
        now = datetime.now(timezone.utc)
        elapsed = now - self.session_start
        elapsed_hours = elapsed.total_seconds() / 3600
        
        # Sort by P&L
        sorted_portfolios = sorted(
            self.portfolios.items(),
            key=lambda x: x[1].total_pnl,
            reverse=True
        )
        
        report = f"""# A/B Test Final Report

**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Test Duration:** {elapsed_hours:.1f} hours  
**Total Evaluations:** {self.evaluation_count}  
**Configurations Tested:** {len(STRATEGY_CONFIGS)}

---

## Rankings by P&L

| Rank | Configuration | Trades | Win % | P&L | Balance |
|------|--------------|--------|-------|-----|---------|
"""
        for i, (config_name, portfolio) in enumerate(sorted_portfolios, 1):
            win_str = f"{portfolio.win_rate:.1f}%" if portfolio.total_trades > 0 else "N/A"
            report += f"| {i} | {config_name} | {portfolio.total_trades} | {win_str} | ${portfolio.total_pnl:+.2f} | ${portfolio.balance:.2f} |\n"
        
        report += f"""
---

## Top 3 Performers

"""
        for i, (config_name, portfolio) in enumerate(sorted_portfolios[:3], 1):
            config = STRATEGY_CONFIGS[config_name]
            report += f"""### {i}. {config_name}
- **Description:** {config['description']}
- **P&L:** ${portfolio.total_pnl:+.2f}
- **Trades:** {portfolio.total_trades} ({portfolio.winning_trades}W / {portfolio.losing_trades}L)
- **Win Rate:** {portfolio.win_rate:.1f}%

"""
        
        report += f"""
---

## Bottom 3 Performers

"""
        for i, (config_name, portfolio) in enumerate(sorted_portfolios[-3:], 1):
            config = STRATEGY_CONFIGS[config_name]
            report += f"""### {i}. {config_name}
- **Description:** {config['description']}
- **P&L:** ${portfolio.total_pnl:+.2f}
- **Trades:** {portfolio.total_trades}
- **Win Rate:** {portfolio.win_rate:.1f}%

"""
        
        report += f"""
---

## Recommendations

Based on the test results:

1. **Best Strategy Configuration:** `{sorted_portfolios[0][0]}`
2. **Avoid:** `{sorted_portfolios[-1][0]}`

### Suggested Next Steps

1. Run the top performer in live test mode for 24-48 hours
2. Compare to current production config (`all_strategies`)
3. Consider combining elements from top 3 performers

---

## Alerts Triggered

| Time | Config | Type | Message |
|------|--------|------|---------|
"""
        for alert in self.alerts_triggered[-20:]:
            report += f"| {alert['timestamp'][:19]} | {alert['config']} | {alert['type']} | {alert['message']} |\n"
        
        report += f"""
---

*Report generated by Strategy A/B Tester v1.0*
"""
        
        # Save report
        report_path = os.path.join(self.output_dir, "final_report.md")
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"\n[REPORT] Final report saved to {report_path}")
        
        return report


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ab_tester(
    output_dir: str = None,
    starting_balance: float = 100.0,
    trade_size: float = None,
) -> StrategyABTester:
    """Get or create the A/B tester instance."""
    global _ab_tester_instance
    
    if output_dir is None:
        # Get project directory
        import os
        project_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(project_dir, "ab_test_results")
    
    if trade_size is None:
        trade_size = Config.TRADE_SIZE
    
    if '_ab_tester_instance' not in globals() or _ab_tester_instance is None:
        _ab_tester_instance = StrategyABTester(
            output_dir=output_dir,
            starting_balance=starting_balance,
            trade_size=trade_size,
        )
    
    return _ab_tester_instance

_ab_tester_instance = None


if __name__ == "__main__":
    # Test initialization
    tester = get_ab_tester()
    print(f"\nConfigurations loaded: {len(STRATEGY_CONFIGS)}")
    for name, config in STRATEGY_CONFIGS.items():
        print(f"  - {name}: {config['description']}")
„w „w‰w*cascade08
‰wÂw Âwçx*cascade08çxÃê Ãê·ê*cascade08·êÊê Êêãë*cascade08ãëØë ØëÁô*cascade08Áô¸ô ¸ôÁ•*cascade08Á•¨±*cascade08¨±Œ« Œ«‡« *cascade08‡«Ï« Ï«Ì«*cascade08Ì«Ù« Ù«˛«*cascade08˛«ô» ô»ö»*cascade08ö»¢» ¢»¨»*cascade08¨»≠» ≠»·»*cascade08·»»Ú »ÚÎÚ*cascade08ÎÚúÛ úÛûÛ*cascade08ûÛüÛ üÛ†Û*cascade08†Û°Û °Û¢Û*cascade08¢ÛÏÛ ÏÛ¿Ù*cascade08¿ÙÙ ÙÚÙ*cascade08ÚÙÛÙ ÛÙÙÙ*cascade08ÙÙıÙ ıÙˆÙ*cascade08ˆÙ®ı ®ı¸ı*cascade08¸ıèÊ "(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Lfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/strategy_ab_tester.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot