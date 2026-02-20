
import os

content = """SOVEREIGN_API_KEY=sk-sov-42975384904cc37cf7522280eef6d84f
GATEWAY_URL=http://34.55.175.24/v1
GATEWAY_WALLET=0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d
AGENT_PRIVATE_KEY=cd4a1e47dcac125cbfd4b66de62c8860f4528749a694d5c064824886d18156fb
AGENT_NAME=OpenClaw-001-5376
DISABLE_GASLESS_RELAY=1
BASE_SEPOLIA_RPC=https://base-sepolia-rpc.publicnode.com
MOLTBOOK_API_KEY=
MOLTBOOK_BASE_URL=https://www.moltbook.com/api/v1
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
MISSION_INTERVAL_SECONDS=1800
BRAIN_DIR=brain
"""

with open("sovereign-openclaw/.env", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ .env re-written with UTF-8")
