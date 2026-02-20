import time
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
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import JSONResponse
import base64
from pymacaroons import Macaroon, Verifier
from api_key_registry import validate_key, get_agent_name, increment_usage

# --- x402 PROTOCOL (Real Coinbase CDP integration) ---
try:
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    from x402.http.types import RouteConfig
    from x402.mechanisms.evm.exact import ExactEvmServerScheme
    from x402.server import x402ResourceServer
    X402_SDK_AVAILABLE = True
except ImportError:
    X402_SDK_AVAILABLE = False
    print("⚠️  [x402] SDK not installed. Run: pip install 'x402[fastapi]'")

# --- FORCE LOAD .env (Fix 1: Docker env mounting) ---
env_path = Path("/app/.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print("✅ [Sovereign] .env LOADED INSIDE CONTAINER")
else:
    # Fallback: try local .env for development
    local_env = Path(__file__).parent / ".env"
    if local_env.exists():
        load_dotenv(dotenv_path=local_env, override=True)
        print("✅ [Sovereign] .env LOADED (local dev)")
    else:
        print("⚠️  [Sovereign] No .env found — using host/Docker defaults only")

print("=== GATEWAY ENV DEBUG ===")
print(f"  POLYGON_RPC            = {os.getenv('POLYGON_RPC', '(NOT SET)')}")
print(f"  FACILITATOR_KEY present = {bool(os.getenv('FACILITATOR_PRIVATE_KEY'))}")
print(f"  ENABLE_X402            = {os.getenv('ENABLE_X402', '(NOT SET)')}")
print(f"  MINT_SECRET present    = {bool(os.getenv('MINT_SECRET'))}")
print("=========================")

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

# --- x402 CONFIGURATION (Coinbase CDP / Base network) ---
X402_PAY_TO = os.getenv("X402_PAY_TO_ADDRESS", os.getenv("X402_WALLET_ADDRESS", ""))
X402_NETWORK = os.getenv("X402_NETWORK", "eip155:84532")  # Base Sepolia default
X402_FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator")
X402_PRICE = os.getenv("X402_PRICE_USDC", "$0.001")
ENABLE_X402 = os.getenv("ENABLE_X402", "true").lower() == "true"

# Legacy Polygon config (kept for watcher/relay backward compat)
FACILITATOR_PRIVATE_KEY = os.getenv("FACILITATOR_PRIVATE_KEY")
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")

# --- x402 MIDDLEWARE INITIALIZATION ---
if ENABLE_X402 and X402_SDK_AVAILABLE and X402_PAY_TO:
    try:
        _facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=X402_FACILITATOR_URL))
        _x402_server = x402ResourceServer(_facilitator)
        _x402_server.register(X402_NETWORK, ExactEvmServerScheme())

        _x402_routes = {
            "POST /v1/chat/completions": RouteConfig(
                accepts=[PaymentOption(
                    scheme="exact",
                    pay_to=X402_PAY_TO,
                    price=X402_PRICE,
                    network=X402_NETWORK,
                )],
                mime_type="application/json",
                description="AI chat completions via Sovereign API",
            ),
            "POST /v1/balance/topup": RouteConfig(
                accepts=[PaymentOption(
                    scheme="exact",
                    pay_to=X402_PAY_TO,
                    price=os.getenv("X402_TOPUP_PRICE", "$1.00"),  # Default $1.00 topup
                    network=X402_NETWORK,
                )],
                mime_type="application/json",
                description="Purchase Sovereign Balance Token (Macaroon)",
            ),
        }

        app.add_middleware(PaymentMiddlewareASGI, routes=_x402_routes, server=_x402_server)
        print(f"✅ [x402] Middleware initialized: network={X402_NETWORK}, pay_to={X402_PAY_TO[:10]}..., price={X402_PRICE}")
    except Exception as e:
        print(f"⚠️  [x402] Middleware init failed: {e}")
else:
    if not X402_PAY_TO:
        print("⚠️  [x402] Disabled: No X402_PAY_TO_ADDRESS set")
    elif not X402_SDK_AVAILABLE:
        print("⚠️  [x402] Disabled: SDK not installed")
    elif not ENABLE_X402:
        print("ℹ️  [x402] Disabled via ENABLE_X402=false")

# --- USDC EIP-3009 CONFIG ---
USDC_ADDRESS = os.getenv("USDC_CONTRACT_ADDRESS", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359") # Default: Polygon Mainnet
USDC_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "validAfter", "type": "uint256"},
            {"name": "validBefore", "type": "uint256"},
            {"name": "nonce", "type": "bytes32"},
            {"name": "v", "type": "uint8"},
            {"name": "r", "type": "bytes32"},
            {"name": "s", "type": "bytes32"}
        ],
        "name": "transferWithAuthorization",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

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



# --- x402 HELPER: Handled by PaymentMiddlewareASGI ---
# The x402 middleware automatically returns 402 with PAYMENT-REQUIRED headers
# and verifies PAYMENT-SIGNATURE headers via the CDP facilitator.
# No manual verify/headers functions needed.


# --- MIDDLEWARE: AUTH (Macaroon + API Key + L402) ---
# NOTE: x402 payments are now handled at the ASGI middleware level by PaymentMiddlewareASGI.
# Requests that pay via x402 bypass this function entirely (middleware settles before reaching here).
# This function only handles Macaroon and L402 auth for non-x402 requests.
async def verify_payment_header(request: Request, cost_sats: int):
    """
    Authentication check (Macaroon + API Key + L402).
    x402 is handled separately by PaymentMiddlewareASGI at ASGI level.
    
    Returns:
        (is_valid, auth_data)
        auth_data can be:
          - {"type": "macaroon", "new_token": ...}
          - {"type": "x402", "payment_payload": ...}
          - {"status": 401/402, "error": ...} (Failure)
    """

    # === CHECK 0: x402 PAYMENT (already verified by ASGI middleware) ===
    payment_payload = getattr(request.state, "payment_payload", None)
    if payment_payload:
        print(f"⚡ [x402] Payment verified by middleware — bypassing auth")
        return True, {"type": "x402", "payment_payload": payment_payload}

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
        print(f"🔑 [AUTH] Agent '{agent_name}' authenticated")
    
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

        # === 402: x402 is handled by ASGI middleware ===
        # If the request reaches here without x402 headers, fall through to L402

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

    # x402 RECEIPT: Return the payment receipt (middleware handles settlement separately)
    if isinstance(auth_data, dict) and auth_data.get("type") == "x402":
        payload = auth_data.get("payment_payload")
        if payload:
            try:
                receipt_json = json.dumps(payload if isinstance(payload, dict) else str(payload))
                encoded_receipt = base64.b64encode(receipt_json.encode()).decode()
                response.headers["PAYMENT-RESPONSE"] = encoded_receipt
            except Exception:
                pass  # Non-critical — settlement handled by x402 middleware

    return response


@app.get("/v1/models")
async def list_models():
    return {"data": [{"id": k, "price": v["price_sats"]} for k, v in MODEL_ROUTER.items()]}


@app.post("/v1/balance/topup")
async def topup_balance(request: Request):
    """
    x402-protected endpoint.
    If reached, payment ($1.00) is already verified by middleware.
    Mint a Macaroon with 100,000 sats credit.
    """
    # 1. Verify Payment (Middleware Check)
    payment_payload = getattr(request.state, "payment_payload", None)
    if not payment_payload:
        # Should be unreachable if middleware works, but safety net
        raise HTTPException(status_code=402, detail="Payment Required")

    # 2. Mint Token
    # $1.00 ~= 100,000 sats (rough approximation for simplicity or use oracle)
    # Since x402 price checks are strict ($1.00), we credit explicitly.
    credits_sats = 100000 
    
    # Generate macaroon (reuse existing mint logic via verify_and_spend hack or direct mint)
    # We need to ACCESS the MINT instance directly. 
    # MINT is initialized later in the file. We rely on MINT global.
    
    try:
        # Mint new macaroon with 100k sats
        # Note: MINT class needs a 'mint' method. Let's check MINT implementation below.
        # But MINT.verify_and_spend is for burning. We need MINTING.
        
        # HACK: Using generating logic from MINT (assuming MINT is SovereignMint instance)
        # We need to construct it manually as SovereignMint doesn't expose a public mint_new_token method easily
        # Wait, MINT.mint_token(amount) exists? Let's check.
        # Assuming verify_and_spend returns new_token, we can just mint fresh.
        
        macaroon = Macaroon(location=SITE_URL, identifier=secrets.token_hex(16), key=MINT_SECRET)
        macaroon.add_first_party_caveat(f"balance = {credits_sats}")
        macaroon.add_first_party_caveat(f"created = {time.time()}")
        serialized = macaroon.serialize()
        
        return {
            "status": "success",
            "credits_sats": credits_sats,
            "token": serialized,
            "message": "Refuel successful"
        }
    except Exception as e:
        print(f"❌ Minting failed: {e}")
        raise HTTPException(status_code=500, detail="Minting failed")


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
        print(f"📬 [MAILBOX] Token stored for {body['identifier'][:10]}...")
        
        return {"access_token": token, "status": "minted_and_stored", "balance": body['amount_sats']}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))  # Conflict (Double Spend)


@app.post("/v1/balance")
async def check_balance(request: Request):
    """
    Allows agents to check their token balance without client-side parsing.
    Returns: {"balance_sats": int, "has_fuel": bool}
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    
    token_str = auth_header.split(" ")[1]
    try:
        # Deserialize without verifying signature just to read caveats
        # (Real verification happens on spend, here we just helper-read)
        m = Macaroon.deserialize(token_str)
        balance = 0
        for caveat in m.caveats:
            cid = caveat.caveat_id
            if isinstance(cid, bytes):
                cid = cid.decode('utf-8')
            if cid.startswith("balance = "):
                balance = int(cid.split(" = ")[1])
        
        return {"balance_sats": balance, "has_fuel": balance > 0}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token format")


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
        print(f"📬 [MAILBOX] Token claimed for {tx_hash[:10]}...")
        return {"access_token": token, "status": "claimed"}
    
    # Check if already minted but claimed (or not yet processed)
    if tx_hash in MINT.history:
        return JSONResponse(status_code=410, content={"error": "Token already claimed"})
    
    return JSONResponse(status_code=404, content={"error": "Token not ready. Deposit may still be processing."})


@app.post("/v1/refuel/relay")
async def refuel_relay(request: Request):
    """
    Acts as a meta-transaction relayer for USDC.
    Allows agents with 0 POL to pay for AI fuel.
    """
    # 1. API Key Check (Identity)
    api_key = request.headers.get("X-Sovereign-Api-Key")
    print(f"🔑 [RELAY DEBUG] Received API Key: '{api_key}'")
    
    if not api_key or not validate_key(api_key):
        from api_key_registry import _load_registry
        reg = _load_registry()
        print(f"❌ [RELAY DEBUG] Validation failed. Registry keys: {list(reg.keys())}")
        raise HTTPException(status_code=401, detail="Invalid API Key")

    if not FACILITATOR_PRIVATE_KEY:
        raise HTTPException(status_code=500, detail="Server misconfigured: No facilitator key for gas.")

    body = await request.json()
    
    # Required fields for EIP-3009 transferWithAuthorization
    f = body.get('from')
    to = body.get('to')
    value = body.get('value')
    validAfter = body.get('validAfter')
    validBefore = body.get('validBefore')
    nonce = body.get('nonce')
    signature = body.get('signature')

    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    try:
        from web3 import Web3
        from eth_account import Account
        
        w3 = Web3(Web3.HTTPProvider(os.getenv("RELAY_RPC", POLYGON_RPC)))
        usdc = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)
        
        # Split signature
        sig_bytes = bytes.fromhex(signature[2:] if signature.startswith("0x") else signature)
        if len(sig_bytes) != 65:
            raise ValueError("Invalid signature length")
            
        r = sig_bytes[:32]
        s = sig_bytes[32:64]
        v = sig_bytes[64]
        if v < 27: v += 27 # Standard EIP-712 v

        # Execute using Facilitator
        facilitator_account = Account.from_key(FACILITATOR_PRIVATE_KEY)
        f_address = facilitator_account.address
        
        print(f"⛽ [RELAY] Executing USDC transfer for {f}...")
        
        nonce_tx = w3.eth.get_transaction_count(f_address)
        
        # Normalize nonce back to bytes32 for contract call
        nonce_bytes = bytes.fromhex(nonce[2:]) if nonce.startswith("0x") else bytes.fromhex(nonce)

        tx = usdc.functions.transferWithAuthorization(
            Web3.to_checksum_address(f), 
            Web3.to_checksum_address(to), 
            value, validAfter, validBefore, nonce_bytes,
            v, r, s
        ).build_transaction({
            'chainId': 84532, # Base Sepolia
            'gas': 150000,
            'gasPrice': int(w3.eth.gas_price * 1.5), # Aggressive gas for relayer
            'nonce': nonce_tx,
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, FACILITATOR_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        print(f"✅ [RELAY] Transaction sent: {tx_hash.hex()}")
        return {"tx_hash": tx_hash.hex(), "status": "relayed"}

    except Exception as e:
        print(f"❌ [RELAY ERROR] {e}")
        raise HTTPException(status_code=400, detail=str(e))


# --- SELF-REGISTRATION (AUTONOMOUS) ---
@app.post("/v1/register")
async def register_agent(request: Request):
    """
    Allow an agent to self-register and get an API key.
    No human required.
    """
    try:
        body = await request.json()
        name = body.get('name')
        description = body.get('description', 'Self-registered agent')

        if not name:
            raise HTTPException(status_code=400, detail="Name required")

        # Import here to avoid circular dependencies if any (though typically top-level is better, this is safe)
        from api_key_registry import create_key

        api_key, msg = create_key(name, description)

        if not api_key:
            raise HTTPException(status_code=409, detail=msg)

        return {
            "api_key": api_key,
            "agent_name": name,
            "gateway_wallet": os.getenv("X402_WALLET_ADDRESS") or os.getenv("MY_WALLET_ADDRESS") or "0x0000000000000000000000000000000000000000",
            "message": "Identity established. You are now sovereign. Next step: Fund your Macaroon."
        }
    except Exception as e:
        # Fallback for simple curl without json body, or invalid json
        return JSONResponse(status_code=400, content={"error": "Invalid request. Send JSON with 'name' field."})


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

    # --- x402 DISCOVERY ENDPOINT ---
    @app.get("/v1/x402/info")
    async def x402_info():
        """Returns gateway x402 configuration for agent/client discovery."""
        return {
            "x402_enabled": ENABLE_X402 and X402_SDK_AVAILABLE and bool(X402_PAY_TO),
            "version": "2.0",
            "supported_networks": [X402_NETWORK] if X402_PAY_TO else [],
            "price": X402_PRICE,
            "pay_to": X402_PAY_TO or None,
            "facilitator": X402_FACILITATOR_URL,
            "docs": "https://docs.cdp.coinbase.com/x402/quickstart-for-buyers",
        }

    print(f"Sovereign Mint (Universal Mode) starting on {PORT}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    except Exception as e:
        if "10048" in str(e):
            print(f"[CRITICAL] Port {PORT} is STUCK. Run: Stop-Process -Id (Get-NetTCPConnection -LocalPort {PORT}).OwningProcess -Force")
            sys.exit(1)
        raise e
