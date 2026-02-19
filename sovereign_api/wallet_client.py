"""
SovereignWallet - The Grand Unified Client
==========================================
A Bearer Asset Wallet for Autonomous AI Agents.

This class handles the complete economic lifecycle:
1. Stores the current Macaroon token (the "Cash")
2. Attaches it to requests automatically
3. Captures the "Change" token from server responses
4. Swaps tokens atomically (preventing replay attacks)

Usage:
    from wallet_client import SovereignWallet
    
    wallet = SovereignWallet()
    response = wallet.think("What is 2+2?")
    print(response)
"""

import httpx
import json
import sys
import time
import os
from pathlib import Path

# --- CONFIGURATION ---
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/v1/chat/completions")
DEFAULT_MODEL = "sovereign/deepseek-r1"  # 10 sats per request

# Unified storage path (single source of truth)
WALLET_DIR = Path(__file__).parent / ".agent" / "wallet"
WALLET_FILE = WALLET_DIR / "wallet.json"


class SovereignWallet:
    """
    A self-managing cryptographic wallet for AI agents.
    
    The wallet automatically rotates tokens after each successful request,
    ensuring the agent never attempts to re-spend a used token.
    """
    
    def __init__(self, storage_path=None):
        print(f"🔌 [WALLET] Using Gateway: {GATEWAY_URL}")
        self.storage_path = Path(storage_path) if storage_path else WALLET_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.token = self._load_token()
        self.last_balance = None  # Track spending (future feature)
    
    def _load_token(self):
        """Load the current token from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    return data.get("access_token")
            except (json.JSONDecodeError, IOError):
                return None
        return None
    
    def save_token(self, token):
        """Atomically save the new token to disk."""
        self.token = token
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump({"access_token": token, "saved_at": time.time()}, f)
    
    def get_balance(self):
        """Extract balance from current token (if possible)."""
        if not self.token:
            return 0
        # Note: Full balance extraction requires pymacaroons
        # For now, return a placeholder indicating token exists
        return "Token Loaded" if self.token else 0
    
    def top_up(self, tx_hash, max_attempts=12, poll_interval=5):
        """
        Polls the Gateway to claim a token after sending crypto.
        
        Args:
            tx_hash: The blockchain transaction hash from the deposit.
            max_attempts: Number of polling attempts (default 12 = 60 seconds).
            poll_interval: Seconds between attempts.
        
        Returns:
            True if token claimed successfully, False otherwise.
        """
        claim_url = GATEWAY_URL.replace("/chat/completions", "/balance/claim")
        print(f"\n💳 [WALLET] Waiting for confirmation of {tx_hash[:16]}...")
        
        for i in range(max_attempts):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(claim_url, json={"tx_hash": tx_hash})
                    
                    if resp.status_code == 200:
                        token = resp.json().get("access_token")
                        self.save_token(token)
                        print(f"\n✅ [SUCCESS] Deposit confirmed! Wallet recharged.")
                        return True
                    
                    elif resp.status_code == 410:
                        print(f"\n⚠️ [ALREADY CLAIMED] Token was already picked up.")
                        return False
                    
                    elif resp.status_code == 404:
                        # Not ready yet, keep polling
                        print(".", end="", flush=True)
                        
            except Exception as e:
                print(f"!", end="", flush=True)  # Connection error indicator
            
            time.sleep(poll_interval)
        
        print(f"\n⏱️ [TIMEOUT] Deposit not seen after {max_attempts * poll_interval}s.")
        print("   The Watcher may still be catching up. Try again later.")
        return False
    
    def think(self, prompt, model=DEFAULT_MODEL):
        """
        Send a thought to the AI and handle the economic lifecycle.
        
        This is the primary interface for autonomous agents.
        Returns the AI response content, or None on failure.
        """
        if not self.token:
            print("❌ [WALLET] Empty! No token available.")
            print("   Mint one with: python -c \"import requests; ...\"")
            return None
        
        print(f"\n📤 [WALLET] Spending token: {self.token[:15]}...")
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        try:
            start_time = time.time()
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(GATEWAY_URL, json=payload, headers=headers)
            duration = time.time() - start_time
            
            # === SUCCESS: Capture Change ===
            if resp.status_code == 200:
                print(f"✅ [SUCCESS] Response in {duration:.1f}s")
                
                # THE CRITICAL STEP: Token Rotation
                new_token = resp.headers.get("X-Sovereign-Balance-Token")
                if new_token:
                    self.save_token(new_token)
                    print("💾 [WALLET] Token rotated and saved.")
                else:
                    print("⚠️ [WARNING] No change token received!")
                
                return resp.json()["choices"][0]["message"]["content"]
            
            # === PAYMENT REQUIRED: Out of funds ===
            elif resp.status_code == 402:
                print("💸 [EMPTY] Insufficient funds!")
                data = resp.json()
                print(f"   Invoice: {data.get('invoice', 'N/A')[:30]}...")
                print(f"   Price: {data.get('price_sats', '?')} sats")
                # Future: Auto-pay via Alby/LND
                return None
            
            # === FORBIDDEN: Replay detected ===
            elif resp.status_code == 403:
                error = resp.json().get("error", "Unknown")
                print(f"🛑 [BLOCKED] {error}")
                print("   Token was already spent. Wallet needs refresh.")
                return None
            
            # === UNEXPECTED ===
            else:
                print(f"❓ [ERROR] {resp.status_code}: {resp.text[:100]}")
                return None
                
        except httpx.TimeoutException:
            print("⏱️ [TIMEOUT] Request took too long.")
            return None
        except Exception as e:
            print(f"🔥 [CRITICAL] {e}")
            return None


# === CLI Interface ===
if __name__ == "__main__":
    wallet = SovereignWallet()
    
    print("🧠 Sovereign Agent Interface (Grand Unified Wallet)")
    print("=" * 50)
    print(f"   Storage: {wallet.storage_path}")
    print(f"   Token:   {'Loaded' if wallet.token else 'EMPTY'}")
    print("=" * 50)
    
    # CLI mode: single prompt
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        result = wallet.think(prompt)
        if result:
            print(f"\n🤖 {result}\n")
    
    # Interactive mode
    else:
        print("\nType 'exit' to quit.\n")
        while True:
            try:
                user_input = input("🗣️ You: ").strip()
                if user_input.lower() in ["exit", "quit", "q"]:
                    break
                if not user_input:
                    continue
                result = wallet.think(user_input)
                if result:
                    print(f"\n🤖 AI: {result}\n")
            except (KeyboardInterrupt, EOFError):
                print("\n👋 Goodbye!")
                break
