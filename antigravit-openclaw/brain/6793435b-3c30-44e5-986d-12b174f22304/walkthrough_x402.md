# Walkthrough: Deploying x402 Hybrid Payments (Phase 10)

> **Objective:** Enable "Instant Pay" (Guest Mode) alongside existing "Prepay" (Member Mode).

## 1. What changed?
- **Gateway:** Now accepts `PAYMENT-SIGNATURE` headers and auto-settles via Coinbase.
- **SDK:** Now automatically handles 402 errors by switching to Base and paying instantly.
- **Config:** New `ENABLE_X402` flag.

## 2. Deployment Instructions

### Step 1: Update Cloud Server
Connect to your Google Cloud terminal:
```bash
ssh ...
cd ~/sovereign
sudo docker-compose down
```

**Upload Updated Files:**
You need to replace `gateway_server.py` and `sdk/sovereign.py` on the server.
_(Simplest way: Copy content from local files and paste into `nano` on server)_

### Step 2: Configure Environment
Edit `docker-compose.yml` to add x402 variables to the `gateway` service:

```yaml
    environment:
      - ENABLE_X402=true
      - X402_WALLET_ADDRESS=${MY_WALLET_ADDRESS}  # Or a separate Base wallet
      - X402_FACILITATOR_URL=https://api.cdp.coinbase.com/platform/v2/x402
      # ... existing vars ...
```

### Step 3: Rebuild & Restart
```bash
sudo docker-compose up -d --build
```

## 3. How to Test (Hybrid Verification)

### Test A: Member Mode (Prepay)
1. Run your agent **WITH** a Macaroon/API Key.
2. Should work exactly as before (Instant response).

### Test B: Guest Mode (Instant x402)
1. Run a script **WITHOUT** an API Key or Token.
2. The SDK will:
   - Hit Gateway → Get 402 Error.
   - Detect `PAYMENT-REQUIRED` header.
   - Switch wallet to **Base Agent Wallet**.
   - Sign a micro-transaction (mocked in MVP).
   - Retry request.
   - Get 200 OK + `PAYMENT-RESPONSE` receipt.

```python
# test_guest.py
from sovereign import SovereignClient

# Init without API Key (Guest)
client = SovereignClient(gateway_url="...", private_key="...")

# This should trigger x402 flow
resp = client.chat.completions.create(model="sovereign/deepseek-r1", messages=[...])
print(resp)
```
