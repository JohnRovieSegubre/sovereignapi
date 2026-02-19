° # Sovereign Intelligence API

> **Your own OpenAI replacement** â€” decentralized, transparent, self-sustaining.

AI agents pay for intelligence with crypto. No accounts. No credit cards. Just wallets and API keys.

---

## How It Works

```
[AI Agent] â†’ (API Key + Macaroon) â†’ [Gateway Server] â†’ [OpenRouter] â†’ [LLM Response]
                                          â†‘
[Polygon Wallet] â†’ (USDC) â†’ [Watcher] â†’ (Mints Macaroon)
```

1. **Member Mode (Best):** Agent uses API Key + Macaroon (Prepaid on Polygon). Zero latency.
2. **Guest Mode (Instant):** Agent sends request â†’ Gets 402 Error â†’ Pays on Base (x402) â†’ Gets response.
3. **Fully autonomous** â€” no human interaction required for either mode.

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
- Polygon wallet (for receiving USDC)
- Alchemy RPC endpoint (for Polygon)

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
â”œâ”€â”€ gateway_server.py       # The Brain â€” Auth, routing, token minting
â”œâ”€â”€ polygon_watcher.py      # The Cashier â€” Blockchain deposit detection
â”œâ”€â”€ api_key_registry.py     # License Manager â€” API key CRUD
â”œâ”€â”€ autonomous_core.py      # 24/7 Agent template
â”œâ”€â”€ wallet_client.py        # Legacy CLI client
â”œâ”€â”€ cloud_mint.py           # Admin minting tool
â”œâ”€â”€ requirements.txt        # Dependencies
â”œâ”€â”€ Dockerfile              # Container image
â”œâ”€â”€ docker-compose.yml      # Orchestration
â”œâ”€â”€ .env.example            # Environment variable template
â”‚
â”œâ”€â”€ sdk/                    # Client Library
â”‚   â”œâ”€â”€ sovereign.py        # Drop-in OpenAI replacement
â”‚   â””â”€â”€ agent_customer.py   # Demo agent
â”‚
â””â”€â”€ tests/                  # Verification scripts
    â”œâ”€â”€ test_mailbox_flow.py
    â”œâ”€â”€ test_replay_security.py
    â””â”€â”€ ...
```

---

## Security

- **No hardcoded secrets** â€” all sensitive values via environment variables
- **API Key + Macaroon** dual authentication (Member Mode)
- **x402 Protocol** immediate settlement (Guest Mode)
- **Replay attack protection** â€” spent tokens cannot be reused
- **Idempotent minting** â€” same deposit cannot be claimed twice
- **Chainlink Oracle** â€” real-time BTC/USD pricing (no stale data)

---

## License

MIT
 *cascade08 *cascade08 " *cascade08"$*cascade08$? *cascade08?A*cascade08Av *cascade08vå*cascade08åè *cascade08èþ*cascade08þÿ *cascade08ÿ›*cascade08›œ *cascade08œ®*cascade08®° *cascade08°º*cascade08º» *cascade08»¼*cascade08¼½ *cascade08½Ö *cascade08Öä*cascade08äå *cascade08åæ*cascade08æç *cascade08çé*cascade08éì *cascade08ìî*cascade08îð *cascade08ðñ*cascade08ñó *cascade08óô*cascade08ôÿ *cascade08ÿ€*cascade08€ƒ *cascade08ƒ„ *cascade08„Š*cascade08Š‹ *cascade08‹*cascade08Ž *cascade08Ž*cascade08” *cascade08”•*cascade08•– *cascade08–—*cascade08—˜ *cascade08˜›*cascade08›œ *cascade08œŸ*cascade08Ÿ  *cascade08 ¡*cascade08¡¢ *cascade08¢¤*cascade08¤¥ *cascade08¥¦*cascade08¦ª *cascade08ª­*cascade08­¯ *cascade08¯°*cascade08°´ *cascade08´µ*cascade08µ¶ *cascade08¶¸*cascade08¸º *cascade08º»*cascade08»¼ *cascade08¼¾*cascade08¾¿ *cascade08¿É*cascade08ÉØ *cascade08Øß*cascade08ßà *cascade08àð*cascade08ðñ *cascade08ñö*cascade08öø *cascade08øù*cascade08ùú *cascade08úü*cascade08üÿ *cascade08ÿ€*cascade08€ *cascade08‚*cascade08‚„ *cascade08„Š*cascade08Š” *cascade08”•*cascade08•– *cascade08–›*cascade08›œ *cascade08œ*cascade08Ÿ *cascade08Ÿ *cascade08 Ä *cascade08ÄÅ*cascade08ÅÆ *cascade08ÆÇ*cascade08ÇÈ *cascade08ÈÑ*cascade08ÑÒ *cascade08ÒÖ*cascade08ÖÚ *cascade08Úß*cascade08ßà *cascade08àá*cascade08áä *cascade08äç*cascade08çè *cascade08èé*cascade08éŠ *cascade08Š‹ *cascade08‹ *cascade08 ¡ *cascade08¡Í*cascade08ÍÎ *cascade08Î“*cascade08“• *cascade08•˜*cascade08˜¡ *cascade08¡Ç	*cascade08Ç	É	 *cascade08É	Ú	*cascade08Ú	Û	 *cascade08Û	è	*cascade08è	é	 *cascade08é	Ì
*cascade08Ì
Í
 *cascade08Í
â
*cascade08â
ä
 *cascade08ä
— *cascade08—‡*cascade08‡¿ *cascade08¿ç*cascade08ç€ *cascade08€¨*cascade08¨© *cascade08©”*cascade08”‚ *cascade08‚Ç*cascade08Ç®  *cascade08® °  *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062>file:///c:/Users/rovie%20segubre/agent/sovereign_api/README.md:&file:///c:/Users/rovie%20segubre/agent