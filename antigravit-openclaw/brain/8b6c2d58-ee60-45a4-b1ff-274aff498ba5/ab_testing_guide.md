# A/B Testing Guide: 29 Strategy Comparison 🧪

This guide explains how to run the **29-configuration A/B test**, interpret the results, and use **Google NotebookLM** for deep analysis.

---

## 🚀 How to Run the Test

1.  **Start the Test:**
    Double-click `run_ab_test.bat` in your bot folder.

2.  **Monitor Progress:**
    -   The bot runs in **Test Mode** (no real money).
    -   It manages **29 Virtual Portfolios** simultaneously.
    -   Every **30 minutes**, a summary performance table appears in the console.

3.  **Stop & Report:**
    -   Let it run for **24 hours** for statistically significant data.
    -   Press **Ctrl+C** to stop.
    -   The bot generates a final report automatically.

---

## 📂 Output Files (Your Data Goldmine)

All results are saved in `ab_test_results/`. You will use these for analysis.

| File | Description | Critical For |
|------|-------------|--------------|
| `ab_test_trades.csv` | **Every single virtual trade** taken by all 29 bots. | **Performance Analysis** |
| `btc_data_1m.csv` | **1-Minute Market Data** (Price, RSI, MACD, OFI, etc.) + **Market Session/Spread**. | **Market Context** |
| `strategy_votes.csv` | **5-Second Snapshot** of every strategy's amplification vote. | **Signal Cross-Analysis** |
| `ab_test_near_misses.csv` | Log of trades that *almost* triggered (0.74% edge with 0.75% threshold). | **Threshold Tuning** |
| `ab_test_config_definitions.csv` | **The "Legend".** Explains exactly what "Scalper" or "Whale" means. | **Context** |
| `ab_test_summary.csv` | Snapshot of P&L and Win Rates. | **Quick Charts** |
| `final_report.md` | Auto-generated ranking of winners/losers. | **Executive Summary** |


## 📚 Data Dictionary: What does it all mean?

Upload this section to NotebookLM so it understands your data structure.

### 1. `ab_test_near_misses.csv` (The "Almost" Log)
*   **Purpose:** Logs events where the bot *wanted* to trade but the edge wasn't *quite* high enough.
*   **Key Columns:**
    *   `edge`: The calculated advantage (fair value - market price).
    *   `threshold`: The required advantage to enter (from config).
    *   `side`: UP or DOWN.
*   **Analysis Question:** "Are we missing good trades by being too greedy? If `edge` is consistently 0.005 less than `threshold` before a big price move, we should lower the threshold."

### 2. `strategy_votes.csv` (The Brain Scan)
*   **Purpose:** A detailed log of *every* strategy's opinion, every 5 seconds.
*   **Key Columns:**
    *   `momentum_amp_up/down`: Did the Momentum strategy want to buy? (>1.0 = Yes)
    *   `velocity_amp_up/down`: Did Price Velocity see a move?
    *   `binance_ofi_...`: Did Binance Order Flow confirm?
    *   `total_amp_...`: The final combined signal.
*   **Analysis Question:** "Why did we buy? Was it Momentum or OFI driving the signal? Which strategy is the 'Leader'?"

### 3. `btc_data_1m.csv` (The Context)
*   **Purpose:** High-resolution market history.
*   **Key Columns:**
    *   `rsi`, `macd`, `stoch`: Technical indicators.
    *   `binance_ofi`: Order flow imbalance.
    *   `bid_ask_spread`: Market liquidity.
*   **Analysis Question:** "Do our strategies fail when `bid_ask_spread` is high (illiquid market)? Do we lose money when `rsi` is overbought?"


## 🤖 Analyzing with NotebookLM

This is where the magic happens. We will use AI to correlate **What Happened** (Trades) with **Why It Happened** (Market Data/Votes).

### Step 1: Upload Data
1.  Go to [notebooklm.google.com](https://notebooklm.google.com).
2.  Create a new notebook titled **"BTC Options Analysis"**.
3.  **Upload the BIG 5:**
    *   `ab_test_trades.csv`
    *   `btc_data_1m.csv`
    *   `strategy_votes.csv` (NEW)
    *   `ab_test_near_misses.csv` (NEW)
    *   `ab_test_config_definitions.csv`

### Step 2: Ask "God Mode" Questions ⚡

#### 🔍 Deep Dives
> "During the **US Session** in `btc_data_1m.csv`, which configurations in `ab_test_trades.csv` had the highest win rate? Did a wider **Spread** hurt their performance?"

#### ⚔️ Strategy Voting Conflict
> "Use `strategy_votes.csv`. Find times when **Momentum** and **OFI** were in conflict (one amplification > 1.0, the other < 1.0). In those cases, which one was more predictive of the trade outcome in `ab_test_trades.csv`?"

#### 📐 Threshold Optimization
> "Analyze `ab_test_near_misses.csv`. If we lowered the `BUY_ENTRY_EDGE` threshold by 0.001 (0.1%), how many more trades would have been taken? Based on the market trend at those times in `btc_data_1m.csv`, would those trades have been winners?"

#### ⚔️ Strategy Wars
> "Compare `scalper_combo` vs `trend_hunter`. Did the Scalper actually exit earlier? Did the Trend Hunter survive dips that stopped out the Scalper?"

#### 📉 Failed Trades
> "Analyze the losing trades for `whale_watcher`. Look at the corresponding time in `btc_data_1m.csv`. Was there a false signal in OFI or Volume that caused this?"

#### 🏆 The Optimization Query
> "Based on all trade data, if we could only run ONE configuration for the next 24 hours, which one has the highest risk-adjusted return (Sharpe Ratio), and why?"

---

## 🧪 The Configurations (The Roster)

### Tier 1-5: The Basics
*   **Isolations:** Testing Momentum, Velocity, and OFI alone.
*   **Combinations:** Testing logical pairs (e.g., Velocity + OFI).
*   **Tuning:** Testing Conservative vs Aggressive parameters.

### Tier 6: The Archetypes (New!) ⭐
These are the "Special Forces" bots we just added:

1.  **🐋 Whale Watcher (The Sniper)**
    *   *Strategy:* OFI + Volume Profile
    *   *Style:* Waits for massive order book walls. Tight stops.
    *   *Goal:* High win rate, low frequency.

2.  **⚡ Scalper Combo (The Speed Demon)**
    *   *Strategy:* Velocity + OFI
    *   *Style:* Enters fast on aggressive signals. Takes profits quickly (8%).
    *   *Goal:* Catching explosive 5-minute moves.

3.  **🏹 Trend Hunter (The Home Run Hitter)**
    *   *Strategy:* Momentum + OBV
    *   *Style:* Wide stops (-60%). Targets huge gains (+40-80%).
    *   *Goal:* Surviving noise to catch the big trend.
