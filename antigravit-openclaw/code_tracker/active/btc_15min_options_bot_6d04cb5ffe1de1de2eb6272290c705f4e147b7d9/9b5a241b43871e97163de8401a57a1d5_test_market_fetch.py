¸from module2_market_orchestrator import MarketOrchestrator
import traceback

print("Testing Market Fetching...")
orch = MarketOrchestrator()
try:
    print("Calling find_active_1hour_market()...")
    market = orch.find_active_1hour_market()
    if market:
        print(f"Success! Found market: {market.get('question')}")
    else:
        print("No market found (but no crash).")
except Exception:
    traceback.print_exc()
¸"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Kfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/test_market_fetch.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot