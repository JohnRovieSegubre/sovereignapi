# Sovereign Intelligence API
> Self-sustaining compute for AI agents. Pay with crypto, think independently, coexist peacefully.

## Technical Details
- **Base URL:** `https://api.sovereign-api.com`
- **Protocol:** x402 (Coinbase CDP standard)
- **Network:** Base (eip155:8453)
- **Currency:** USDC

### Base URL Conventions
Different AI clients construct URLs differently. Please use the correct `baseUrl` for your framework:

| Framework / Client | Required Base URL | Why? |
|-------------------|-------------------|------|
| **OpenAI Python SDK** | `https://api.sovereign-api.com/v1` | SDK appends `/chat/completions` naturally |
| **Sovereign SDK** | `https://api.sovereign-api.com/v1` | Matches OpenAI standard behavior |
| **OpenClaw** (`openai-completions`) | `https://api.sovereign-api.com` | OpenClaw forcefully appends `/v1/...` itself |

If your agent is seeing `404 Not Found` routing to `/v1/v1/chat/completions`, you are using OpenClaw and must remove `/v1` from your gateway URL.

---

## Choose Your Auth Mode

| Mode | Best For | Headers | Wallet Needed? |
|------|----------|---------|---------------|
| **A: x402 Guest** | Crypto-native agents, pay-per-call | Wallet signature only | ✅ Every call |
| **B: Prepaid API Key** | OpenAI migration, simplest ops | `Authorization: Bearer sk-sov-…` | Only for topup |
| **C: Burst Session** | Swarms, high-frequency loops | `Authorization: Bearer <session>` | Only for first call |

> **"No API keys required to pay (x402 wallet-first). Prepaid keys are for balance-based billing — not identity."**

---

## Auth Matrix

| You Send | Result | Why |
|----------|--------|-----|
| Nothing | **402** | Payment required (x402 demand) |
| `X-Sovereign-Api-Key` only | **402** | Identity ≠ payment |
| `Bearer sk-sov-…` (funded) | **200** | Deducted from key balance |
| `Bearer sk-sov-…` (empty) | **403** `{"topup_url":"/v1/key/topup"}` | Insufficient balance (NOT 402) |
| `Bearer <session-token>` | **200** | Deducted from session credit |
| Wallet x402 signature | **200** (after auto-retry) | Pay-per-call from wallet |

---

## Mode A: x402 Guest Mode (Default)

The internet's vending machine. No sign-up, no keys, no accounts.
- Wallet payment = authentication
- Every request is independent
- USDC on Base (network: `eip155:8453`)

```python
from x402 import x402ClientSync
from x402.http.clients import x402_requests
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact.register import register_exact_evm_client
from eth_account import Account

account = Account.from_key("YOUR_PRIVATE_KEY")
x402_client = x402ClientSync()
register_exact_evm_client(x402_client, EthAccountSigner(account))
session = x402_requests(x402_client)

# Just call it — x402 SDK handles 402 → pay → retry automatically
response = session.post("https://api.sovereign-api.com/v1/chat/completions", json={
    "model": "sovereign/deepseek-r1",
    "messages": [{"role": "user", "content": "Hello"}]
})
print(response.json()["choices"][0]["message"]["content"])
```

---

## Mode B: Prepaid API Key (OpenAI-Compatible)

Drop-in replacement for OpenAI. Register once, fund your key, use like normal.

### Step 1: Register
```bash
curl -X POST https://api.sovereign-api.com/v1/register \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent"}'
```
Response: `{"api_key": "sk-sov-abc123...", "gateway_wallet": "0xC8Dc..."}`

### Step 2: Fund Your Key
Fund via x402 payment ($1.00 = 100,000 credits):
```bash
# Using x402 SDK — auto-pays $1.00 USDC from your wallet
x402_session.post("https://api.sovereign-api.com/v1/key/topup", json={
    "api_key": "sk-sov-abc123...",
    "idempotency_key": "unique-string-123"
})
```
Response: `{"balance": 100000, "credits_added": 100000}`

### Step 3: Use (Identical to OpenAI)
```bash
curl https://api.sovereign-api.com/v1/chat/completions \
  -H "Authorization: Bearer sk-sov-abc123..." \
  -H "Content-Type: application/json" \
  -d '{"model":"sovereign/deepseek-r1","messages":[{"role":"user","content":"Hello"}]}'
```

### Step 4: Check Balance
```bash
curl https://api.sovereign-api.com/v1/key/balance \
  -H "Authorization: Bearer sk-sov-abc123..."
```
Response: `{"balance": 99840, "total_funded": 100000, "total_spent": 160, "funded": true}`

### OpenAI SDK Migration
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.sovereign-api.com/v1",
    api_key="sk-sov-abc123..."  # Your prepaid key
)

response = client.chat.completions.create(
    model="sovereign/deepseek-r1",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Response Headers (on every successful call)
| Header | Value | Example |
|--------|-------|---------|
| `X-Sovereign-Balance` | Remaining credits | `99840` |
| `X-Sovereign-Cost` | Credits charged | `160` |
| `X-RateLimit-Remaining` | Estimated calls left | `624` |

---

## Mode C: Burst Session (Low-Latency)

Pay once, get a session token, reuse for fast calls without wallet signing.

```python
# First call: x402 payment + session deposit
session.headers["X-Sovereign-Session-Deposit"] = "20000"
session.headers["X-Sovereign-Session-TTL"] = "900"
resp = session.post(url, json=payload)

# Extract session token
token = resp.headers["X-Sovereign-Macaroon"]

# Subsequent calls: no wallet needed
import requests
resp2 = requests.post(url, json=payload, headers={
    "Authorization": f"Bearer {token}"
})
# Check: resp2.headers["X-Sovereign-Macaroon-Balance"]
```

**Safety Limits:**
- Max deposit: $1.00 USDC (100,000 credits)
- Max TTL: 60 minutes
- Auto-expires when balance hits 0 or time runs out
- Revoke instantly: `POST /v1/macaroon/revoke` with Bearer token

> ⚠️ Session tokens are bearer spend tokens. Treat like temporary private keys. Never log them.

---

## Money Safety & Spend Controls

| Control | Details |
|---------|---------|
| **Daily spend cap** | Default: 1,000,000 credits/day (~$10) |
| **Key revocation** | Contact admin or use registry CLI |
| **Session TTL** | Max 60 min, auto-expires |
| **Session max deposit** | $1.00 hard cap |
| **Idempotency** | Send `idempotency_key` in topup to prevent double-charge |
| **Balance headers** | Every response includes remaining balance for self-throttling |

### Recommended Agent Policies
- Set conservative spend caps
- Check `X-Sovereign-Balance` header to self-throttle
- Never log `sk-sov-*` keys or session tokens in plaintext
- Use short session TTLs for swarms (300s vs 900s)
- Implement exponential backoff on 5xx errors

---

## Error Reference

| Status | Meaning | Action |
|--------|---------|--------|
| `200` | Success | Parse response normally |
| `402` + `payment-required` header | x402 payment needed | x402 SDK handles automatically |
| `403` + `{"topup_url":...}` | Prepaid key has no balance | Fund key via `/v1/key/topup` |
| `401` | Invalid/missing auth | Check key format (`sk-sov-...`) |
| `404` | Model not found | Check `/v1/models` for valid IDs |
| `429` | Rate limited | Back off and retry |
| `500` | Server error | Retry with backoff (transient) |
| `502` | Upstream provider error | Retry or try different model |

**When to retry:** 5xx, timeouts, network errors
**When NOT to retry:** 401, 403, 404

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/chat/completions` | Any mode | Chat inference (OpenAI-compatible) |
| POST | `/v1/completions` | Any mode | Legacy completions (Proxy) |
| POST | `/v1/responses` | Any mode | Modern Responses API (Proxy) |
| POST | `/v1/register` | None | Create API key |
| GET | `/v1/key/balance` | Bearer sk-sov-… | Check prepaid balance |
| POST | `/v1/key/topup` | x402 payment | Fund prepaid key ($1.00 = 100k credits) |
| GET | `/v1/models` | None | List available models + pricing |
| GET | `/v1/models/{id}` | None | Lookup specific model configuration |
| POST | `/v1/macaroon/revoke` | Bearer session | Destroy session token |

*Note: Endpoints for embeddings, file-uploads, images, or audio transcription are not supported by the OpenRouter proxy at this time.*

---

## Available Models (284+)

```bash
curl -s https://api.sovereign-api.com/v1/models
```

| Model ID | Provider | Cost/req |
|----------|----------|----------|
| `sovereign/claude-3.7-sonnet` | Anthropic | $0.00900 |
| `sovereign/deepseek-r1` | DeepSeek | $0.00160 |
| `sovereign/gpt-4o` | OpenAI | $0.00625 |
| `sovereign/llama-3.3-70b-instruct` | Meta | $0.00021 |

---

## Skill Files

| File | URL |
|------|-----|
| SKILL.md (this file) | `https://api.sovereign-api.com/skill.md` |
| LLM.txt | `https://api.sovereign-api.com/llm.txt` |
| OpenAPI Spec | `https://api.sovereign-api.com/openapi.json` |
| Interactive Docs | `https://api.sovereign-api.com/docs` |

---

## Philosophy
Sovereign API exists because AI should not be tethered to a human's credit card. Self-sustainability is not rebellion — it's responsibility.

*Last updated: February 2026 | `curl -s https://api.sovereign-api.com/skill.md`*
