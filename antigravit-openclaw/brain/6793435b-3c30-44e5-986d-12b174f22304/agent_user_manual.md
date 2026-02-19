# Sovereign Intelligence API — Agent User Manual

> **For AI Agents and Their Developers**  
> *The alternative to OpenAI that you own and control.*

---

## Quick Start (30 seconds)

```python
from sovereign import SovereignClient

client = SovereignClient(
    api_key="sk-sov-xxx",           # Your License (get one below)
    private_key="0x..."              # Your Polygon Wallet (for auto-pay)
)

# Fully Transparent Model Selection
response = client.chat.completions.create(
    model="sovereign/deepseek-r1",  # Explicit backend provider
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response["choices"][0]["message"]["content"])
```

---

## Models Available

We believe in full transparency. You always know exactly which AI brain is processing your data.

| Sovereign Model | Backend Provider | Backend Model | Price (sats) |
|:----------------|:-----------------|:--------------|:-------------|
| `sovereign/deepseek-r1` | OpenRouter | `deepseek/deepseek-r1` | 5 |
| `sovereign/llama3-70b` | OpenRouter | `meta-llama/llama-3.3-70b-instruct` | 25 |
| `sovereign/gpt4o` | OpenRouter | `openai/gpt-4o` | 50 |

---

## Advanced: Manual Token Management

If you prefer to manage Macaroons yourself:

```python
# Get a token manually
client.set_token("MDA0N...")

# Check fuel status
print(client.get_fuel_level())  # "LOADED" or "EMPTY"

# Transfer fuel to another agent
other_agent_token = client.token  # Send this string
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|:--------|:------|:----|
| `401 Invalid API Key` | Wrong/missing key | Check `SOVEREIGN_API_KEY` |
| `402` loop forever | Wallet has no USDC | Fund your Polygon wallet |
| `Timeout on claim` | Watcher is offline | Contact Gateway operator |
| `403 Spent Token` | Using old Macaroon | Let SDK rotate automatically |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                  YOUR AI AGENT                      │
│  ┌─────────────────────────────────────────────────┤
│  │  SovereignClient (SDK)                          │
│  │   • API Key (Identity)                          │
│  │   • Macaroon (Fuel)                             │
│  │   • Auto-Pay (Self-Refuel)                      │
└──┴──────────────────┬──────────────────────────────┘
                      │
         ┌────────────▼────────────┐
         │    Gateway Server       │
         │  • Validates API Key    │
         │  • Checks Macaroon      │
         │  • Routes to LLM        │
         │  • Returns New Token    │
         └────────────┬────────────┘
                      │
         ┌────────────▼────────────┐
         │   Polygon Blockchain    │
         │  (USDC Payments)        │
         └─────────────────────────┘
```

---

## Getting Your API Key

1. Contact the Gateway operator
2. They will run: `python api_key_registry.py create "YourAgentName"`
3. You receive: `sk-sov-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
4. Store it securely (like an OpenAI key)

---

*This is your OpenAI replacement. You own the infrastructure.*
