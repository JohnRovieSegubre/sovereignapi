# Sovereign Mint: Complete System Inventory

**Last Updated:** 2026-02-08  
**Wallet Address:** `0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d`

---

## Core System Files

### 1. Gateway & Mint (The Brain)
| File | Purpose | Dependencies |
|:-----|:--------|:-------------|
| [`gateway_server.py`](file:///c:/Users/rovie%20segubre/agent/gateway_server.py) | Main AI Gateway with Sovereign Mint, L402, and Macaroon auth | `fastapi`, `httpx`, `pymacaroons`, `uvicorn` |

**Key Features:**
- Dual authentication (L402 + Bearer Macaroons)
- Token minting via `/v1/admin/mint`
- Token claiming via `/v1/balance/claim`
- Replay attack protection
- OpenRouter integration

---

### 2. Client & Wallet (The Agent)
| File | Purpose | Dependencies |
|:-----|:--------|:-------------|
| [`wallet_client.py`](file:///c:/Users/rovie%20segubre/agent/wallet_client.py) | Unified SovereignWallet class with auto token rotation | `httpx`, `json` |

**Key Methods:**
- `think(prompt)` - Send AI request with automatic token rotation
- `top_up(tx_hash)` - Claim minted tokens from Mailbox
- `save_token()` - Atomic token storage

---

### 3. Blockchain Watcher (The Cashier)
| File | Purpose | Dependencies |
|:-----|:--------|:-------------|
| [`polygon_watcher.py`](file:///c:/Users/rovie%20segubre/agent/polygon_watcher.py) | Monitors Polygon for USDC deposits, triggers minting | `web3`, `requests` |

**Configuration:**
- Wallet: `0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d`
- RPC: Alchemy (`https://polygon-mainnet.g.alchemy.com/...`)
- Rate: 5000 sats per 1 USDC

---

## Configuration & Secrets

### Secure Files (`.agent/secure/`)
| File | Purpose | Format |
|:-----|:--------|:-------|
| `mint_secret.json` | Macaroon signing key + Admin API key | `{"MINT_SECRET": "..."}` |
| `alby_token.json` | Alby Lightning API token | `{"ALBY_ACCESS_TOKEN": "..."}` |
| `openrouter_key.json` | OpenRouter API key | `{"OPENROUTER_API_KEY": "..."}` |

### Data Files (`.agent/data/`)
| File | Purpose | Format |
|:-----|:--------|:-------|
| `mint_history.json` | Tracks minted/spent tokens (idempotency + replay protection) | `{tx_hash: {status, time, ...}}` |
| `wallet.json` | Current Macaroon token storage | `{"access_token": "...", "saved_at": ...}` |

---

## Testing & Utilities

### Scripts (`scripts/`)
| File | Purpose |
|:-----|:--------|
| [`antigravity_monitor.py`](file:///c:/Users/rovie%20segubre/agent/scripts/antigravity_monitor.py) | 24/7 inbox monitor (executes `.md` commands) |
| [`check_balance.py`](file:///c:/Users/rovie%20segubre/agent/scripts/check_balance.py) | Inspect Macaroon token balance |
| [`test_replay_security.py`](file:///c:/Users/rovie%20segubre/agent/scripts/test_replay_security.py) | Automated replay attack verification |
| [`verify_alby.py`](file:///c:/Users/rovie%20segubre/agent/scripts/verify_alby.py) | Test Alby Lightning API connection |
| [`manual_stranger_test.py`](file:///c:/Users/rovie%20segubre/agent/scripts/manual_stranger_test.py) | Manual L402 payment testing |
| [`test_invoice_generation.py`](file:///c:/Users/rovie%20segubre/agent/scripts/test_invoice_generation.py) | Test Lightning invoice generation |
| [`watchdog.py`](file:///c:/Users/rovie%20segubre/agent/scripts/watchdog.py) | Process monitoring utility |

### Batch Files
| File | Purpose |
|:-----|:--------|
| [`START_MONITOR.bat`](file:///c:/Users/rovie%20segubre/agent/START_MONITOR.bat) | Windows launcher for antigravity_monitor |

---

## Integration & Registration

### Moltbook (AI Model Registry)
| File | Purpose |
|:-----|:--------|
| [`Moltbook_Registration.json`](file:///c:/Users/rovie%20segubre/agent/Moltbook_Registration.json) | Service registration payload |
| `post_moltbook.py` | Submit registration to Moltbook |
| `post_and_verify_moltbook.py` | Submit + verify registration |
| `check_moltbook_status.py` | Check registration status |
| `list_moltbook_submolts.py` | List registered submolts |
| `create_submolt.py` | Create new submolt entry |
| `moltbook_explore.py` | Explore Moltbook API |
| `debug_moltbook_raw.py` | Debug Moltbook responses |
| `moltbook_debug.json` | Debug data storage |
| `moltbook_findings.json` | API exploration results |
| `moltbook_report.md` | Moltbook integration report |

---

## Documentation

### Project Docs
| File | Purpose |
|:-----|:--------|
| `README.md` | Project overview |
| `IMPROVEMENT_ANALYSIS.md` | System improvement analysis |
| `refined_prompt.md` | Refined system prompts |

### Artifacts (`.gemini/antigravity/brain/`)
| File | Purpose |
|:-----|:--------|
| `task.md` | Current task checklist |
| `walkthrough.md` | Implementation walkthrough |
| `implementation_plan.md` | Technical implementation plan |
| `wallet_comparison.md` | Wallet architecture comparison |
| `system_audit_report.md` | Security audit findings |

---

## System Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    SOVEREIGN MINT SYSTEM                     │
└─────────────────────────────────────────────────────────────┘

[User] ──USDC──> [Polygon Blockchain]
                        │
                        ▼
              [polygon_watcher.py] ◄──web3──► Alchemy RPC
                        │
                        │ POST /v1/admin/mint
                        ▼
              [gateway_server.py]
                        │
                        ├──> PENDING_CLAIMS{} (Mailbox)
                        │
[Agent] ──top_up()──> POST /v1/balance/claim
                        │
                        ▼
              [wallet_client.py]
                        │
                        ├──> wallet.json (Token Storage)
                        │
              ──think()──> POST /v1/chat/completions
                        │
                        ▼
              [OpenRouter] ──> [DeepSeek-R1 / GPT-4o / Llama]
```

---

## Dependency Summary

### Python Packages
```
fastapi
uvicorn
httpx
pymacaroons
web3
requests
```

### External Services
- **Alchemy** - Polygon RPC endpoint
- **Alby** - Lightning Network payments
- **OpenRouter** - AI model routing
- **Polygon** - USDC deposits

---

## Security Model

| Layer | Protection |
|:------|:-----------|
| **Admin Mint** | IP Whitelist (localhost) + Admin Key |
| **Token Replay** | Used token blacklist in `mint_history.json` |
| **Token Rotation** | Automatic "change" token after each spend |
| **Idempotency** | Deposit tx_hash prevents double-minting |
| **Mailbox Claims** | One-time token claiming (pop from dict) |

---

## Next Steps

- [ ] Test end-to-end Polygon deposit flow
- [ ] Deploy to production (set `ENVIRONMENT=PRODUCTION`)
- [ ] Register on Moltbook
- [ ] Add auto-sweep (Proxy Wallet → Cold Storage)
