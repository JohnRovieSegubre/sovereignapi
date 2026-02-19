Ë¨import time
import httpx
import os
import hashlib
import json
import uvicorn
import socket
import sys
import secrets
import requests
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
import base64
from pymacaroons import Macaroon, Verifier
from api_key_registry import validate_key, get_agent_name, increment_usage

app = FastAPI(title="Sovereign AI Gateway (Phase 7: Decoupled Identity + Fuel)")

# --- CONFIGURATION ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "DEVELOPMENT")
MAX_TOKENS_CAP = 1024
SITE_URL = os.getenv("SITE_URL", "https://indecomposable-adelia-impolitely.ngrok-free.dev")  # UPDATE THIS IF NGROK CHANGES
SITE_TITLE = "Sovereign Shadow Node"

# Load Secrets
SECURE_DIR = Path(__file__).parent / ".agent" / "secure"
DATA_DIR = Path(__file__).parent / ".agent" / "data"
ALBY_TOKEN_FILE = SECURE_DIR / "alby_token.json"
OPENROUTER_KEY_FILE = SECURE_DIR / "openrouter_key.json"
MINT_SECRET_FILE = SECURE_DIR / "mint_secret.json"

ALBY_ACCESS_TOKEN = None
OPENROUTER_API_KEY = None
MINT_SECRET = None  # MUST be set via env var or secure file

# Default values (overridden by Env Vars or Files)
ALBY_ACCESS_TOKEN = os.getenv("ALBY_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MINT_SECRET = os.getenv("MINT_SECRET")

# --- x402 CONFIGURATION ---
X402_FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "https://api.cdp.coinbase.com/platform/v2/x402")
X402_WALLET_ADDRESS = os.getenv("X402_WALLET_ADDRESS") 
ENABLE_X402 = os.getenv("ENABLE_X402", "true").lower() == "true"

try:
    if not ALBY_ACCESS_TOKEN and ALBY_TOKEN_FILE.exists():
        with open(ALBY_TOKEN_FILE, 'r') as f:
            ALBY_ACCESS_TOKEN = json.load(f).get("ALBY_ACCESS_TOKEN")
            
    if not OPENROUTER_API_KEY and OPENROUTER_KEY_FILE.exists():
        with open(OPENROUTER_KEY_FILE, 'r') as f:
            OPENROUTER_API_KEY = json.load(f).get("OPENROUTER_API_KEY")
            
    if not MINT_SECRET and MINT_SECRET_FILE.exists():
        with open(MINT_SECRET_FILE, 'r') as f:
            MINT_SECRET = json.load(f).get("MINT_SECRET")
            
except Exception as e:
    print(f"[ERROR] Failed to load secrets from files: {e}")

# Validate
if not MINT_SECRET:
    print("[CRITICAL] MINT_SECRET is missing! Admin and Token features will fail.")


MODEL_ROUTER = {
    # 50% DISCOUNT (Fair Market Pricing)
    "sovereign/llama3-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.3-70b-instruct", "price_sats": 25},
    "sovereign/deepseek-r1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-r1", "price_sats": 5},
    "sovereign/gpt4o": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o", "price_sats": 50}
}

INVOICE_DB = {}

# --- PERSISTENT PENDING CLAIMS (Mailbox) ---
PENDING_CLAIMS_FILE = DATA_DIR / "pending_claims.json"

def load_pending_claims():
    """Load pending claims from disk (crash recovery)."""
    if PENDING_CLAIMS_FILE.exists():
        try:
            with open(PENDING_CLAIMS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_pending_claims():
    """Persist pending claims to disk."""
    PENDING_CLAIMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_CLAIMS_FILE, 'w') as f:
        json.dump(PENDING_CLAIMS, f)

PENDING_CLAIMS = load_pending_claims()  # Load on startup


# --- CLASS: THE SOVEREIGN MINT (SECURED) ---
class SovereignMint:
    def __init__(self, secret, location):
        self.secret = secret
        self.location = location
        self.history_file = DATA_DIR / "mint_history.json"
        self.history = self._load_history()

    def _load_history(self):
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_history(self):
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f)

    def mint_token(self, amount_sats: int, identifier: str):
        """Creates a FRESH token from a deposit (Idempotent)."""
        # Normalize identifier to string
        if isinstance(identifier, bytes):
            identifier = identifier.decode('utf-8')

        # 1. Check if deposit ID was already used
        if identifier in self.history:
            raise ValueError(f"Deposit {identifier} already claimed!")

        # 2. Mint Token
        m = Macaroon(location=self.location, identifier=identifier, key=self.secret)
        m.add_first_party_caveat(f"balance = {amount_sats}")

        # 3. Save History (Mark as minted)
        self.history[identifier] = {"amount": amount_sats, "status": "minted", "time": time.time()}
        self._save_history()

        return m.serialize()

    def verify_and_spend(self, token_str: str, cost: int):
        """Verifies token, deducts cost, marks old token as SPENT, returns NEW token."""
        try:
            m = Macaroon.deserialize(token_str)
            
            # Normalize identifier to string for history check
            m_id = m.identifier
            if isinstance(m_id, bytes):
                m_id = m_id.decode('utf-8')

            # --- [SECURITY PATCH: REPLAY PROTECTION] ---
            # Check if this token identifier is in our "Used" list
            token_record = self.history.get(m_id, {})
            if token_record.get("status") == "spent":
                return False, None, "Token Already Spent (Replay Detected)"
            # -------------------------------------------

            # Extract Balance (Needed for verification satisfaction)
            current_balance = 0
            for caveat in m.caveats:
                if caveat.caveat_id.startswith("balance = "):
                    current_balance = int(caveat.caveat_id.split(" = ")[1])

            v = Verifier()
            # SATISFY CAVEAT: We must tell the verifier we accept this balance
            v.satisfy_exact(f"balance = {current_balance}")
            
            # Verify the signature
            if not v.verify(m, self.secret): 
                return False, None, "Invalid Signature"

            if current_balance < cost:
                return False, None, "Insufficient Funds"

            # --- [STATE UPDATE] ---
            # Mark the OLD token as SPENT so it cannot be used again
            self.history[m_id] = {
                "status": "spent", 
                "time": time.time(),
                "prev_balance": current_balance
            }
            self._save_history()
            # ----------------------

            # MINT REPLACEMENT TOKEN (The "Change")
            new_balance = current_balance - cost
            # We use a random identifier for change tokens to avoid collision with deposits
            new_id = f"change_{secrets.token_hex(8)}"

            new_m = Macaroon(location=self.location, identifier=new_id, key=self.secret)
            new_m.add_first_party_caveat(f"balance = {new_balance}")

            return True, new_m.serialize(), "Success"
        except Exception as e:
            return False, None, f"Token Error: {e}"


MINT = SovereignMint(MINT_SECRET, SITE_URL)


# --- ALBY LOGIC ---
async def generate_real_invoice(price_sats: int, description: str):
    if not ALBY_ACCESS_TOKEN:
        return "mock_hash", "lnbc_mock_invoice_missing_token"
    url = "https://api.getalby.com/invoices"
    headers = {"Authorization": f"Bearer {ALBY_ACCESS_TOKEN}"}
    payload = {"amount": price_sats, "description": description}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                data = response.json()
                p_hash = data['payment_hash']
                INVOICE_DB[p_hash] = {"status": "pending"}
                return p_hash, data['payment_request']
        except Exception as e:
            print(f"[ALBY EXCEPTION] {e}")
    return None, None


async def check_alby_payment_status(payment_hash: str):
    if not ALBY_ACCESS_TOKEN:
        return False
    url = f"https://api.getalby.com/invoices/{payment_hash}"
    headers = {"Authorization": f"Bearer {ALBY_ACCESS_TOKEN}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("settled", False)
        except Exception:
            pass
    return False



# --- x402 HELPER FUNCTIONS ---
def verify_x402_payment(signature: str):
    """
    Verifies and settles an x402 payment via the Coinbase Facilitator.
    Returns the receipt if successful, None otherwise.
    """
    try:
        # 1. Verify
        print(f"[x402] Verifying Signature: {signature[:10]}...")
        headers = {}
        cdp_key = os.getenv("X402_CDP_API_KEY")
        if cdp_key:
            headers["Authorization"] = f"Bearer {cdp_key}"
            
        verify_resp = requests.post(
            f"{X402_FACILITATOR_URL}/verify",
            json={"signature": signature},
            headers=headers,
            timeout=5
        )
        if verify_resp.status_code != 200:
            print(f"[x402] Verification failed: {verify_resp.text}")
            return None
            
        verify_data = verify_resp.json()
        payment_id = verify_data.get("paymentId")
        
        # 2. Settle (Immediate Capture)
        print(f"[x402] Settling Payment: {payment_id}...")
        settle_resp = requests.post(
            f"{X402_FACILITATOR_URL}/settle",
            json={"paymentId": payment_id},
            headers=headers,
            timeout=5
        )
        
        if settle_resp.status_code == 200:
            print(f"[x402] Settlement Success!")
            return settle_resp.json() # Receipt
            
        print(f"[x402] Settlement failed: {settle_resp.text}")
        return None
        
    except Exception as e:
        print(f"[x402] Error: {e}")
        return None

def get_x402_headers(price_sats: int):
    """Returns the PAYMENT-REQUIRED headers for a 402 response."""
    # Convert sats to USDC (approximate: 1 sat ~= $0.0006 at $60k BTC, but let's use fixed 1 cent for MVP)
    # Ideally fetch real price, but for x402 simplicity we start with fixed tier.
    price_usdc = "0.01"
    wallet = X402_WALLET_ADDRESS or os.getenv("MY_WALLET_ADDRESS")
    if not wallet:
        wallet = "0x0000000000000000000000000000000000000000" # Placeholder if not set
    
    payment_request = {
        "x402Version": "2.0",
        "accepts": [
            {
                "scheme": "exact",
                "network": "base-mainnet",
                "price": price_usdc,
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", # USDC on Base
                "payTo": wallet
            },
            {
                "scheme": "exact",
                "network": "base-sepolia", 
                "price": price_usdc,
                "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e", # USDC on Base Sepolia
                "payTo": wallet
            }
        ]
    }
    
    encoded_json = base64.b64encode(json.dumps(payment_request).encode()).decode()
    return {"PAYMENT-REQUIRED": encoded_json}


# --- MIDDLEWARE: TRI-BRID AUTH (Phase 10: x402 + Macaroon + Key) ---
async def verify_payment_header(request: Request, cost_sats: int):
    """
    Tri-brid authentication check:
    1. x402 (PAYMENT-SIGNATURE) - Instant Guest Access
    2. API Key (X-Sovereign-Api-Key) - Identity/License
    3. Macaroon/L402 (Authorization) - Prepay Fuel
    
    Returns:
        (is_valid, auth_data)
        auth_data can be:
          - {"type": "macaroon", "new_token": ...}
          - {"type": "x402", "receipt": ...}
          - {"status": 401/402, "error": ...} (Failure)
    """
    
    # === CHECK 0: x402 SIGNATURE (INSTANT GUEST MODE) ===
    # This comes first to allow keyless access if enabled
    x402_sig = request.headers.get("PAYMENT-SIGNATURE")
    if ENABLE_X402 and x402_sig:
        receipt = verify_x402_payment(x402_sig)
        if receipt:
            return True, {"type": "x402", "receipt": receipt}
        # If sig exists but fails, return 402 to prompt retry
        return False, {"status": 402, "error": "Invalid x402 Signature"}

    # === CHECK 1: API KEY (IDENTITY) ===
    api_key = request.headers.get("X-Sovereign-Api-Key")
    
    # Allow legacy mode (no API key required) in development
    if ENVIRONMENT == "PRODUCTION" or api_key:
        if not api_key:
            return False, {"status": 401, "error": "Missing API Key (X-Sovereign-Api-Key header)"}
        
        if not validate_key(api_key):
            return False, {"status": 401, "error": "Invalid or revoked API Key"}
        
        # Log usage
        increment_usage(api_key)
        agent_name = get_agent_name(api_key)
        print(f"üîë [AUTH] Agent '{agent_name}' authenticated")
    
    # === CHECK 2: FUEL (MACAROON OR L402) ===
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False, "Missing Authorization"

    # CASE A: BEARER TOKEN (Macaroon)
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        valid, new_token, msg = MINT.verify_and_spend(token, cost_sats)
        if valid:
            return True, {"type": "macaroon", "new_token": new_token}
        return False, msg

    # CASE B: LIGHTNING (L402)
    if auth_header.startswith("L402 "):
        try:
            token = auth_header.split(" ")[1]
            preimage, _ = token.split(":")

            # Dev Backdoor
            if preimage == "secret_proof_of_payment" and ENVIRONMENT != "PRODUCTION":
                return True, {"type": "lightning"}

            # Real Check
            preimage_bytes = bytes.fromhex(preimage)
            calculated_hash = hashlib.sha256(preimage_bytes).hexdigest()

            if await check_alby_payment_status(calculated_hash):
                return True, {"type": "lightning"}
            return False, "Lightning Payment Not Settled"
        except:
            return False, "Invalid L402 Format"

    return False, "Unknown Auth Type"


# --- OPENROUTER FORWARDING ---
async def forward_to_openrouter(payload: dict, route_config: dict):
    if not OPENROUTER_API_KEY:
        return JSONResponse(status_code=500, content={"error": "No API Key"})
    backend_payload = payload.copy()
    backend_payload["model"] = route_config["backend_model"]
    if "max_tokens" not in backend_payload or backend_payload["max_tokens"] > MAX_TOKENS_CAP:
        backend_payload["max_tokens"] = MAX_TOKENS_CAP

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_TITLE
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                route_config["backend_url"],
                json=backend_payload,
                headers=headers,
                timeout=120.0
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=response.headers.get("content-type")
            )
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": f"Upstream Error: {e}"})


# --- ENDPOINTS ---
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    requested_model = body.get("model")
    if requested_model not in MODEL_ROUTER:
        raise HTTPException(status_code=404, detail="Model not found")
    route_config = MODEL_ROUTER[requested_model]

    # Verify Payment
    is_valid, auth_data = await verify_payment_header(request, route_config["price_sats"])

    if not is_valid:
        # === 401: API KEY FAILURE ===
        if isinstance(auth_data, dict) and auth_data.get("status") == 401:
            return JSONResponse(
                status_code=401,
                content={"error": auth_data.get("error", "Invalid API Key")},
                headers={"WWW-Authenticate": "Sovereign-Api-Key"}
            )
        
        # === 403: REPLAY ATTACK / TOKEN SPENT ===
        if isinstance(auth_data, str) and "Spent" in auth_data:
            return JSONResponse(status_code=403, content={"error": auth_data})
        
        # === 402: INSUFFICIENT FUNDS ===
        if isinstance(auth_data, str) and "Funds" in auth_data:
            return JSONResponse(status_code=402, content={"error": "Insufficient Funds in Token"})

        # === 402: x402 / PAYMENT REQUIRED ===
        # If enabled, prefer x402 headers over L402 invoice
        if ENABLE_X402:
            x402_headers = get_x402_headers(route_config["price_sats"])
            return JSONResponse(
                status_code=402,
                content={}, # Empty body as per spec
                headers=x402_headers
            )

        # === 402: LEGACY L402 INVOICE (If x402 disabled) ===
        p_hash, invoice = await generate_real_invoice(route_config["price_sats"], f"Sovereign: {requested_model}")
        return JSONResponse(
            status_code=402,
            content={"error": "Payment Required", "debug_msg": str(auth_data), "invoice": invoice, "price_sats": route_config["price_sats"]},
            headers={"WWW-Authenticate": "L402 token", "X-L402-Invoice": invoice}
        )


    # Execute
    response = await forward_to_openrouter(body, route_config)

    # TOKEN ROTATION: Return the NEW balance token
    if isinstance(auth_data, dict) and auth_data.get("type") == "macaroon":
        response.headers["X-Sovereign-Balance-Token"] = auth_data["new_token"]

    # x402 RECEIPT: Return the payment receipt
    if isinstance(auth_data, dict) and auth_data.get("type") == "x402":
        receipt_json = json.dumps(auth_data["receipt"])
        encoded_receipt = base64.b64encode(receipt_json.encode()).decode()
        response.headers["PAYMENT-RESPONSE"] = encoded_receipt

    return response


@app.get("/v1/models")
async def list_models():
    return {"data": [{"id": k, "price": v["price_sats"]} for k, v in MODEL_ROUTER.items()]}


# --- ADMIN MINT (The Stablecoin Hook) ---
@app.post("/v1/admin/mint")
async def admin_mint(request: Request):
    # REMOVED IP CHECK to allow Docker Container communication (Security via X-Admin-Key)
    
    # 2. Key Check
    auth = request.headers.get("X-Admin-Key")
    if auth != MINT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid Admin Key")

    body = await request.json()
    try:
        # Mint logic checks for Idempotency internally
        token = MINT.mint_token(body['amount_sats'], body['identifier'])
        
        # Store in Mailbox for async claiming
        PENDING_CLAIMS[body['identifier']] = token
        save_pending_claims()  # Persist to disk
        print(f"üì¨ [MAILBOX] Token stored for {body['identifier'][:10]}...")
        
        return {"access_token": token, "status": "minted_and_stored", "balance": body['amount_sats']}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))  # Conflict (Double Spend)


@app.post("/v1/balance/claim")
async def claim_token(request: Request):
    """
    Agents call this endpoint to pick up their minted tokens using the tx_hash.
    This enables fully autonomous funding without human intervention.
    """
    body = await request.json()
    tx_hash = body.get('tx_hash')
    
    if not tx_hash:
        raise HTTPException(status_code=400, detail="tx_hash required")
    
    if tx_hash in PENDING_CLAIMS:
        token = PENDING_CLAIMS.pop(tx_hash)  # Retrieve and Delete (one-time claim)
        save_pending_claims()  # Persist to disk
        print(f"üì¨ [MAILBOX] Token claimed for {tx_hash[:10]}...")
        return {"access_token": token, "status": "claimed"}
    
    # Check if already minted but claimed (or not yet processed)
    if tx_hash in MINT.history:
        return JSONResponse(status_code=410, content={"error": "Token already claimed"})
    
    return JSONResponse(status_code=404, content={"error": "Token not ready. Deposit may still be processing."})


if __name__ == "__main__":
    PORT = 8000
    
    # Idempotency Check
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', PORT))
    sock.close()
    
    if result == 0:
        try:
             resp = requests.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=2.0)
             if resp.status_code == 200:
                 print(f"[INFO] Gateway already running on {PORT}. Stop it before restarting.")
                 sys.exit(0)
        except:
             pass

    print(f"Sovereign Mint (Universal Mode) starting on {PORT}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    except Exception as e:
        if "10048" in str(e):
            print(f"[CRITICAL] Port {PORT} is STUCK. Run: Stop-Process -Id (Get-NetTCPConnection -LocalPort {PORT}).OwningProcess -Force")
            sys.exit(1)
        raise e
î *cascade08î£*cascade08£‹
 *cascade08‹
‚*cascade08‚òF *cascade08òFÉe*cascade08ÉeÁà *cascade08Áàçå*cascade08çå≤è *cascade08≤è¥è*cascade08¥è‘ë *cascade08‘ëîî*cascade08îîË¨ *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062Ffile:///c:/Users/rovie%20segubre/agent/sovereign_api/gateway_server.py:&file:///c:/Users/rovie%20segubre/agent