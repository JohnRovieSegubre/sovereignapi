ÍQ"""
Sovereign SDK - The 'Stripe for AI' Library
============================================
Allows AI Agents to pay for intelligence using crypto.

This SDK handles:
1. Macaroon-based authentication
2. Automatic USDC payments on Polygon
3. Mailbox claiming (polling for minted tokens)
4. Token rotation (session management)

Usage:
    from sovereign import SovereignClient
    
    client = SovereignClient(
        private_key="0x...",
        base_url="http://34.55.175.24:8000/v1",
        gateway_wallet="0xC8Dc..."
    )
    
    response = client.chat.completions.create(
        model="sovereign-r1",
        messages=[{"role": "user", "content": "Hello!"}]
    )
"""

import time
import requests
import os
from eth_account import Account
from web3 import Web3

# --- CONSTANTS ---
# Standard USDC Contract on Polygon
USDC_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"

# Minimal ABI for 'transfer'
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


class SovereignClient:
    """
    The 'Stripe for AI' SDK.
    Manages API Keys (Identity), Macaroons (Fuel), Payments, and Claims automatically.
    
    Phase 7 Architecture:
        - api_key (sk-sov-xxx): Your persistent license/identity
        - macaroon: Your liquid fuel/credits (transferable)
    """
    
    def __init__(
        self, 
        api_key=None,
        private_key=None, 
        base_url=None,
        gateway_wallet=None, 
        rpc_url=None,
        mock_mode=False
    ):
        # API Key (Identity/License)
        self.api_key = api_key or os.getenv("SOVEREIGN_API_KEY")
        
        # Mock Mode (Skip real blockchain transactions)
        self.mock_mode = mock_mode or os.getenv("MOCK_MODE", "0") == "1"
        
        # Defaults (can be overridden by env vars)
        self.base_url = base_url or os.getenv("GATEWAY_URL", "http://34.55.175.24:8000/v1")
        self.base_url = self.base_url.rstrip('/')
        
        self.gateway_wallet = gateway_wallet or os.getenv("GATEWAY_WALLET", "0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d")
        self.rpc_url = rpc_url or os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
        self.private_key = private_key or os.getenv("AGENT_PRIVATE_KEY")
        
        # Identity (only if private key provided)
        if self.private_key:
            self.account = Account.from_key(self.private_key)
            self.address = self.account.address
        else:
            self.account = None
            self.address = None
        
        self.token = None  # The Macaroon (Bearer Token / Fuel)
        
        # Setup Namespaces (OpenAI-style API)
        self.chat = self.Chat(self)
        
        print(f"ü§ñ Sovereign SDK Initialized (Phase 7)")
        print(f"   Gateway: {self.base_url}")
        print(f"   API Key: {self.api_key[:12]}..." if self.api_key else "   API Key: Not Set")
        print(f"   Mock Mode: {'ON' if self.mock_mode else 'OFF'}")

    class Chat:
        def __init__(self, client):
            self.client = client
            self.completions = self.Completions(client)

        class Completions:
            def __init__(self, client):
                self.client = client

            def create(self, model, messages, max_retries=1):
                """
                Send a chat request. Automatically pays if 402 is returned.
                Raises error on 401 (invalid API key).
                """
                url = f"{self.client.base_url}/chat/completions"
                payload = {"model": model, "messages": messages}
                
                # Prepare Headers (API Key + Macaroon)
                headers = {"Content-Type": "application/json"}
                
                # API Key (Identity/License) - Phase 7
                if self.client.api_key:
                    headers["X-Sovereign-Api-Key"] = self.client.api_key
                
                # Macaroon (Fuel)
                if self.client.token:
                    headers["Authorization"] = f"Bearer {self.client.token}"

                try:
                    print(f"üîÑ Sending Request to {model}...")
                    response = requests.post(url, json=payload, headers=headers, timeout=120)
                    
                    # --- SUCCESS (200) ---
                    if response.status_code == 200:
                        # ROTATION: Grab the new token from the header!
                        new_token = response.headers.get("X-Sovereign-Balance-Token")
                        if new_token:
                            self.client.token = new_token
                            print("üîÑ Token Rotated (Balance Updated)")
                        return response.json()
                    
                    # --- UNAUTHORIZED (401) - Invalid API Key ---
                    elif response.status_code == 401:
                        error = response.json().get("error", "Invalid API Key")
                        print(f"üõë [401] API Key Rejected: {error}")
                        raise ValueError(f"Invalid API Key: {error}")

                    # --- PAYMENT REQUIRED (402) ---
                    elif response.status_code == 402:
                        print("üí∞ Payment Required (402). Initiating Deposit...")
                        
                        if self.client.mock_mode:
                            print("üé≠ [MOCK MODE] Would pay $1.00 USDC. Skipping...")
                            return {"error": "Mock Mode - Payment simulated", "would_pay": 1.0}
                        
                        if not self.client.private_key:
                            return {"error": "No private key configured. Cannot auto-pay."}
                        
                        # 1. Pay via Polygon (Default $1.00 USDC)
                        tx_hash = self.client._send_usdc(amount_usd=1.0)
                        
                        # 2. Claim the Macaroon from the Mailbox
                        print(f"üì¨ Claiming Token for Tx: {tx_hash}...")
                        new_macaroon = self.client._claim_macaroon(tx_hash)
                        
                        # 3. Save & Retry
                        self.client.token = new_macaroon
                        print("üîÅ Retrying request with new token...")
                        return self.create(model, messages)  # Recursive Retry
                    
                    # --- FORBIDDEN (403) - Token Invalid ---
                    elif response.status_code == 403:
                        print(f"üõë Token Invalid/Rejected: {response.text}")
                        return {"error": "Token rejected", "detail": response.text}
                    
                    else:
                        return {"error": f"API Error {response.status_code}", "msg": response.text}

                except requests.exceptions.Timeout:
                    return {"error": "Request timed out"}
                except Exception as e:
                    return {"error": str(e)}

    # --- INTERNAL MECHANICS ---

    def _claim_macaroon(self, tx_hash, max_attempts=30, poll_interval=2):
        """
        Polls the Gateway's mailbox until the Watcher confirms the deposit.
        """
        claim_url = f"{self.base_url}/balance/claim"
        
        print(f"   Polling {claim_url}...", end="", flush=True)
        
        for attempt in range(max_attempts):
            try:
                resp = requests.post(claim_url, json={"tx_hash": tx_hash}, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    print("\n‚úÖ Token Claimed Successfully!")
                    return data["access_token"]
                    
                elif resp.status_code == 410:
                    raise ValueError("Token already claimed!")
                    
                elif resp.status_code == 404:
                    # Still processing...
                    print(".", end="", flush=True)
                    
            except requests.exceptions.RequestException:
                print("!", end="", flush=True)  # Connection error
            
            time.sleep(poll_interval)
        
        print()
        raise TimeoutError(f"Deposit not detected by Watcher after {max_attempts * poll_interval}s")

    def _send_usdc(self, amount_usd):
        """
        Sends USDC on Polygon. Returns the Transaction Hash.
        """
        if not self.gateway_wallet:
            raise ValueError("Gateway Wallet Address not configured in SDK!")

        w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        if not w3.is_connected():
            raise ConnectionError(f"Cannot connect to Polygon RPC: {self.rpc_url}")

        # Setup Contract
        usdc = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
        decimals = 6
        amount_units = int(amount_usd * (10 ** decimals))

        # Check Balance
        my_balance = usdc.functions.balanceOf(self.address).call() if hasattr(usdc.functions, 'balanceOf') else 0
        
        # Build Transaction
        nonce = w3.eth.get_transaction_count(self.address)
        
        tx = usdc.functions.transfer(
            self.gateway_wallet,
            amount_units
        ).build_transaction({
            'chainId': 137,  # Polygon Mainnet
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
        })

        # Sign & Send
        signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"üí∏ Sent ${amount_usd} USDC. Tx: {tx_hash.hex()}")
        return tx_hash.hex()
    
    def set_token(self, token):
        """
        Manually set a Macaroon token (e.g., from admin mint).
        """
        self.token = token
        print(f"üîë Token set: {token[:20]}...")
¸
 *cascade08¸
ë*cascade08ëö *cascade08ö°*cascade08°Ã *cascade08ÃÏ*cascade08Ïò *cascade08òØ*cascade08Øƒ *cascade08ƒ…*cascade08…ò *cascade08ò≤*cascade08≤∆ *cascade08∆≈*cascade08≈Å *cascade08Å£*cascade08£¡ *cascade08¡‡*cascade08‡È *cascade08Èã*cascade08ã¨ *cascade08¨±*cascade08±ø *cascade08ø√*cascade08√¯ *cascade08¯”*cascade08”Ç *cascade08Çâ*cascade08â¢ *cascade08¢¨*cascade08¨Ú *cascade08Ú¯*cascade08¯˘ *cascade08˘˙*cascade08˙˚ *cascade08˚Å*cascade08ÅÇ *cascade08Çò*cascade08òô *cascade08ô§*cascade08§• *cascade08•¶*cascade08¶ß *cascade08ß∑*cascade08∑∏ *cascade08∏‹*cascade08‹ﬂ *cascade08ﬂÁ*cascade08ÁÏ *cascade08ÏÛ*cascade08ÛÙ *cascade08Ùˆ*cascade08ˆ˜ *cascade08˜¯*cascade08¯˘ *cascade08˘Ä*cascade08Ä∏ *cascade08∏*cascade08Ø *cascade08Ø∑*cascade08∑Å  *cascade08Å Û!*cascade08Û!ò( *cascade08ò(â+*cascade08â+À, *cascade08À,Ç0*cascade08Ç0ÍQ *cascade08"(d4e7a325d0144b3814ef864593774f7a3951320627file:///c:/Users/rovie%20segubre/agent/sdk/sovereign.py:&file:///c:/Users/rovie%20segubre/agent