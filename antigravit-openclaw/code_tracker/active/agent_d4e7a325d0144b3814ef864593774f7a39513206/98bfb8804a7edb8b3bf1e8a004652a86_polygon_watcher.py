ìA"""
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

# --- CONFIGURATION (EDIT THESE) ---

# 1. YOUR WALLET (The Cash Register)
#    Use a PROXY wallet, not your main cold storage!
MY_WALLET_ADDRESS = "0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d" 

# 2. YOUR GATEWAY (The Mint)
GATEWAY_MINT_URL = os.getenv("GATEWAY_MINT_URL", "http://localhost:8000/v1/admin/mint")

# 3. POLYGON RPC (Alchemy)
#    Dedicated endpoint for reliability.
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-mainnet.g.alchemy.com/v2/S__e1JUkM03zL4EonOpfV")

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
            logger.warning(f"‚ö†Ô∏è Chainlink data is stale ({age_seconds}s old). Using fallback.")
            return FALLBACK_BTC_PRICE
        
        logger.info(f"üìä Chainlink BTC/USD: ${btc_price:,.2f}")
        return btc_price
    except Exception as e:
        logger.warning(f"‚ö†Ô∏è Chainlink error: {e}. Using fallback ${FALLBACK_BTC_PRICE}")
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
logger.info("üîå Connecting to Polygon via Alchemy...")
try:
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        raise ConnectionError("Web3.is_connected() returned False")
    
    current_block = w3.eth.block_number
    logger.info(f"‚úÖ Connected! Current Block: {current_block}")

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
    print(f"üí∞ [DEPOSIT DETECTED] {amount_usdc:,.2f} USDC from {sender[:10]}...")
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
            print(f"‚úÖ [MAILBOX FILLED] Token ready for pickup.")
            print(f"   Agent can claim with tx_hash: {tx_hash[:16]}...")
            print("=" * 60 + "\n")
            
        elif resp.status_code == 409:
            print(f"‚ö†Ô∏è [SKIP] Transaction already processed.")
            print("=" * 60 + "\n")
            
        else:
            print(f"‚ùå [MINT ERROR] {resp.status_code} {resp.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"‚ùå [ERROR] Gateway is unreachable!")


def watch_loop():
    if "0xYOUR" in MY_WALLET_ADDRESS:
        logger.error("Please configure MY_WALLET_ADDRESS in the script first!")
        sys.exit(1)

    logger.info(f"üëÄ Watching for USDC -> {MY_WALLET_ADDRESS}")
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
¯ *cascade08¯É*cascade08É— *cascade08—”*cascade08”‘ *cascade08‘‡*cascade08‡· *cascade08·Î*cascade08ÎÏ *cascade08Ï˘*cascade08˘∞ *cascade08∞Œ*cascade08ŒÛ *cascade08ÛÙ*cascade08ÙÃ *cascade08ÃÂ*cascade08Â• *cascade08•¶*cascade08¶≤ *cascade08≤≥*cascade08≥¥ *cascade08¥∏*cascade08∏π *cascade08π∫*cascade08∫º *cascade08ºæ*cascade08æ¡ *cascade08¡¬*cascade08¬√ *cascade08√ƒ *cascade08
ƒ≈ ≈…*cascade08…À *cascade08ÀŒŒ⁄*cascade08⁄‚ *cascade08‚Ò*cascade08ÒÚ *cascade08Úııú*cascade08úû *cascade08ûü *cascade08üß*cascade08ß® *cascade08®™*cascade08
™´ ´∞*cascade08
∞± ±∫*cascade08
∫ª ª„*cascade08
„Ê ÊÁ *cascade08ÁÍ*cascade08ÍÎ *cascade08ÎÏ*cascade08ÏÌ *cascade08Ìı*cascade08ıˆ *cascade08ˆ˛*cascade08˛ˇ *cascade08
ˇÅ	 Å	É	*cascade08
É	Ñ	 Ñ	Ö	 *cascade08Ö	é	*cascade08
é	è	 è	ô	*cascade08
ô	ö	 ö	ú	*cascade08
ú	ù	 ù	ê
*cascade08
ê
ë
 ë
í
*cascade08
í
ì
 ì
±
*cascade08
±
≤
 ≤
É*cascade08
ÉÑ Ñ¨*cascade08
¨≠ ≠˜*cascade08
˜˘ ˘˙ *cascade08˙–*cascade08
–— —Ü*cascade08
Üá áà *cascade08àä*cascade08äã *cascade08ãñ*cascade08ñóóò *cascade08òæ*cascade08æøøÿ*cascade08ÿ⁄ *cascade08⁄Ï*cascade08ÏÓ *cascade08Óò*cascade08òõ *cascade08õ©*cascade08©™ *cascade08™´´¨ *cascade08¨µ*cascade08
µ∂ ∂∑*cascade08
∑∏ ∏”*cascade08”‘ *cascade08‘’’‡*cascade08‡· *cascade08
·‚ ‚¯*cascade08
¯˘ ˘˛*cascade08˛Ä *cascade08ÄŒ*cascade08Œœ *cascade08œ◊*cascade08◊ÿ *cascade08ÿï*cascade08ïñ *cascade08ñ∑*cascade08∑π *cascade08πº*cascade08ºΩ *cascade08Ωﬂ*cascade08ﬂ‡ *cascade08‡Ó*cascade08ÓÔ *cascade08Ôõ*cascade08õ† *cascade08†·*cascade08·„ *cascade08„â*cascade08âä *cascade08äò*cascade08òô *cascade08ô«*cascade08«› *cascade08›Ó*cascade08Ó *cascade08≠*cascade08≠≥ *cascade08≥∑*cascade08∑è *cascade08èπ*cascade08π‹ *cascade08‹‰*cascade08‰ô *cascade08ôù*cascade08ù≠ *cascade08≠≤*cascade08≤π *cascade08πΩ*cascade08Ωƒ *cascade08ƒ∆*cascade08∆« *cascade08«»*cascade08»… *cascade08…À*cascade08ÀÃ *cascade08ÃÕ*cascade08ÕŒ *cascade08Œ—*cascade08—“ *cascade08“”*cascade08”’ *cascade08’÷*cascade08÷› *cascade08›Ô*cascade08Ô *cascade08Û*cascade08ÛÙ *cascade08Ù˚*cascade08˚¸ *cascade08¸˛*cascade08˛ˇ *cascade08ˇÄ*cascade08ÄÅ *cascade08Åá*cascade08áà *cascade08àñ*cascade08ñó *cascade08óô*cascade08ôõ *cascade08õú*cascade08úù *cascade08ù≤*cascade08≤≥ *cascade08≥µ*cascade08µ∂ *cascade08∂∑*cascade08∑π *cascade08π¡*cascade08¡ƒ *cascade08ƒ *cascade08 Ã *cascade08ÃÕ*cascade08ÕŒ *cascade08Œœ*cascade08œ– *cascade08–’*cascade08’÷ *cascade08÷◊*cascade08◊Î *cascade08ÎÌ*cascade08ÌË& *cascade08Ë&¢'*cascade08¢'´' *cascade08´'ô(*cascade08ô(π( *cascade08π(Ω(*cascade08Ω(æ( *cascade08æ(¡(*cascade08¡(¬( *cascade08¬(ÿ(*cascade08ÿ(©* *cascade08©*≠**cascade08≠*Æ* *cascade08Æ*±**cascade08±*≤* *cascade08≤*∂**cascade08∂*∑* *cascade08∑*ø**cascade08ø*˛- *cascade08˛-ˇ-*cascade08ˇ-Ä. *cascade08Ä.Ñ.*cascade08Ñ.Ö. *cascade08Ö.â.*cascade08â.ä. *cascade08ä.ã.*cascade08ã.ç. *cascade08ç.ê.*cascade08ê.ë. *cascade08ë.í.*cascade08í.ì. *cascade08ì.î.*cascade08î.ï. *cascade08ï.ñ.*cascade08ñ.ó. *cascade08ó.ò.*cascade08ò.ô. *cascade08ô.ú.*cascade08ú.ü. *cascade08ü.§.*cascade08§.ø. *cascade08ø.¡.*cascade08¡.√. *cascade08√.ƒ.*cascade08ƒ.≈. *cascade08≈.∆.*cascade08∆.…. *cascade08….Œ.*cascade08Œ.œ. *cascade08œ.–.*cascade08–.“. *cascade08“.”.*cascade08”.’. *cascade08’.‹.*cascade08‹.›. *cascade08›.ﬁ.*cascade08ﬁ.ﬂ. *cascade08ﬂ.·.*cascade08·.‚. *cascade08‚.„.*cascade08„.‰. *cascade08‰.Ó.*cascade08Ó.ìA *cascade08"(d4e7a325d0144b3814ef864593774f7a3951320629file:///c:/Users/rovie%20segubre/agent/polygon_watcher.py:&file:///c:/Users/rovie%20segubre/agent