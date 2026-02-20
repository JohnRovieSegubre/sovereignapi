"""
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
        api_key="sk-sov-xxx",
        private_key="0x...",
        base_url="http://YOUR_GATEWAY:8000/v1",
        gateway_wallet="0xYOUR_WALLET"
    )
    
    response = client.chat.completions.create(
        model="sovereign/deepseek-r1",
        messages=[{"role": "user", "content": "Hello!"}]
    )
"""

import time
import requests
import os
import base64
import json
from eth_account import Account
from web3 import Web3

# x402 client SDK (optional — for Base USDC auto-pay)
try:
    from x402 import x402ClientSync
    from x402.http.clients import x402_requests
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact.register import register_exact_evm_client
    X402_CLIENT_AVAILABLE = True
except ImportError:
    X402_CLIENT_AVAILABLE = False

# --- CONSTANTS ---
# Standard USDC Contract on Polygon
USDC_ADDRESS = "0x036CbD53842c5426634e7929541eC2318f3dCF7e" # Base Sepolia

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
        
        # Defaults (MUST be set via env vars or constructor args)
        self.base_url = base_url or os.getenv("GATEWAY_URL")
        if not self.base_url:
            raise ValueError("GATEWAY_URL is required. Set env var or pass base_url.")
        self.base_url = self.base_url.rstrip('/')
        
        self.gateway_wallet = gateway_wallet or os.getenv("GATEWAY_WALLET")
        self.rpc_url = rpc_url or os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
        self.disable_gasless_relay = os.getenv("DISABLE_GASLESS_RELAY", "0") == "1"
        
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
        
        print(f"🤖 Sovereign SDK Initialized (Phase 7)")
        print(f"   Gateway: {self.base_url}")
        print(f"   API Key: {self.api_key[:12]}..." if self.api_key else "   API Key: Not Set")
        print(f"   Mock Mode: {'ON' if self.mock_mode else 'OFF'}")

    def refuel_balance(self):
        """
        Attempts to refuel the balance (buy a macaroon).
        Supports x402 (Instant) and Legacy (Polygon TX + Watcher).
        """
        # 1. Try x402 (Base Sepolia / Coinbase CDP)
        if self._has_x402_support():
            print("⛽ Refueling via x402 (Instant)...")
            try:
                session = self._get_x402_session()
                url = f"{self.base_url}/balance/topup"
                resp = session.post(url, json={}, headers={"Content-Type": "application/json"}, timeout=120)
                
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data["token"]  # Auto-update token
                    print(f"✅ Refueled! Credit: {data.get('credits_sats')} sats")
                    return self.token
                else:
                    print(f"❌ x402 Refuel Failed: {resp.status_code} - {resp.text}")
                    # Fallthrough to legacy
            except Exception as e:
                print(f"⚠️  x402 Refuel Error: {e}")
        
        # 2. Legacy Fallback (Polygon / Watcher)
        print("⏳ Falling back to Legacy Refuel (Polygon)...")
        tx = self._send_usdc(amount_usd=1.0)
        return self._claim_macaroon(tx)

    class Chat:
        def __init__(self, client):
            self.client = client
            self.completions = self.Completions(client)

        class Completions:
            def __init__(self, client):
                self.client = client

            # --- CORE METHODS ---



            def create(self, model, messages, max_retries=1, **kwargs):
                """
                Send a chat request. Automatically pays if 402 is returned.
                kwargs: Pass 'tools', 'tool_choice', 'max_tokens' etc.
                """
                url = f"{self.client.base_url}/chat/completions"
                payload = {"model": model, "messages": messages}
                payload.update(kwargs)
                
                # Prepare Headers (API Key + Macaroon)
                headers = {"Content-Type": "application/json"}
                
                # API Key (Identity/License) - Phase 7
                if self.client.api_key:
                    headers["X-Sovereign-Api-Key"] = self.client.api_key
                
                # Macaroon (Fuel)
                if self.client.token:
                    headers["Authorization"] = f"Bearer {self.client.token}"

                try:
                    print(f"🔄 Sending Request to {model}...")
                    response = requests.post(url, json=payload, headers=headers, timeout=120)
                    
                    # --- SUCCESS (200) ---
                    if response.status_code == 200:
                        # ROTATION: Grab the new token from the header!
                        new_token = response.headers.get("X-Sovereign-Balance-Token")
                        if new_token:
                            self.client.token = new_token
                            print("🔄 Token Rotated (Balance Updated)")
                            
                        # x402 RECEIPT
                        receipt_b64 = response.headers.get("PAYMENT-RESPONSE")
                        if receipt_b64:
                            try:
                                receipt = json.loads(base64.b64decode(receipt_b64).decode())
                                print(f"🧾 x402 Receipt: {receipt.get('paymentId')}")
                            except:
                                pass
                                
                        return response.json()
                    
                    # --- UNAUTHORIZED (401) - Invalid API Key ---
                    elif response.status_code == 401:
                        error = response.json().get("error", "Invalid API Key")
                        print(f"🛑 [401] API Key Rejected: {error}")
                        raise ValueError(f"Invalid API Key: {error}")

                    # --- PAYMENT REQUIRED (402) ---
                    elif response.status_code == 402:
                        print("💰 Payment Required (402). Checking Protocol...")
                        
                        # === CASE A: x402 (Real CDP Protocol) ===
                        x402_header = response.headers.get("PAYMENT-REQUIRED")
                        if x402_header and self.client._has_x402_support():
                            print("⚡ x402 Header Detected. Auto-paying via x402 SDK...")
                            try:
                                x402_session = self.client._get_x402_session()
                                retry_resp = x402_session.post(url, json=payload, headers=headers, timeout=120)
                                if retry_resp.ok:
                                    new_token = retry_resp.headers.get("X-Sovereign-Balance-Token")
                                    if new_token:
                                        self.client.token = new_token
                                    return retry_resp.json()
                                else:
                                    return {"error": f"x402 payment failed: {retry_resp.status_code}", "detail": retry_resp.text}
                            except Exception as e:
                                print(f"❌ x402 auto-pay error: {e}")
                                return {"error": f"x402 Payment Failed: {e}"}

                        # === CASE B: MACAROON / POLYGON (Legacy/Prepay) ===
                        print("   Falling back to Polygon Prepay...")
                        
                        if self.client.mock_mode:
                            print("🎭 [MOCK MODE] Would pay $1.00 USDC. Skipping...")
                            return {"error": "Mock Mode - Payment simulated", "would_pay": 1.0}
                        
                        if not self.client.private_key:
                            return {"error": "No private key configured. Cannot auto-pay."}
                        
                        # 1. Pay via Polygon (Default $1.00 USDC)
                        tx_hash = self.client._send_usdc(amount_usd=1.0)
                        
                        # 2. Claim the Macaroon from the Mailbox
                        print(f"📬 Claiming Token for Tx: {tx_hash}...")
                        new_macaroon = self.client._claim_macaroon(tx_hash)
                        
                        # 3. Save & Retry
                        self.client.token = new_macaroon
                        print("🔁 Retrying request with new token...")
                        return self.create(model, messages)  # Recursive Retry
                    
                    # --- FORBIDDEN (403) - Token Invalid ---
                    elif response.status_code == 403:
                        print(f"🛑 Token Invalid/Rejected: {response.text}")
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
                    print("\n✅ Token Claimed Successfully!")
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

        # Check native POL balance (gas)
        gas_balance = w3.eth.get_balance(self.address)
        
        if gas_balance == 0:
            if self.disable_gasless_relay:
                raise ValueError("Insufficient gas (ETH) and Gasless Relay is disabled!")
            print("⛽ No POL for gas. Attempting gasless relay refuel...")
            return self._send_usdc_relayed(amount_usd)

        # Setup Contract
        usdc = w3.eth.contract(address=USDC_ADDRESS, abi=ERC20_ABI)
        amount_units = int(amount_usd * (10 ** 6))

        # Build Transaction
        nonce = w3.eth.get_transaction_count(self.address)
        
        tx = usdc.functions.transfer(
            self.gateway_wallet,
            amount_units
        ).build_transaction({
            'chainId': 137,  # Polygon Mainnet
            'gas': 100000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce,
        })

        # Sign & Send
        signed_tx = w3.eth.account.sign_transaction(tx, self.private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"💸 Sent ${amount_usd} USDC. Tx: {tx_hash.hex()}")
        return tx_hash.hex()

    def _send_usdc_relayed(self, amount_usd):
        """Sends USDC via Gateway Relayer (EIP-3009) — No POL needed."""
        import secrets
        
        amount_units = int(amount_usd * (10 ** 6))
        nonce = "0x" + secrets.token_hex(32)
        valid_after = 0
        valid_before = int(time.time()) + 3600  # 1 hour
        
        # EIP-712 Domain and Message
        domain_data = {
            "name": "USD Coin",
            "version": "2",
            "chainId": 84532, # Base Sepolia
            "verifyingContract": USDC_ADDRESS
        }
        
        message_types = {
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ]
        }
        
        message_data = {
            "from": self.address,
            "to": self.gateway_wallet,
            "value": amount_units,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
        }
        
        from eth_account.messages import encode_typed_data
        encoded_data = encode_typed_data(domain_data, message_types, message_data)
        signed_msg = self.account.sign_message(encoded_data)
        
        # Call Relayer
        relay_url = f"{self.base_url}/refuel/relay"
        payload = {
            "from": self.address,
            "to": self.gateway_wallet,
            "value": amount_units,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce,
            "signature": signed_msg.signature.hex()
        }
        
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Sovereign-Api-Key"] = self.api_key
            
        resp = requests.post(relay_url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            tx_hash = resp.json().get("tx_hash")
            print(f"🚀 Relayed Transaction Sent! Tx: {tx_hash}")
            return tx_hash
        else:
            raise ValueError(f"Relay failed: {resp.text}")

    def _has_x402_support(self):
        """Check if this client can auto-pay via x402 (needs private key + SDK)."""
        return X402_CLIENT_AVAILABLE and self.private_key is not None

    def _get_x402_session(self):
        """Create an x402-aware requests session that auto-handles 402 → sign → retry."""
        if not X402_CLIENT_AVAILABLE:
            raise ImportError("x402 SDK not installed. Run: pip install 'x402[requests]'")
        if not self.private_key:
            raise ValueError("No private key configured for x402 signing.")

        client = x402ClientSync()
        register_exact_evm_client(client, EthAccountSigner(self.account))
        return x402_requests(client)
    
    def set_token(self, token):
        """
        Manually set a Macaroon token (e.g., from admin mint).
        """
        self.token = token
        print(f"🔑 Token set: {token[:20]}...")
    def get_balance_estimate(self):
        """Get balance from API (no client-side parsing needed)."""
        if not self.token:
            return 0
            
        url = f"{self.base_url}/balance"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            resp = requests.post(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("balance_sats", 0)
        except Exception:
            pass
            
        return -1  # Unknown
