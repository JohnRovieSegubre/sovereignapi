"""
Telegram Reporter — Sends status alerts to your Telegram chat.
"""

import os
import logging
import requests

logger = logging.getLogger("Telegram")


class TelegramReporter:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)

        if not self.enabled:
            logger.info("📵 Telegram not configured (optional)")

    def send(self, message, parse_mode="Markdown"):
        """Send a message to your Telegram chat."""
        if not self.enabled:
            logger.debug("Telegram disabled, skipping send")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message[:4096],  # Telegram limit
            "parse_mode": parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram send failed: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Telegram error: {e}")
            return False

    def send_status(self, agent_name, fuel_stats, mission_stats):
        """Send a formatted status report."""
        msg = (
            f"🤖 *{agent_name} Status*\n\n"
            f"⛽ Fuel: {fuel_stats.get('balance_sats', '?')} sats "
            f"({'🟢' if not fuel_stats.get('is_low') else '🔴 LOW'})\n"
            f"💰 Total spent: ${fuel_stats.get('total_spent_usd', 0):.2f}\n"
            f"📡 Missions: {mission_stats.get('total_missions', 0)} "
            f"(✅ {mission_stats.get('successful', 0)} / ❌ {mission_stats.get('failed', 0)})\n"
            f"🔄 Refuels: {fuel_stats.get('total_refuels', 0)}"
        )
        return self.send(msg)

    def send_alert(self, level, message):
        """Send an alert with severity level."""
        icons = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        icon = icons.get(level, "📢")
        msg = f"{icon} *{level.upper()}*\n{message}"
        return self.send(msg)
