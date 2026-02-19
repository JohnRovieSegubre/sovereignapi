�A"""
Sovereign Watcher (Polygon Branch)
==================================
Monitors the Polygon Blockchain for USDC deposits.
Automatically mints "Sovereign Macaroons" when money arrives.

Architecture:
  [User] -> (USDC) -> [Proxy Wallet] -> [Watcher Script] -> (Mint Command) -> [Gateway]
"""

import time
import requests
import json
import sys
import logging
import os
from web3 import Web3
from pathlib import Path

# --- CONFIGURATION (Set via Environment Variables) ---

# 1. YOUR WALLET (The Cash Register)
MY_WALLET_ADDRESS = os.getenv("MY_WALLET_ADDRESS")
if not MY_WALLET_ADDRESS:
    print("[CRITICAL] MY_WALLET_ADDRESS not set! Set it as an environment variable.")
    sys.exit(1)

# 2. YOUR GATEWAY (The Mint)
GATEWAY_MINT_URL = os.getenv("GATEWAY_MINT_URL", "http://localhost:8000/v1/admin/mint")

# 3. POLYGON RPC
POLYGON_RPC = os.getenv("POLYGON_RPC")
if not POLYGON_RPC:
    print("[CRITICAL] POLYGON_RPC not set! Set it as an environment variable.")
    sys.exit(1)

# 4. CHAINLINK ORACLE (Real-Time BTC/USD Pricing)
#    Polygon Mainnet BTC/USD Price Feed
CHAINLINK_BTC_USD_FEED = "0xc907E116054Ad103354f2D350FD2514433D57F6f"
FALLBACK_BTC_PRICE = 70000  # Used if oracle fails

# Chainlink Aggregator V3 ABI (minimal)
CHAINLINK_ABI = json.loads('[{"inputs":[],"name":"latestRoundData","outputs":[{"internalType":"uint80","name":"roundId","type":"uint80"},{"internalType":"int256","name":"answer","type":"int256"},{"internalType":"uint256","name":"startedAt","type":"uint256"},{"internalType":"uint256","name":"updatedAt","type":"uint256"},{"internalType":"uint80","name":"answeredInRound","type":"uint80"}],"stateMutability":"view","type":"function"}]')

def get_btc_price_from_chainlink():
    """Fetch real-time BTC/USD price from Chainlink Oracle on Polygon."""
    try:
        chainlink_contract = w3.eth.contract(
            address=Web3.to_checksum_address(CHAINLINK_BTC_USD_FEED),
            abi=CHAINLINK_ABI
        )
        _, answer, _, updated_at, _ = chainlink_contract.functions.latestRoundData().call()
        
        # Chainlink returns 8 decimals for BTC/USD
        btc_price = answer / 1e8
        
        # Check staleness (data older than 1 hour = stale)
        age_seconds = int(time.time()) - updated_at
        if age_seconds > 3600:
            logger.warning(f"⚠️ Chainlink data is stale ({age_seconds}s old). Using fallback.")
            return FALLBACK_BTC_PRICE
        
        logger.info(f"📊 Chainlink BTC/USD: ${btc_price:,.2f}")
        return btc_price
    except Exception as e:
        logger.warning(f"⚠️ Chainlink error: {e}. Using fallback ${FALLBACK_BTC_PRICE}")
        return FALLBACK_BTC_PRICE

def get_sats_per_usdc():
    """Calculate sats per USDC using real-time BTC price. Always rounds DOWN."""
    btc_price = get_btc_price_from_chainlink()
    # 100,000,000 sats / BTC price = sats per $1
    # Use floor division to always round DOWN (user never gets more than they paid for)
    sats = int(100_000_000 // btc_price)
    return sats

# --- SYSTEM CONSTANTS ---
USDC_CONTRACT_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359" # Native USDC Polygon
POLL_INTERVAL = 10  # Seconds (Values < 5 may hit Alchemy free tier limits)

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Watcher")

# Load Admin Key (Prefer Env Var)
ADMIN_KEY = os.getenv("ADMIN_KEY")

if not ADMIN_KEY:
    try:
        params_file = Path(__file__).parent / ".agent" / "secure" / "mint_secret.json"
        if params_file.exists():
            with open(params_file, 'r') as f:
                ADMIN_KEY = json.load(f).get("MINT_SECRET")
    except Exception as e:
        logger.warning(f"Failed to load ADMIN_KEY from file: {e}")

if not ADMIN_KEY:
    logger.critical("ADMIN_KEY is missing! Provisioning credits will fail.")
    sys.exit(1)



# --- SETUP WEB3 ---
logger.info("🔌 Connecting to Polygon via Alchemy...")
try:
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        raise ConnectionError("Web3.is_connected() returned False")
    
    current_block = w3.eth.block_number
    logger.info(f"✅ Connected! Current Block: {current_block}")

except Exception as e:
    logger.critical(f"Failed to connect to Polygon: {e}")
    sys.exit(1)

# ERC-20 ABI (Transfer Event Only)
ERC20_ABI = json.loads('[{"anonymous":false,"inputs":[{"indexed":true,"internalType":"address","name":"from","type":"address"},{"indexed":true,"internalType":"address","name":"to","type":"address"},{"indexed":false,"internalType":"uint256","name":"value","type":"uint256"}],"name":"Transfer","type":"event"}]')

contract = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=ERC20_ABI)


# --- CORE LOGIC ---

def mint_credits(tx_hash, amount_usdc, sender):
    """
    Calls the Local Gateway to mint Macaroons.
    Uses real-time Chainlink oracle for BTC/USD pricing.
    """
    # Get real-time rate and use floor division (always round DOWN)
    sats_per_usdc = get_sats_per_usdc()
    amount_sats = int(amount_usdc * sats_per_usdc)  # Floor by int()
    
    print("\n" + "="*60)
    print(f"💰 [DEPOSIT DETECTED] {amount_usdc:,.2f} USDC from {sender[:10]}...")
    print(f"   Tx: {tx_hash}")
    print(f"   Converting to: {amount_sats} Sats (Rate: {sats_per_usdc} sats/$1)")
    print("-" * 60)
    
    payload = {
        "amount_sats": amount_sats,
        "identifier": tx_hash # Critical Idempotency Key
    }
    
    try:
        resp = requests.post(
            GATEWAY_MINT_URL, 
            json=payload, 
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ [MAILBOX FILLED] Token ready for pickup.")
            print(f"   Agent can claim with tx_hash: {tx_hash[:16]}...")
            print("=" * 60 + "\n")
            
        elif resp.status_code == 409:
            print(f"⚠️ [SKIP] Transaction already processed.")
            print("=" * 60 + "\n")
            
        else:
            print(f"❌ [MINT ERROR] {resp.status_code} {resp.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ [ERROR] Gateway is unreachable!")


def watch_loop():
    if "0xYOUR" in MY_WALLET_ADDRESS:
        logger.error("Please configure MY_WALLET_ADDRESS in the script first!")
        sys.exit(1)

    logger.info(f"👀 Watching for USDC -> {MY_WALLET_ADDRESS}")
    logger.info("   (Press Ctrl+C to stop)")
    
    # Start mainly for new blocks
    last_processed_block = w3.eth.block_number
    
    while True:
        try:
            current_block = w3.eth.block_number
            
            if current_block > last_processed_block:
                # Scan a range (max 50 to avoid RPC limits)
                to_scan = min(current_block, last_processed_block + 50)
                
                # Fetch Logs
                logs = contract.events.Transfer.get_logs(
                    fromBlock=last_processed_block + 1,
                    toBlock=to_scan
                )
                
                for log in logs:
                    to_address = log['args']['to']
                    
                    if to_address.lower() == MY_WALLET_ADDRESS.lower():
                        # Found a deposit!
                        amount_units = log['args']['value']
                        amount_usdc = amount_units / 1_000_000 # USDC = 6 decimals
                        sender = log['args']['from']
                        tx_hash = log['transactionHash'].hex()
                        
                        mint_credits(tx_hash, amount_usdc, sender)
                
                last_processed_block = to_scan
                
                if to_scan < current_block:
                    # If we are catching up, don't sleep
                    continue
            
            time.sleep(POLL_INTERVAL)
            
        except Exception as e:
            logger.warning(f"RPC Error: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    watch_loop()
�A*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062Gfile:///c:/Users/rovie%20segubre/agent/sovereign_api/polygon_watcher.py:&file:///c:/Users/rovie%20segubre/agent