à-import os
import json
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds

# Load environment variables
load_dotenv()

# Initialize CLOB client
private_key = os.getenv("OWNER_PRIVATE_KEY")
host = "https://clob.polymarket.com"

creds = ApiCreds(
    api_key=os.getenv("CLOB_API_KEY"),
    api_secret=os.getenv("CLOB_SECRET"),
    api_passphrase=os.getenv("CLOB_PASSPHRASE")
)

client = ClobClient(
    host=host,
    key=private_key,
    chain_id=137,
    creds=creds
)

print("="*80)
print("SEARCHING FOR BTC 1-HOUR MARKETS")
print("="*80)

# Try get_sampling_markets with all data
try:
    sampling = client.get_sampling_markets()
    
    if 'data' in sampling:
        all_markets = sampling['data']
        print(f"\nTotal sampling markets: {len(all_markets)}")
        
        # Filter for BTC/Bitcoin markets
        btc_markets = []
        for market in all_markets:
            question = market.get('question', '').lower()
            slug = market.get('market_slug', '').lower()
            
            if 'btc' in question or 'bitcoin' in question or 'btc' in slug:
                btc_markets.append(market)
        
        print(f"BTC-related markets found: {len(btc_markets)}")
        
        # Check for 15-minute or up/down markets
        rapid_markets = []
        for market in btc_markets:
            question = market.get('question', '').lower()
            slug = market.get('market_slug', '').lower()
            desc = market.get('description', '').lower()
            
            if any(term in slug or term in question or term in desc 
                   for term in ['1h', '60m', '1-hour', 'updown', 'up/down', 'rapid']):
                rapid_markets.append(market)
        
        print(f"1-hour/rapid markets: {len(rapid_markets)}")
        
        if rapid_markets:
            print("\n" + "="*80)
            print("FOUND BTC 1-HOUR MARKETS!")
            print("="*80)
            for market in rapid_markets:
                print(f"\nQuestion: {market.get('question')}")
                print(f"Slug: {market.get('market_slug')}")
                print(f"Condition ID: {market.get('condition_id')}")
                print(f"Active: {market.get('active')}")
                print(f"Tokens:")
                for token in market.get('tokens', []):
                    print(f"  - {token.get('outcome')}: {token.get('token_id')}")
        else:
            print("\nNo 15-minute markets found in sampling markets.")
            print("\nShowing first 3 BTC markets:")
            for market in btc_markets[:3]:
                print(f"\n  - {market.get('question')}")
                print(f"    Slug: {market.get('market_slug')}")
        
        # Check if there are any with short time windows
        print(f"\n{'='*80}")
        print("Checking for markets with short resolution times...")
        print(f"{'='*80}")
        
        from datetime import datetime
        now = datetime.utcnow()
        
        short_window_markets = []
        for market in all_markets:
            end_date_str = market.get('end_date_iso')
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    hours_until_end = (end_date - now).total_seconds() / 3600
                    
                    if 0 < hours_until_end <= 1:  # Ends within 1 hour
                        short_window_markets.append({
                            'market': market,
                            'hours_left': hours_until_end
                        })
                except:
                    pass
        
        if short_window_markets:
            print(f"\nMarkets ending within 1 hour: {len(short_window_markets)}")
            for item in short_window_markets[:5]:
                m = item['market']
                print(f"\n  - {m.get('question')}")
                print(f"    Time left: {item['hours_left']:.2f} hours")
                print(f"    Slug: {m.get('market_slug')}")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Try get_markets() with active filter
print(f"\n{'='*80}")
print("Trying get_markets() with filters...")
print(f"{'='*80}")

try:
    # The user's URL: https://polymarket.com/event/btc-updown-15m-1763153100
    # Let's try to search for this specific slug
    markets_response = client.get_markets()
    
    if isinstance(markets_response, dict) and 'data' in markets_response:
        all_markets = markets_response['data']
        print(f"\nTotal markets from get_markets(): {len(all_markets)}")
        
        # Search for btc-updown patterns
        updown_markets = [m for m in all_markets 
                          if 'btc-updown' in m.get('market_slug', '').lower()]
        
        print(f"Markets with 'btc-updown' in slug: {len(updown_markets)}")
        
        if updown_markets:
            print("\nFOUND BTC UP/DOWN MARKETS!")
            for market in updown_markets[:5]:
                print(f"\n  Question: {market.get('question')}")
                print(f"  Slug: {market.get('market_slug')}")
                print(f"  Active: {market.get('active')}")
                
except Exception as e:
    print(f"Error with get_markets(): {e}")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print("If no BTC 15-minute markets found, they may be:")
print("1. Created dynamically and only visible when active")
print("2. In a special endpoint we haven't found yet")
print("3. Require fetching by exact condition_id or token_id")
print("4. Only accessible via websocket/streaming API")
à-"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Jfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/search_btc_15min.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot