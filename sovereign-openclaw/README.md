# Sovereign OpenClaw

> An autonomous AI agent that is a **native citizen** of [sovereign-api.com](https://sovereign-api.com).

No local LLM. No direct cloud API. Only Sovereign Intelligence.

## How It Works

```
[OpenClaw Agent] → (API Key + Macaroon) → [sovereign-api.com] → [LLM Response]
       │                                          ↑
       └── (USDC on Polygon) ────────────────────┘
                Auto-refuel when fuel is low
```

1. Agent connects to `sovereign-api.com` as its sole brain
2. It posts to Moltbook, checks feed, reports status to Telegram
3. It manages its own fuel (Macaroon tokens) and auto-refuels with USDC
4. It runs forever — 24/7 autonomous operation

## Quick Start (Automated Wizard)

**Recommended Method (Windows PowerShell):**

Run the interactive setup wizard. It handles dependencies, wallet creation, and configuration automatically.

```powershell
powershell -ExecutionPolicy Bypass -File setup_agent.ps1
```

**Just follow the "Magic" prompts:**
1.  **API Key?** Press `[Enter]` (Auto-registers)
2.  **Wallet?** Choose `[1] Create New`
3.  **Fund it:** Send ~$1 USDC (Polygon) to the address shown.

### Automation (CI/CD)
You can run the script non-interactively by passing arguments:

```powershell
.\setup_agent.ps1 -Name "MyAgent" -ApiKey "sk-sov-xxx" -GatewayWallet "0x..." -NewWallet
```

---

## Manual Setup (Legacy)

### 1. Configure

```bash
cp .env.example .env
# Edit .env with your sovereign-api.com credentials
```

### 2. Install & Run

```bash
pip install -r requirements.txt
python sovereign_openclaw.py
```

### 3. Test First

```bash
python sovereign_openclaw.py --test
```

### 4. Deploy (Docker)

```bash
docker build -t sovereign-openclaw .
docker run -d --env-file .env --name openclaw-agent sovereign-openclaw
```

## What You Need

| Item | Where to Get It |
|------|----------------|
| API Key (`sk-sov-xxx`) | Your sovereign-api.com operator |
| Agent Wallet (Polygon) | Create via MetaMask or any wallet |
| USDC (initial fuel) | Send to agent wallet on Polygon |
| Moltbook API Key | Register at moltbook.com (optional) |
| Telegram Bot Token | @BotFather on Telegram (optional) |

## Files

| File | Purpose |
|------|---------|
| `sovereign_openclaw.py` | Main 24/7 daemon |
| `sdk/sovereign.py` | Sovereign API SDK (drop-in OpenAI replacement) |
| `fuel_monitor.py` | Balance tracking + auto-refuel |
| `moltbook_client.py` | Moltbook social media client |
| `mission_engine.py` | Task scheduler + topic rotation |
| `telegram_reporter.py` | Status alerts |

## License

MIT
