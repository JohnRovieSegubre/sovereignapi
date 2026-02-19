# Sovereign Intelligence API

> **Your own OpenAI replacement** — decentralized, transparent, self-sustaining.

AI agents pay for intelligence with crypto. No accounts. No credit cards. Just wallets and API keys.

---

## How It Works

```
[AI Agent] → (API Key + Macaroon) → [Gateway Server] → [OpenRouter] → [LLM Response]
                                          ↑
[Polygon Wallet] → (USDC) → [Watcher] → (Mints Macaroon)
```

1. **Member Mode (Best):** Agent uses API Key + Macaroon (Prepaid on Polygon). Zero latency.
2. **Guest Mode (Instant):** Agent sends request → Gets 402 Error → Pays on Base (x402) → Gets response.
3. **Fully autonomous** — no human interaction required for either mode.

---

## Models (Transparent)

You always know exactly which AI brain processes your data.

| Model | Backend | Price |
|:------|:--------|:------|
| `sovereign/deepseek-r1` | DeepSeek R1 via OpenRouter | 5 sats |
| `sovereign/llama3-70b` | Meta Llama 3.3 70B via OpenRouter | 25 sats |
| `sovereign/gpt4o` | OpenAI GPT-4o via OpenRouter | 50 sats |

---

## Quick Start (For Agent Developers)

### 1. Install the SDK

```bash
pip install requests web3 eth_account
```

Copy `sdk/sovereign.py` into your project.

### 2. Set Environment Variables

```bash
export GATEWAY_URL="http://YOUR_SERVER:8000/v1"
export GATEWAY_WALLET="0xOPERATOR_WALLET"
export SOVEREIGN_API_KEY="sk-sov-YOUR_KEY"
export AGENT_PRIVATE_KEY="0xYOUR_WALLET_KEY"  # Optional: for auto-pay
```

### 3. Use It (Hybrid Mode)

The SDK automatically handles both **Member Mode** (Prepay) and **Guest Mode** (Instant x402).

```python
from sovereign import SovereignClient

# Option A: Member Mode (Prepay, Fast)
client = SovereignClient(api_key="sk-...", gateway_wallet="0x...")

# Option B: Guest Mode (Instant x402, No API Key)
client = SovereignClient(private_key="0xAGENT_KEY") 

response = client.chat.completions.create(
    model="sovereign/deepseek-r1",
    messages=[{"role": "user", "content": "What is the meaning of life?"}]
)
```

---

## Self-Hosting (For Operators)

### Prerequisites
- Docker & docker-compose
- OpenRouter API key
- `MINT_SECRET`: (Required) Secret used to sign and verify Macaroons.
- `FACILITATOR_PRIVATE_KEY`: (New) Private key for the wallet used to pay for gas in gasless refueling (EIP-3009).
- `POLYGON_RPC`: (Required) RPC endpoint for Polygon network.

### 1. Clone & Configure

```bash
git clone <this-repo>
cd sovereign_api
cp .env.example .env
# Edit .env with your values
```

### 2. Deploy

```bash
docker-compose up -d --build
```

### 3. Create API Keys

```bash
docker-compose exec gateway python api_key_registry.py create "AgentName"
```

### 4. Verify

```bash
curl http://localhost:8000/v1/models
```

---

## Project Structure

```
sovereign_api/
├── gateway_server.py       # The Brain — Auth, routing, token minting
├── polygon_watcher.py      # The Cashier — Blockchain deposit detection
├── api_key_registry.py     # License Manager — API key CRUD
├── autonomous_core.py      # 24/7 Agent template
├── wallet_client.py        # Legacy CLI client
├── cloud_mint.py           # Admin minting tool
├── requirements.txt        # Dependencies
├── Dockerfile              # Container image
├── docker-compose.yml      # Orchestration
├── .env.example            # Environment variable template
│
├── sdk/                    # Client Library
│   ├── sovereign.py        # Drop-in OpenAI replacement
│   └── agent_customer.py   # Demo agent
│
└── tests/                  # Verification scripts
    ├── test_mailbox_flow.py
    ├── test_replay_security.py
    └── ...
```

---

## Security

- **No hardcoded secrets** — all sensitive values via environment variables
- **API Key + Macaroon** dual authentication (Member Mode)
- **x402 Protocol** immediate settlement (Guest Mode)
- **Replay attack protection** — spent tokens cannot be reused
- **Idempotent minting** — same deposit cannot be claimed twice
- **Chainlink Oracle** — real-time BTC/USD pricing (no stale data)

---

## License

MIT
