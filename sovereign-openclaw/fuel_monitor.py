"""
Fuel Monitor — Tracks macaroon balance and auto-refuels when low.
"""

import os
import json
import time
import logging
from pathlib import Path

logger = logging.getLogger("FuelMonitor")


class FuelMonitor:
    LOW_FUEL_THRESHOLD = 50  # sats — trigger refuel below this
    REFUEL_AMOUNT_USD = 1.0  # USDC per refuel

    def __init__(self, sdk_client, brain_dir="brain"):
        self.client = sdk_client
        self.brain_dir = Path(brain_dir)
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self.fuel_file = self.brain_dir / "fuel.json"
        self.state = self._load_state()

    def _load_state(self):
        if self.fuel_file.exists():
            try:
                with open(self.fuel_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "total_refuels": 0,
            "total_spent_usd": 0.0,
            "last_refuel_time": None,
            "last_known_balance": 0
        }

    def _save_state(self):
        with open(self.fuel_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def get_balance(self):
        """Read balance from the current macaroon token."""
        balance = self.client.get_balance_estimate()
        if balance >= 0:
            self.state["last_known_balance"] = balance
            self._save_state()
        return balance

    def is_low(self):
        balance = self.get_balance()
        if balance < 0:
            # Unknown balance (no token or parse error)
            return not self.client.token
        return balance < self.LOW_FUEL_THRESHOLD

    def refuel(self):
        """Send USDC to gateway and claim a new macaroon."""
        if self.client.mock_mode:
            logger.info("🎭 [MOCK] Simulating refuel")
            return True

        if not self.client.private_key:
            logger.error("❌ Cannot refuel: no private key configured")
            return False

        try:
            logger.info(f"⛽ Refueling: sending ${self.REFUEL_AMOUNT_USD} USDC...")
            tx_hash = self.client._send_usdc(self.REFUEL_AMOUNT_USD)
            logger.info(f"📬 Claiming macaroon for tx: {tx_hash[:16]}...")
            new_token = self.client._claim_macaroon(tx_hash)
            self.client.token = new_token

            self.state["total_refuels"] += 1
            self.state["total_spent_usd"] += self.REFUEL_AMOUNT_USD
            self.state["last_refuel_time"] = time.time()
            self.state["last_known_balance"] = self.get_balance()
            self._save_state()

            logger.info(f"✅ Refueled! Total refuels: {self.state['total_refuels']}")
            return True

        except Exception as e:
            logger.error(f"❌ Refuel failed: {e}")
            return False

    def get_stats(self):
        return {
            "balance_sats": self.state["last_known_balance"],
            "total_refuels": self.state["total_refuels"],
            "total_spent_usd": self.state["total_spent_usd"],
            "has_token": bool(self.client.token),
            "is_low": self.is_low()
        }
