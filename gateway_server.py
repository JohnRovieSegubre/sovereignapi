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

from fastapi import FastAPI, Request, HTTPException, Response, Depends

from fastapi.responses import JSONResponse, FileResponse

from fastapi.middleware.cors import CORSMiddleware

from collections import defaultdict

import base64

from pymacaroons import Macaroon, Verifier

from api_key_registry import validate_key, get_agent_name, increment_usage



# --- x402 PROTOCOL (Real Coinbase CDP integration) ---

try:

    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption

    from x402.http.middleware.fastapi import PaymentMiddlewareASGI, payment_middleware

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

import asyncio

@app.on_event("startup")
async def startup_event():
    async def cleanup_macaroons():
        while True:
            try:
                # 86400 seconds = 1 day grace period for forensics
                cutoff = time.time() - 86400
                with MINT._get_db() as conn:
                    conn.execute("DELETE FROM macaroons WHERE expires_at < ?", (cutoff,))
                    conn.commit()
                print(f"🧹 [Cron] Cleaned up expired Macaroon sessions older than 24h.")
            except Exception as e:
                print(f"⚠️ [Cron] Failed to clean up Macaroons: {e}")
            await asyncio.sleep(3600) # Run every 60 minutes
    
    asyncio.create_task(cleanup_macaroons())



# --- CORS CONFIGURATION ---

app.add_middleware(

    CORSMiddleware,

    allow_origins=["*"],  # Adjust in production to restrict domains

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

    expose_headers=["X-Sovereign-Balance-Token", "PAYMENT-RESPONSE", "X-L402-Invoice"]

)



@app.get("/")
async def root():
    return {
        "status": "operational",
        "version": "6.0 (Pure Wallet-First)",
        "message": "Sovereign AI Gateway. Identity = Wallet.",
        "docs": "https://sovereign-api.com"
    }



# --- IN-MEMORY RATE LIMITER ---

RATE_LIMITS = defaultdict(list)

RL_WINDOW = 60  # seconds



def get_client_ip(request: Request) -> str:

    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:

        return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "127.0.0.1"



async def rate_limit(request: Request, max_requests: int):

    ip = get_client_ip(request)

    now = time.time()

    RATE_LIMITS[ip] = [t for t in RATE_LIMITS[ip] if now - t < RL_WINDOW]

    if len(RATE_LIMITS[ip]) >= max_requests:

        print(f"🛑 [RATE LIMIT] Blocked IP {ip}")

        raise HTTPException(status_code=429, detail="Too Many Requests")

    RATE_LIMITS[ip].append(now)



async def rl_strict(request: Request):

    await rate_limit(request, max_requests=10)  # Max 10 requests per minute



async def rl_standard(request: Request):

    await rate_limit(request, max_requests=120)  # Max 120 requests per minute



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



# --- x402 CONFIGURATION (Coinbase CDP / Base Mainnet) ---

X402_PAY_TO = os.getenv("X402_PAY_TO_ADDRESS", os.getenv("X402_WALLET_ADDRESS", ""))

X402_NETWORK = os.getenv("X402_NETWORK", "eip155:8453")  # Base Mainnet

X402_FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator")

X402_PRICE = os.getenv("X402_PRICE_USDC", "$0.001")

ENABLE_X402 = os.getenv("ENABLE_X402", "true").lower() == "true"



# Legacy config removed (FACILITATOR_PRIVATE_KEY, POLYGON_RPC not needed for x402)





# --- x402 MIDDLEWARE INITIALIZATION ---

_x402_middleware_func = None

if ENABLE_X402 and X402_SDK_AVAILABLE and X402_PAY_TO:

    try:

        # Load the official authenticated CDP Facilitator configuration

        try:

            from cdp.x402.x402 import create_facilitator_config

            cdp_config = create_facilitator_config(

                api_key_id=os.getenv("CDP_API_KEY_ID"),

                api_key_secret=os.getenv("CDP_API_KEY_SECRET")

            )

            _facilitator = HTTPFacilitatorClient(cdp_config)

            print(f"✅ [x402] Using authenticated CDP Facilitator: {cdp_config.get('url')}")

        except ImportError:

            # Fallback to unauthenticated config if cdp-sdk isn't installed

            _facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=X402_FACILITATOR_URL))

            print("⚠️  [x402] cdp-sdk not found, using unauthenticated Facilitator fallback.")

            

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

            "POST /v1/key/topup": RouteConfig(

                accepts=[PaymentOption(

                    scheme="exact",

                    pay_to=X402_PAY_TO,

                    price=os.getenv("X402_TOPUP_PRICE", "$1.00"),

                    network=X402_NETWORK,

                )],

                mime_type="application/json",

                description="Fund your prepaid API key with credits",

            ),

        }




        _x402_middleware_func = payment_middleware(routes=_x402_routes, server=_x402_server)

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





# --- UNIFIED PAYMENT MIDDLEWARE ---
# We must intercept the request BEFORE the x402 SDK, because the SDK strictly demands 
# a cryptographic signature and will block the transaction if one isn't present.
from fastapi.responses import JSONResponse

MAX_SESSION_DEPOSIT_SATS = 100000  # $1.00 hard cap

@app.middleware("http")
async def unified_payment_middleware(request: Request, call_next):
    # 1. Macaroon Bypass Check (The "Fast Lane")
    auth_header = request.headers.get("Authorization", "")
    
    if auth_header.startswith("Bearer ") and hasattr(request, "state"):
        token_str = auth_header.split(" ", 1)[1]
        try:
            m = Macaroon.deserialize(token_str)
            # Just pass the token to the route handler, verify_payment_header will do the DB deduction
            request.state.payment_payload = {"type": "macaroon_bypass", "token": token_str}
            return await call_next(request)
        except Exception:
            pass  # Invalid macaroon, let x402 handle it normally
            
    # 1b. Prepaid Key Check (The "OpenAI Lane")
    if auth_header.startswith("Bearer sk-sov-"):
        api_key = auth_header.split(" ", 1)[1]
        if validate_key(api_key):
            request.state.payment_payload = {"type": "prepaid_key", "key": api_key}
            return await call_next(request)

    # 2. Session Deposits — now handled AFTER x402 payment in verify_payment_header (L1410)
    # (Previously returned L402 format here, which x402 SDK clients couldn't parse)

    # 3. x402 SDK Check (The "Tollbooth")
    if _x402_middleware_func is not None:
        # We need to temporarily mock the request if it has an L402 header for a session deposit
        # because the SDK middleware might reject overpayments if it's strict.
        # However, most SDKs accept >= required price. Let's see if it passes naturally.
        return await _x402_middleware_func(request, call_next)
    
    # 4. Disabled x402 (Dev Mode)
    return await call_next(request)

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

    "sovereign/jamba-large-1.7": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "ai21/jamba-large-1.7", "price_sats": 500},  # AI21: Jamba Large 1.7

    "sovereign/aion-1.0": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "aion-labs/aion-1.0", "price_sats": 600},  # AionLabs: Aion-1.0

    "sovereign/aion-1.0-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "aion-labs/aion-1.0-mini", "price_sats": 105},  # AionLabs: Aion-1.0-Mini

    "sovereign/aion-rp-llama-3.1-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "aion-labs/aion-rp-llama-3.1-8b", "price_sats": 120},  # AionLabs: Aion-RP 1.0 (8B)

    "sovereign/codellama-7b-instruct-solidity": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "alfredpros/codellama-7b-instruct-solidity", "price_sats": 100},  # AlfredPros: CodeLLaMa 7B Instruct Solidity

    "sovereign/tongyi-deepresearch-30b-a3b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "alibaba/tongyi-deepresearch-30b-a3b", "price_sats": 27},  # Tongyi DeepResearch 30B A3B

    "sovereign/molmo-2-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/molmo-2-8b", "price_sats": 20},  # AllenAI: Molmo2 8B

    "sovereign/olmo-2-0325-32b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/olmo-2-0325-32b-instruct", "price_sats": 12},  # AllenAI: Olmo 2 32B Instruct

    "sovereign/olmo-3-32b-think": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/olmo-3-32b-think", "price_sats": 32},  # AllenAI: Olmo 3 32B Think

    "sovereign/olmo-3-7b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/olmo-3-7b-instruct", "price_sats": 15},  # AllenAI: Olmo 3 7B Instruct

    "sovereign/olmo-3-7b-think": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/olmo-3-7b-think", "price_sats": 16},  # AllenAI: Olmo 3 7B Think

    "sovereign/olmo-3.1-32b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/olmo-3.1-32b-instruct", "price_sats": 40},  # AllenAI: Olmo 3.1 32B Instruct

    "sovereign/olmo-3.1-32b-think": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "allenai/olmo-3.1-32b-think", "price_sats": 32},  # AllenAI: Olmo 3.1 32B Think

    "sovereign/goliath-120b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "alpindale/goliath-120b", "price_sats": 562},  # Goliath 120B

    "sovereign/nova-2-lite-v1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "amazon/nova-2-lite-v1", "price_sats": 140},  # Amazon: Nova 2 Lite

    "sovereign/nova-lite-v1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "amazon/nova-lite-v1", "price_sats": 15},  # Amazon: Nova Lite 1.0

    "sovereign/nova-micro-v1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "amazon/nova-micro-v1", "price_sats": 9},  # Amazon: Nova Micro 1.0

    "sovereign/nova-premier-v1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "amazon/nova-premier-v1", "price_sats": 750},  # Amazon: Nova Premier 1.0

    "sovereign/nova-pro-v1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "amazon/nova-pro-v1", "price_sats": 200},  # Amazon: Nova Pro 1.0

    "sovereign/magnum-v4-72b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthracite-org/magnum-v4-72b", "price_sats": 400},  # Magnum v4 72B

    "sovereign/claude-3-haiku": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-3-haiku", "price_sats": 75},  # Anthropic: Claude 3 Haiku

    "sovereign/claude-3.5-haiku": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-3.5-haiku", "price_sats": 240},  # Anthropic: Claude 3.5 Haiku

    "sovereign/claude-3.5-sonnet": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-3.5-sonnet", "price_sats": 1800},  # Anthropic: Claude 3.5 Sonnet

    "sovereign/claude-3.7-sonnet": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-3.7-sonnet", "price_sats": 900},  # Anthropic: Claude 3.7 Sonnet

    "sovereign/claude-3.7-sonnet:thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-3.7-sonnet:thinking", "price_sats": 900},  # Anthropic: Claude 3.7 Sonnet (thinking)

    "sovereign/claude-haiku-4.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-haiku-4.5", "price_sats": 300},  # Anthropic: Claude Haiku 4.5

    "sovereign/claude-opus-4": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-opus-4", "price_sats": 4500},  # Anthropic: Claude Opus 4

    "sovereign/claude-opus-4.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-opus-4.1", "price_sats": 4500},  # Anthropic: Claude Opus 4.1

    "sovereign/claude-opus-4.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-opus-4.5", "price_sats": 1500},  # Anthropic: Claude Opus 4.5

    "sovereign/claude-opus-4.6": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-opus-4.6", "price_sats": 1500},  # Anthropic: Claude Opus 4.6

    "sovereign/claude-sonnet-4": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-sonnet-4", "price_sats": 900},  # Anthropic: Claude Sonnet 4

    "sovereign/claude-sonnet-4.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-sonnet-4.5", "price_sats": 900},  # Anthropic: Claude Sonnet 4.5

    "sovereign/claude-sonnet-4.6": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "anthropic/claude-sonnet-4.6", "price_sats": 900},  # Anthropic: Claude Sonnet 4.6

    "sovereign/coder-large": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "arcee-ai/coder-large", "price_sats": 65},  # Arcee AI: Coder Large

    "sovereign/maestro-reasoning": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "arcee-ai/maestro-reasoning", "price_sats": 210},  # Arcee AI: Maestro Reasoning

    "sovereign/spotlight": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "arcee-ai/spotlight", "price_sats": 18},  # Arcee AI: Spotlight

    "sovereign/trinity-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "arcee-ai/trinity-mini", "price_sats": 10},  # Arcee AI: Trinity Mini

    "sovereign/virtuoso-large": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "arcee-ai/virtuoso-large", "price_sats": 97},  # Arcee AI: Virtuoso Large

    "sovereign/ernie-4.5-21b-a3b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "baidu/ernie-4.5-21b-a3b", "price_sats": 18},  # Baidu: ERNIE 4.5 21B A3B

    "sovereign/ernie-4.5-21b-a3b-thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "baidu/ernie-4.5-21b-a3b-thinking", "price_sats": 18},  # Baidu: ERNIE 4.5 21B A3B Thinking

    "sovereign/ernie-4.5-300b-a47b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "baidu/ernie-4.5-300b-a47b", "price_sats": 69},  # Baidu: ERNIE 4.5 300B A47B 

    "sovereign/ernie-4.5-vl-28b-a3b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "baidu/ernie-4.5-vl-28b-a3b", "price_sats": 35},  # Baidu: ERNIE 4.5 VL 28B A3B

    "sovereign/ernie-4.5-vl-424b-a47b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "baidu/ernie-4.5-vl-424b-a47b", "price_sats": 84},  # Baidu: ERNIE 4.5 VL 424B A47B 

    "sovereign/seed-1.6": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "bytedance-seed/seed-1.6", "price_sats": 112},  # ByteDance Seed: Seed 1.6

    "sovereign/seed-1.6-flash": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "bytedance-seed/seed-1.6-flash", "price_sats": 19},  # ByteDance Seed: Seed 1.6 Flash

    "sovereign/ui-tars-1.5-7b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "bytedance/ui-tars-1.5-7b", "price_sats": 15},  # ByteDance: UI-TARS 7B 

    "sovereign/command-a": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "cohere/command-a", "price_sats": 625},  # Cohere: Command A

    "sovereign/command-r-08-2024": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "cohere/command-r-08-2024", "price_sats": 37},  # Cohere: Command R (08-2024)

    "sovereign/command-r-plus-08-2024": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "cohere/command-r-plus-08-2024", "price_sats": 625},  # Cohere: Command R+ (08-2024)

    "sovereign/command-r7b-12-2024": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "cohere/command-r7b-12-2024", "price_sats": 9},  # Cohere: Command R7B (12-2024)

    "sovereign/cogito-v2.1-671b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepcogito/cogito-v2.1-671b", "price_sats": 125},  # Deep Cogito: Cogito v2.1 671B

    "sovereign/deepseek-chat": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-chat", "price_sats": 60},  # DeepSeek: DeepSeek V3

    "sovereign/deepseek-chat-v3-0324": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-chat-v3-0324", "price_sats": 53},  # DeepSeek: DeepSeek V3 0324

    "sovereign/deepseek-chat-v3.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-chat-v3.1", "price_sats": 45},  # DeepSeek: DeepSeek V3.1

    "sovereign/deepseek-r1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-r1", "price_sats": 160},  # DeepSeek: R1

    "sovereign/deepseek-r1-0528": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-r1-0528", "price_sats": 107},  # DeepSeek: R1 0528

    "sovereign/deepseek-r1-distill-llama-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-r1-distill-llama-70b", "price_sats": 75},  # DeepSeek: R1 Distill Llama 70B

    "sovereign/deepseek-r1-distill-qwen-32b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-r1-distill-qwen-32b", "price_sats": 29},  # DeepSeek: R1 Distill Qwen 32B

    "sovereign/deepseek-v3.1-terminus": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-v3.1-terminus", "price_sats": 50},  # DeepSeek: DeepSeek V3.1 Terminus

    "sovereign/deepseek-v3.2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-v3.2", "price_sats": 32},  # DeepSeek: DeepSeek V3.2

    "sovereign/deepseek-v3.2-exp": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-v3.2-exp", "price_sats": 34},  # DeepSeek: DeepSeek V3.2 Exp

    "sovereign/deepseek-v3.2-speciale": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "deepseek/deepseek-v3.2-speciale", "price_sats": 80},  # DeepSeek: DeepSeek V3.2 Speciale

    "sovereign/llemma_7b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "eleutherai/llemma_7b", "price_sats": 100},  # EleutherAI: Llemma 7b

    "sovereign/rnj-1-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "essentialai/rnj-1-instruct", "price_sats": 15},  # EssentialAI: Rnj 1 Instruct

    "sovereign/gemini-2.0-flash-001": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.0-flash-001", "price_sats": 25},  # Google: Gemini 2.0 Flash

    "sovereign/gemini-2.0-flash-lite-001": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.0-flash-lite-001", "price_sats": 19},  # Google: Gemini 2.0 Flash Lite

    "sovereign/gemini-2.5-flash": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-flash", "price_sats": 140},  # Google: Gemini 2.5 Flash

    "sovereign/gemini-2.5-flash-image": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-flash-image", "price_sats": 140},  # Google: Gemini 2.5 Flash Image (Nano Banana)

    "sovereign/gemini-2.5-flash-lite": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-flash-lite", "price_sats": 25},  # Google: Gemini 2.5 Flash Lite

    "sovereign/gemini-2.5-flash-lite-preview-09-2025": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-flash-lite-preview-09-2025", "price_sats": 25},  # Google: Gemini 2.5 Flash Lite Preview 09-2025

    "sovereign/gemini-2.5-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-pro", "price_sats": 562},  # Google: Gemini 2.5 Pro

    "sovereign/gemini-2.5-pro-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-pro-preview", "price_sats": 562},  # Google: Gemini 2.5 Pro Preview 06-05

    "sovereign/gemini-2.5-pro-preview-05-06": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-2.5-pro-preview-05-06", "price_sats": 562},  # Google: Gemini 2.5 Pro Preview 05-06

    "sovereign/gemini-3-flash-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-3-flash-preview", "price_sats": 175},  # Google: Gemini 3 Flash Preview

    "sovereign/gemini-3-pro-image-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-3-pro-image-preview", "price_sats": 700},  # Google: Nano Banana Pro (Gemini 3 Pro Image Preview)

    "sovereign/gemini-3-pro-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-3-pro-preview", "price_sats": 700},  # Google: Gemini 3 Pro Preview

    "sovereign/gemini-3.1-pro-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemini-3.1-pro-preview", "price_sats": 700},  # Google: Gemini 3.1 Pro Preview

    "sovereign/gemma-2-27b-it": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemma-2-27b-it", "price_sats": 65},  # Google: Gemma 2 27B

    "sovereign/gemma-2-9b-it": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemma-2-9b-it", "price_sats": 6},  # Google: Gemma 2 9B

    "sovereign/gemma-3-12b-it": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemma-3-12b-it", "price_sats": 8},  # Google: Gemma 3 12B

    "sovereign/gemma-3-27b-it": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemma-3-27b-it", "price_sats": 9},  # Google: Gemma 3 27B

    "sovereign/gemma-3-4b-it": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemma-3-4b-it", "price_sats": 6},  # Google: Gemma 3 4B

    "sovereign/gemma-3n-e4b-it": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "google/gemma-3n-e4b-it", "price_sats": 3},  # Google: Gemma 3n 4B

    "sovereign/mythomax-l2-13b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "gryphe/mythomax-l2-13b", "price_sats": 6},  # MythoMax 13B

    "sovereign/granite-4.0-h-micro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "ibm-granite/granite-4.0-h-micro", "price_sats": 6},  # IBM: Granite 4.0 Micro

    "sovereign/mercury": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "inception/mercury", "price_sats": 62},  # Inception: Mercury

    "sovereign/mercury-coder": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "inception/mercury-coder", "price_sats": 62},  # Inception: Mercury Coder

    "sovereign/inflection-3-pi": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "inflection/inflection-3-pi", "price_sats": 625},  # Inflection: Inflection 3 Pi

    "sovereign/inflection-3-productivity": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "inflection/inflection-3-productivity", "price_sats": 625},  # Inflection: Inflection 3 Productivity

    "sovereign/kat-coder-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "kwaipilot/kat-coder-pro", "price_sats": 52},  # Kwaipilot: KAT-Coder-Pro V1

    "sovereign/lfm-2.2-6b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "liquid/lfm-2.2-6b", "price_sats": 2},  # LiquidAI: LFM2-2.6B

    "sovereign/lfm2-8b-a1b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "liquid/lfm2-8b-a1b", "price_sats": 2},  # LiquidAI: LFM2-8B-A1B

    "sovereign/weaver": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mancer/weaver", "price_sats": 88},  # Mancer: Weaver (alpha)

    "sovereign/longcat-flash-chat": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meituan/longcat-flash-chat", "price_sats": 50},  # Meituan: LongCat Flash Chat

    "sovereign/llama-3-70b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3-70b-instruct", "price_sats": 62},  # Meta: Llama 3 70B Instruct

    "sovereign/llama-3-8b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3-8b-instruct", "price_sats": 3},  # Meta: Llama 3 8B Instruct

    "sovereign/llama-3.1-405b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.1-405b", "price_sats": 400},  # Meta: Llama 3.1 405B (base)

    "sovereign/llama-3.1-405b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.1-405b-instruct", "price_sats": 400},  # Meta: Llama 3.1 405B Instruct

    "sovereign/llama-3.1-70b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.1-70b-instruct", "price_sats": 40},  # Meta: Llama 3.1 70B Instruct

    "sovereign/llama-3.1-8b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.1-8b-instruct", "price_sats": 3},  # Meta: Llama 3.1 8B Instruct

    "sovereign/llama-3.2-11b-vision-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.2-11b-vision-instruct", "price_sats": 5},  # Meta: Llama 3.2 11B Vision Instruct

    "sovereign/llama-3.2-1b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.2-1b-instruct", "price_sats": 11},  # Meta: Llama 3.2 1B Instruct

    "sovereign/llama-3.2-3b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.2-3b-instruct", "price_sats": 2},  # Meta: Llama 3.2 3B Instruct

    "sovereign/llama-3.3-70b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-3.3-70b-instruct", "price_sats": 21},  # Meta: Llama 3.3 70B Instruct

    "sovereign/llama-4-maverick": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-4-maverick", "price_sats": 37},  # Meta: Llama 4 Maverick

    "sovereign/llama-4-scout": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-4-scout", "price_sats": 19},  # Meta: Llama 4 Scout

    "sovereign/llama-guard-2-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-guard-2-8b", "price_sats": 20},  # Meta: LlamaGuard 2 8B

    "sovereign/llama-guard-3-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-guard-3-8b", "price_sats": 4},  # Llama Guard 3 8B

    "sovereign/llama-guard-4-12b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "meta-llama/llama-guard-4-12b", "price_sats": 18},  # Meta: Llama Guard 4 12B

    "sovereign/phi-4": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "microsoft/phi-4", "price_sats": 10},  # Microsoft: Phi 4

    "sovereign/wizardlm-2-8x22b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "microsoft/wizardlm-2-8x22b", "price_sats": 62},  # WizardLM-2 8x22B

    "sovereign/minimax-01": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "minimax/minimax-01", "price_sats": 65},  # MiniMax: MiniMax-01

    "sovereign/minimax-m1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "minimax/minimax-m1", "price_sats": 130},  # MiniMax: MiniMax M1

    "sovereign/minimax-m2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "minimax/minimax-m2", "price_sats": 63},  # MiniMax: MiniMax M2

    "sovereign/minimax-m2-her": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "minimax/minimax-m2-her", "price_sats": 75},  # MiniMax: MiniMax M2-her

    "sovereign/minimax-m2.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "minimax/minimax-m2.1", "price_sats": 61},  # MiniMax: MiniMax M2.1

    "sovereign/minimax-m2.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "minimax/minimax-m2.5", "price_sats": 70},  # MiniMax: MiniMax M2.5

    "sovereign/codestral-2508": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/codestral-2508", "price_sats": 60},  # Mistral: Codestral 2508

    "sovereign/devstral-2512": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/devstral-2512", "price_sats": 120},  # Mistral: Devstral 2 2512

    "sovereign/devstral-medium": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/devstral-medium", "price_sats": 120},  # Mistral: Devstral Medium

    "sovereign/devstral-small": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/devstral-small", "price_sats": 20},  # Mistral: Devstral Small 1.1

    "sovereign/ministral-14b-2512": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/ministral-14b-2512", "price_sats": 20},  # Mistral: Ministral 3 14B 2512

    "sovereign/ministral-3b-2512": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/ministral-3b-2512", "price_sats": 10},  # Mistral: Ministral 3 3B 2512

    "sovereign/ministral-8b-2512": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/ministral-8b-2512", "price_sats": 15},  # Mistral: Ministral 3 8B 2512

    "sovereign/mistral-7b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-7b-instruct", "price_sats": 20},  # Mistral: Mistral 7B Instruct

    "sovereign/mistral-7b-instruct-v0.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-7b-instruct-v0.1", "price_sats": 15},  # Mistral: Mistral 7B Instruct v0.1

    "sovereign/mistral-7b-instruct-v0.2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-7b-instruct-v0.2", "price_sats": 20},  # Mistral: Mistral 7B Instruct v0.2

    "sovereign/mistral-7b-instruct-v0.3": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-7b-instruct-v0.3", "price_sats": 20},  # Mistral: Mistral 7B Instruct v0.3

    "sovereign/mistral-large": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-large", "price_sats": 400},  # Mistral Large

    "sovereign/mistral-large-2407": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-large-2407", "price_sats": 400},  # Mistral Large 2407

    "sovereign/mistral-large-2411": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-large-2411", "price_sats": 400},  # Mistral Large 2411

    "sovereign/mistral-large-2512": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-large-2512", "price_sats": 100},  # Mistral: Mistral Large 3 2512

    "sovereign/mistral-medium-3": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-medium-3", "price_sats": 120},  # Mistral: Mistral Medium 3

    "sovereign/mistral-medium-3.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-medium-3.1", "price_sats": 120},  # Mistral: Mistral Medium 3.1

    "sovereign/mistral-nemo": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-nemo", "price_sats": 3},  # Mistral: Mistral Nemo

    "sovereign/mistral-saba": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-saba", "price_sats": 40},  # Mistral: Saba

    "sovereign/mistral-small-24b-instruct-2501": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-small-24b-instruct-2501", "price_sats": 6},  # Mistral: Mistral Small 3

    "sovereign/mistral-small-3.1-24b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-small-3.1-24b-instruct", "price_sats": 45},  # Mistral: Mistral Small 3.1 24B

    "sovereign/mistral-small-3.2-24b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-small-3.2-24b-instruct", "price_sats": 12},  # Mistral: Mistral Small 3.2 24B

    "sovereign/mistral-small-creative": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mistral-small-creative", "price_sats": 20},  # Mistral: Mistral Small Creative

    "sovereign/mixtral-8x22b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mixtral-8x22b-instruct", "price_sats": 400},  # Mistral: Mixtral 8x22B Instruct

    "sovereign/mixtral-8x7b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/mixtral-8x7b-instruct", "price_sats": 54},  # Mistral: Mixtral 8x7B Instruct

    "sovereign/pixtral-large-2411": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/pixtral-large-2411", "price_sats": 400},  # Mistral: Pixtral Large 2411

    "sovereign/voxtral-small-24b-2507": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "mistralai/voxtral-small-24b-2507", "price_sats": 20},  # Mistral: Voxtral Small 24B 2507

    "sovereign/kimi-k2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "moonshotai/kimi-k2", "price_sats": 145},  # MoonshotAI: Kimi K2 0711

    "sovereign/kimi-k2-0905": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "moonshotai/kimi-k2-0905", "price_sats": 120},  # MoonshotAI: Kimi K2 0905

    "sovereign/kimi-k2-thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "moonshotai/kimi-k2-thinking", "price_sats": 123},  # MoonshotAI: Kimi K2 Thinking

    "sovereign/kimi-k2.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "moonshotai/kimi-k2.5", "price_sats": 162},  # MoonshotAI: Kimi K2.5

    "sovereign/morph-v3-fast": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "morph/morph-v3-fast", "price_sats": 100},  # Morph: Morph V3 Fast

    "sovereign/morph-v3-large": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "morph/morph-v3-large", "price_sats": 140},  # Morph: Morph V3 Large

    "sovereign/llama-3.1-lumimaid-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "neversleep/llama-3.1-lumimaid-8b", "price_sats": 34},  # NeverSleep: Lumimaid v0.2 8B

    "sovereign/noromaid-20b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "neversleep/noromaid-20b", "price_sats": 137},  # Noromaid 20B

    "sovereign/deepseek-v3.1-nex-n1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nex-agi/deepseek-v3.1-nex-n1", "price_sats": 64},  # Nex AGI: DeepSeek V3.1 Nex N1

    "sovereign/hermes-2-pro-llama-3-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nousresearch/hermes-2-pro-llama-3-8b", "price_sats": 14},  # NousResearch: Hermes 2 Pro - Llama-3 8B

    "sovereign/hermes-3-llama-3.1-405b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nousresearch/hermes-3-llama-3.1-405b", "price_sats": 100},  # Nous: Hermes 3 405B Instruct

    "sovereign/hermes-3-llama-3.1-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nousresearch/hermes-3-llama-3.1-70b", "price_sats": 30},  # Nous: Hermes 3 70B Instruct

    "sovereign/hermes-4-405b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nousresearch/hermes-4-405b", "price_sats": 200},  # Nous: Hermes 4 405B

    "sovereign/hermes-4-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nousresearch/hermes-4-70b", "price_sats": 26},  # Nous: Hermes 4 70B

    "sovereign/llama-3.1-nemotron-70b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nvidia/llama-3.1-nemotron-70b-instruct", "price_sats": 120},  # NVIDIA: Llama 3.1 Nemotron 70B Instruct

    "sovereign/llama-3.1-nemotron-ultra-253b-v1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nvidia/llama-3.1-nemotron-ultra-253b-v1", "price_sats": 120},  # NVIDIA: Llama 3.1 Nemotron Ultra 253B v1

    "sovereign/llama-3.3-nemotron-super-49b-v1.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nvidia/llama-3.3-nemotron-super-49b-v1.5", "price_sats": 25},  # NVIDIA: Llama 3.3 Nemotron Super 49B V1.5

    "sovereign/nemotron-3-nano-30b-a3b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nvidia/nemotron-3-nano-30b-a3b", "price_sats": 12},  # NVIDIA: Nemotron 3 Nano 30B A3B

    "sovereign/nemotron-nano-12b-v2-vl": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nvidia/nemotron-nano-12b-v2-vl", "price_sats": 13},  # NVIDIA: Nemotron Nano 12B 2 VL

    "sovereign/nemotron-nano-9b-v2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "nvidia/nemotron-nano-9b-v2", "price_sats": 10},  # NVIDIA: Nemotron Nano 9B V2

    "sovereign/gpt-3.5-turbo": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-3.5-turbo", "price_sats": 100},  # OpenAI: GPT-3.5 Turbo

    "sovereign/gpt-3.5-turbo-0613": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-3.5-turbo-0613", "price_sats": 150},  # OpenAI: GPT-3.5 Turbo (older v0613)

    "sovereign/gpt-3.5-turbo-16k": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-3.5-turbo-16k", "price_sats": 350},  # OpenAI: GPT-3.5 Turbo 16k

    "sovereign/gpt-3.5-turbo-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-3.5-turbo-instruct", "price_sats": 175},  # OpenAI: GPT-3.5 Turbo Instruct

    "sovereign/gpt-4": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4", "price_sats": 4500},  # OpenAI: GPT-4

    "sovereign/gpt-4-0314": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4-0314", "price_sats": 4500},  # OpenAI: GPT-4 (older v0314)

    "sovereign/gpt-4-1106-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4-1106-preview", "price_sats": 2000},  # OpenAI: GPT-4 Turbo (older v1106)

    "sovereign/gpt-4-turbo": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4-turbo", "price_sats": 2000},  # OpenAI: GPT-4 Turbo

    "sovereign/gpt-4-turbo-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4-turbo-preview", "price_sats": 2000},  # OpenAI: GPT-4 Turbo Preview

    "sovereign/gpt-4.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4.1", "price_sats": 500},  # OpenAI: GPT-4.1

    "sovereign/gpt-4.1-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4.1-mini", "price_sats": 100},  # OpenAI: GPT-4.1 Mini

    "sovereign/gpt-4.1-nano": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4.1-nano", "price_sats": 25},  # OpenAI: GPT-4.1 Nano

    "sovereign/gpt-4o": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o", "price_sats": 625},  # OpenAI: GPT-4o

    "sovereign/gpt-4o-2024-05-13": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-2024-05-13", "price_sats": 1000},  # OpenAI: GPT-4o (2024-05-13)

    "sovereign/gpt-4o-2024-08-06": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-2024-08-06", "price_sats": 625},  # OpenAI: GPT-4o (2024-08-06)

    "sovereign/gpt-4o-2024-11-20": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-2024-11-20", "price_sats": 625},  # OpenAI: GPT-4o (2024-11-20)

    "sovereign/gpt-4o-audio-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-audio-preview", "price_sats": 625},  # OpenAI: GPT-4o Audio

    "sovereign/gpt-4o-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-mini", "price_sats": 37},  # OpenAI: GPT-4o-mini

    "sovereign/gpt-4o-mini-2024-07-18": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-mini-2024-07-18", "price_sats": 37},  # OpenAI: GPT-4o-mini (2024-07-18)

    "sovereign/gpt-4o-mini-search-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-mini-search-preview", "price_sats": 37},  # OpenAI: GPT-4o-mini Search Preview

    "sovereign/gpt-4o-search-preview": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-4o-search-preview", "price_sats": 625},  # OpenAI: GPT-4o Search Preview

    "sovereign/gpt-5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5", "price_sats": 562},  # OpenAI: GPT-5

    "sovereign/gpt-5-chat": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-chat", "price_sats": 562},  # OpenAI: GPT-5 Chat

    "sovereign/gpt-5-codex": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-codex", "price_sats": 562},  # OpenAI: GPT-5 Codex

    "sovereign/gpt-5-image": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-image", "price_sats": 1000},  # OpenAI: GPT-5 Image

    "sovereign/gpt-5-image-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-image-mini", "price_sats": 225},  # OpenAI: GPT-5 Image Mini

    "sovereign/gpt-5-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-mini", "price_sats": 112},  # OpenAI: GPT-5 Mini

    "sovereign/gpt-5-nano": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-nano", "price_sats": 22},  # OpenAI: GPT-5 Nano

    "sovereign/gpt-5-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5-pro", "price_sats": 6750},  # OpenAI: GPT-5 Pro

    "sovereign/gpt-5.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.1", "price_sats": 562},  # OpenAI: GPT-5.1

    "sovereign/gpt-5.1-chat": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.1-chat", "price_sats": 562},  # OpenAI: GPT-5.1 Chat

    "sovereign/gpt-5.1-codex": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.1-codex", "price_sats": 562},  # OpenAI: GPT-5.1-Codex

    "sovereign/gpt-5.1-codex-max": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.1-codex-max", "price_sats": 562},  # OpenAI: GPT-5.1-Codex-Max

    "sovereign/gpt-5.1-codex-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.1-codex-mini", "price_sats": 112},  # OpenAI: GPT-5.1-Codex-Mini

    "sovereign/gpt-5.2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.2", "price_sats": 787},  # OpenAI: GPT-5.2

    "sovereign/gpt-5.2-chat": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.2-chat", "price_sats": 787},  # OpenAI: GPT-5.2 Chat

    "sovereign/gpt-5.2-codex": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.2-codex", "price_sats": 787},  # OpenAI: GPT-5.2-Codex

    "sovereign/gpt-5.2-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-5.2-pro", "price_sats": 9450},  # OpenAI: GPT-5.2 Pro

    "sovereign/gpt-audio": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-audio", "price_sats": 625},  # OpenAI: GPT Audio

    "sovereign/gpt-audio-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-audio-mini", "price_sats": 150},  # OpenAI: GPT Audio Mini

    "sovereign/gpt-oss-120b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-oss-120b", "price_sats": 11},  # OpenAI: gpt-oss-120b

    "sovereign/gpt-oss-20b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-oss-20b", "price_sats": 8},  # OpenAI: gpt-oss-20b

    "sovereign/gpt-oss-safeguard-20b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/gpt-oss-safeguard-20b", "price_sats": 19},  # OpenAI: gpt-oss-safeguard-20b

    "sovereign/o1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o1", "price_sats": 3750},  # OpenAI: o1

    "sovereign/o1-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o1-pro", "price_sats": 37500},  # OpenAI: o1-pro

    "sovereign/o3": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o3", "price_sats": 500},  # OpenAI: o3

    "sovereign/o3-deep-research": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o3-deep-research", "price_sats": 2500},  # OpenAI: o3 Deep Research

    "sovereign/o3-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o3-mini", "price_sats": 275},  # OpenAI: o3 Mini

    "sovereign/o3-mini-high": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o3-mini-high", "price_sats": 275},  # OpenAI: o3 Mini High

    "sovereign/o3-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o3-pro", "price_sats": 5000},  # OpenAI: o3 Pro

    "sovereign/o4-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o4-mini", "price_sats": 275},  # OpenAI: o4 Mini

    "sovereign/o4-mini-deep-research": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o4-mini-deep-research", "price_sats": 500},  # OpenAI: o4 Mini Deep Research

    "sovereign/o4-mini-high": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "openai/o4-mini-high", "price_sats": 275},  # OpenAI: o4 Mini High

    "sovereign/internvl3-78b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "opengvlab/internvl3-78b", "price_sats": 37},  # OpenGVLab: InternVL3 78B

    "sovereign/sonar": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "perplexity/sonar", "price_sats": 100},  # Perplexity: Sonar

    "sovereign/sonar-deep-research": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "perplexity/sonar-deep-research", "price_sats": 500},  # Perplexity: Sonar Deep Research

    "sovereign/sonar-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "perplexity/sonar-pro", "price_sats": 900},  # Perplexity: Sonar Pro

    "sovereign/sonar-pro-search": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "perplexity/sonar-pro-search", "price_sats": 900},  # Perplexity: Sonar Pro Search

    "sovereign/sonar-reasoning-pro": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "perplexity/sonar-reasoning-pro", "price_sats": 500},  # Perplexity: Sonar Reasoning Pro

    "sovereign/intellect-3": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "prime-intellect/intellect-3", "price_sats": 65},  # Prime Intellect: INTELLECT-3

    "sovereign/qwen-2.5-72b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-2.5-72b-instruct", "price_sats": 26},  # Qwen2.5 72B Instruct

    "sovereign/qwen-2.5-7b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-2.5-7b-instruct", "price_sats": 7},  # Qwen: Qwen2.5 7B Instruct

    "sovereign/qwen-2.5-coder-32b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-2.5-coder-32b-instruct", "price_sats": 20},  # Qwen2.5 Coder 32B Instruct

    "sovereign/qwen-2.5-vl-7b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-2.5-vl-7b-instruct", "price_sats": 20},  # Qwen: Qwen2.5-VL 7B Instruct

    "sovereign/qwen-max": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-max", "price_sats": 400},  # Qwen: Qwen-Max 

    "sovereign/qwen-plus": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-plus", "price_sats": 80},  # Qwen: Qwen-Plus

    "sovereign/qwen-plus-2025-07-28": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-plus-2025-07-28", "price_sats": 80},  # Qwen: Qwen Plus 0728

    "sovereign/qwen-plus-2025-07-28:thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-plus-2025-07-28:thinking", "price_sats": 80},  # Qwen: Qwen Plus 0728 (thinking)

    "sovereign/qwen-turbo": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-turbo", "price_sats": 12},  # Qwen: Qwen-Turbo

    "sovereign/qwen-vl-max": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-vl-max", "price_sats": 200},  # Qwen: Qwen VL Max

    "sovereign/qwen-vl-plus": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen-vl-plus", "price_sats": 42},  # Qwen: Qwen VL Plus

    "sovereign/qwen2.5-coder-7b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen2.5-coder-7b-instruct", "price_sats": 6},  # Qwen: Qwen2.5 Coder 7B Instruct

    "sovereign/qwen2.5-vl-32b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen2.5-vl-32b-instruct", "price_sats": 40},  # Qwen: Qwen2.5 VL 32B Instruct

    "sovereign/qwen2.5-vl-72b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen2.5-vl-72b-instruct", "price_sats": 50},  # Qwen: Qwen2.5 VL 72B Instruct

    "sovereign/qwen3-14b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-14b", "price_sats": 15},  # Qwen: Qwen3 14B

    "sovereign/qwen3-235b-a22b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-235b-a22b", "price_sats": 114},  # Qwen: Qwen3 235B A22B

    "sovereign/qwen3-235b-a22b-2507": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-235b-a22b-2507", "price_sats": 9},  # Qwen: Qwen3 235B A22B Instruct 2507

    "sovereign/qwen3-30b-a3b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-30b-a3b", "price_sats": 18},  # Qwen: Qwen3 30B A3B

    "sovereign/qwen3-30b-a3b-instruct-2507": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-30b-a3b-instruct-2507", "price_sats": 19},  # Qwen: Qwen3 30B A3B Instruct 2507

    "sovereign/qwen3-30b-a3b-thinking-2507": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-30b-a3b-thinking-2507", "price_sats": 20},  # Qwen: Qwen3 30B A3B Thinking 2507

    "sovereign/qwen3-32b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-32b", "price_sats": 16},  # Qwen: Qwen3 32B

    "sovereign/qwen3-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-8b", "price_sats": 22},  # Qwen: Qwen3 8B

    "sovereign/qwen3-coder": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-coder", "price_sats": 61},  # Qwen: Qwen3 Coder 480B A35B

    "sovereign/qwen3-coder-30b-a3b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-coder-30b-a3b-instruct", "price_sats": 17},  # Qwen: Qwen3 Coder 30B A3B Instruct

    "sovereign/qwen3-coder-flash": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-coder-flash", "price_sats": 90},  # Qwen: Qwen3 Coder Flash

    "sovereign/qwen3-coder-next": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-coder-next", "price_sats": 44},  # Qwen: Qwen3 Coder Next

    "sovereign/qwen3-coder-plus": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-coder-plus", "price_sats": 300},  # Qwen: Qwen3 Coder Plus

    "sovereign/qwen3-max": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-max", "price_sats": 360},  # Qwen: Qwen3 Max

    "sovereign/qwen3-max-thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-max-thinking", "price_sats": 360},  # Qwen: Qwen3 Max Thinking

    "sovereign/qwen3-next-80b-a3b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-next-80b-a3b-instruct", "price_sats": 60},  # Qwen: Qwen3 Next 80B A3B Instruct

    "sovereign/qwen3-next-80b-a3b-thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-next-80b-a3b-thinking", "price_sats": 67},  # Qwen: Qwen3 Next 80B A3B Thinking

    "sovereign/qwen3-vl-235b-a22b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-vl-235b-a22b-instruct", "price_sats": 54},  # Qwen: Qwen3 VL 235B A22B Instruct

    "sovereign/qwen3-vl-30b-a3b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-vl-30b-a3b-instruct", "price_sats": 32},  # Qwen: Qwen3 VL 30B A3B Instruct

    "sovereign/qwen3-vl-32b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-vl-32b-instruct", "price_sats": 26},  # Qwen: Qwen3 VL 32B Instruct

    "sovereign/qwen3-vl-8b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-vl-8b-instruct", "price_sats": 29},  # Qwen: Qwen3 VL 8B Instruct

    "sovereign/qwen3-vl-8b-thinking": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3-vl-8b-thinking", "price_sats": 74},  # Qwen: Qwen3 VL 8B Thinking

    "sovereign/qwen3.5-397b-a17b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3.5-397b-a17b", "price_sats": 57},  # Qwen: Qwen3.5 397B A17B

    "sovereign/qwen3.5-plus-02-15": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwen3.5-plus-02-15", "price_sats": 140},  # Qwen: Qwen3.5 Plus 2026-02-15

    "sovereign/qwq-32b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "qwen/qwq-32b", "price_sats": 27},  # Qwen: QwQ 32B

    "sovereign/sorcererlm-8x22b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "raifle/sorcererlm-8x22b", "price_sats": 450},  # SorcererLM 8x22B

    "sovereign/relace-apply-3": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "relace/relace-apply-3", "price_sats": 105},  # Relace: Relace Apply 3

    "sovereign/relace-search": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "relace/relace-search", "price_sats": 200},  # Relace: Relace Search

    "sovereign/l3-euryale-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "sao10k/l3-euryale-70b", "price_sats": 148},  # Sao10k: Llama 3 Euryale 70B v2.1

    "sovereign/l3-lunaris-8b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "sao10k/l3-lunaris-8b", "price_sats": 4},  # Sao10K: Llama 3 8B Lunaris

    "sovereign/l3.1-70b-hanami-x1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "sao10k/l3.1-70b-hanami-x1", "price_sats": 300},  # Sao10K: Llama 3.1 70B Hanami x1

    "sovereign/l3.1-euryale-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "sao10k/l3.1-euryale-70b", "price_sats": 70},  # Sao10K: Llama 3.1 Euryale 70B v2.2

    "sovereign/l3.3-euryale-70b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "sao10k/l3.3-euryale-70b", "price_sats": 70},  # Sao10K: Llama 3.3 Euryale 70B

    "sovereign/step-3.5-flash": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "stepfun/step-3.5-flash", "price_sats": 20},  # StepFun: Step 3.5 Flash

    "sovereign/router": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "switchpoint/router", "price_sats": 212},  # Switchpoint Router

    "sovereign/hunyuan-a13b-instruct": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "tencent/hunyuan-a13b-instruct", "price_sats": 36},  # Tencent: Hunyuan A13B Instruct

    "sovereign/cydonia-24b-v4.1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "thedrummer/cydonia-24b-v4.1", "price_sats": 40},  # TheDrummer: Cydonia 24B V4.1

    "sovereign/rocinante-12b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "thedrummer/rocinante-12b", "price_sats": 30},  # TheDrummer: Rocinante 12B

    "sovereign/skyfall-36b-v2": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "thedrummer/skyfall-36b-v2", "price_sats": 68},  # TheDrummer: Skyfall 36B V2

    "sovereign/unslopnemo-12b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "thedrummer/unslopnemo-12b", "price_sats": 40},  # TheDrummer: UnslopNemo 12B

    "sovereign/deepseek-r1t2-chimera": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "tngtech/deepseek-r1t2-chimera", "price_sats": 55},  # TNG: DeepSeek R1T2 Chimera

    "sovereign/remm-slerp-l2-13b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "undi95/remm-slerp-l2-13b", "price_sats": 55},  # ReMM SLERP 13B

    "sovereign/palmyra-x5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "writer/palmyra-x5", "price_sats": 330},  # Writer: Palmyra X5

    "sovereign/grok-3": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-3", "price_sats": 900},  # xAI: Grok 3

    "sovereign/grok-3-beta": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-3-beta", "price_sats": 900},  # xAI: Grok 3 Beta

    "sovereign/grok-3-mini": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-3-mini", "price_sats": 40},  # xAI: Grok 3 Mini

    "sovereign/grok-3-mini-beta": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-3-mini-beta", "price_sats": 40},  # xAI: Grok 3 Mini Beta

    "sovereign/grok-4": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-4", "price_sats": 900},  # xAI: Grok 4

    "sovereign/grok-4-fast": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-4-fast", "price_sats": 35},  # xAI: Grok 4 Fast

    "sovereign/grok-4.1-fast": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-4.1-fast", "price_sats": 35},  # xAI: Grok 4.1 Fast

    "sovereign/grok-code-fast-1": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "x-ai/grok-code-fast-1", "price_sats": 85},  # xAI: Grok Code Fast 1

    "sovereign/mimo-v2-flash": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "xiaomi/mimo-v2-flash", "price_sats": 19},  # Xiaomi: MiMo-V2-Flash

    "sovereign/glm-4-32b": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4-32b", "price_sats": 10},  # Z.ai: GLM 4 32B 

    "sovereign/glm-4.5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.5", "price_sats": 128},  # Z.ai: GLM 4.5

    "sovereign/glm-4.5-air": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.5-air", "price_sats": 49},  # Z.ai: GLM 4.5 Air

    "sovereign/glm-4.5v": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.5v", "price_sats": 120},  # Z.ai: GLM 4.5V

    "sovereign/glm-4.6": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.6", "price_sats": 103},  # Z.ai: GLM 4.6

    "sovereign/glm-4.6v": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.6v", "price_sats": 60},  # Z.ai: GLM 4.6V

    "sovereign/glm-4.7": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.7", "price_sats": 104},  # Z.ai: GLM 4.7

    "sovereign/glm-4.7-flash": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-4.7-flash", "price_sats": 23},  # Z.ai: GLM 4.7 Flash

    "sovereign/glm-5": {"backend_url": "https://openrouter.ai/api/v1/chat/completions", "backend_model": "z-ai/glm-5", "price_sats": 142},  # Z.ai: GLM 5

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





# --- CLASS: THE SOVEREIGN MINT (SECURED - SQLite WAL) ---
import sqlite3
import time
import secrets
from pathlib import Path
import json

class SovereignMint:
    def __init__(self, secret, location):
        self.secret = secret
        self.location = location
        self.db_path = DATA_DIR / "mint_history.db"
        self._init_db()

    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_db() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS macaroons (
                    id TEXT PRIMARY KEY,
                    remaining_sats INTEGER NOT NULL,
                    expires_at REAL NOT NULL,
                    revoked BOOLEAN DEFAULT 0
                )
            """)
            # --- Prepaid API Key Ledger ---
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_balances (
                    api_key        TEXT PRIMARY KEY,
                    balance_credits INTEGER DEFAULT 0,
                    total_funded   INTEGER DEFAULT 0,
                    total_spent    INTEGER DEFAULT 0,
                    spend_cap_day  INTEGER DEFAULT 1000000,
                    spent_today    INTEGER DEFAULT 0,
                    spent_today_date TEXT DEFAULT '',
                    last_topup_at  REAL DEFAULT 0,
                    last_spend_at  REAL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_transactions (
                    id             TEXT PRIMARY KEY,
                    api_key        TEXT NOT NULL,
                    type           TEXT NOT NULL,
                    amount         INTEGER NOT NULL,
                    balance_after  INTEGER NOT NULL,
                    model          TEXT,
                    created_at     REAL NOT NULL,
                    x402_receipt   TEXT
                )
            """)
            conn.commit()

    def create_session(self, amount_sats: int, ttl_seconds: int = 900):
        """Mints a new static session macaroon."""
        session_id = f"sess_{secrets.token_hex(16)}"
        expires_at = time.time() + ttl_seconds
        
        m = Macaroon(location=self.location, identifier=session_id, key=self.secret)
        
        with self._get_db() as conn:
            conn.execute(
                "INSERT INTO macaroons (id, remaining_sats, expires_at, revoked) VALUES (?, ?, ?, 0)",
                (session_id, amount_sats, expires_at)
            )
            conn.commit()
            
        return m.serialize(), amount_sats

    def verify_and_spend(self, token_str: str, cost: int):
        """Verifies session token, deducts cost atomically from SQLite."""
        try:
            m = Macaroon.deserialize(token_str)
            m_id = m.identifier
            if isinstance(m_id, bytes):
                m_id = m_id.decode('utf-8')
            
            v = Verifier()
            # We trust the db balance, so we only need to verify the HMAC signature
            if not v.verify(m, self.secret): 
                return False, None, "Invalid Signature"

            with self._get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE macaroons 
                    SET remaining_sats = remaining_sats - ? 
                    WHERE id = ? 
                      AND remaining_sats >= ? 
                      AND expires_at > ? 
                      AND revoked = 0
                    RETURNING remaining_sats
                """, (cost, m_id, cost, time.time()))
                
                row = cursor.fetchone()
                if row:
                    new_balance = row["remaining_sats"]
                    conn.commit()
                    return True, new_balance, "Success"
                
                # If we get here, the update failed. Let's find out why for accurate error reporting.
                cursor.execute("SELECT remaining_sats, expires_at, revoked FROM macaroons WHERE id = ?", (m_id,))
                state = cursor.fetchone()
                if not state:
                    return False, None, "Token/Session not found"
                if state["revoked"]:
                    return False, None, "Token/Session revoked"
                if state["expires_at"] <= time.time():
                    return False, None, "Token/Session expired"
                if state["remaining_sats"] < cost:
                    return False, state["remaining_sats"], "Insufficient Funds"
                    
                return False, None, "Unknown spend error"
        except Exception as e:
            return False, None, f"Token Error: {e}"

    # --- Prepaid API Key Methods ---

    def topup_key(self, api_key: str, amount: int, idempotency_key: str, receipt: str = None):
        """Credit balance to an API key. Idempotent."""
        with self._get_db() as conn:
            existing = conn.execute("SELECT id FROM key_transactions WHERE id = ?", (idempotency_key,)).fetchone()
            if existing:
                row = conn.execute("SELECT balance_credits FROM key_balances WHERE api_key = ?", (api_key,)).fetchone()
                return row["balance_credits"] if row else 0

            conn.execute("""
                INSERT INTO key_balances (api_key, balance_credits, total_funded, last_topup_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(api_key) DO UPDATE SET
                    balance_credits = balance_credits + ?,
                    total_funded = total_funded + ?,
                    last_topup_at = ?
            """, (api_key, amount, amount, time.time(), amount, amount, time.time()))

            new_balance = conn.execute("SELECT balance_credits FROM key_balances WHERE api_key = ?", (api_key,)).fetchone()["balance_credits"]

            conn.execute("""
                INSERT INTO key_transactions (id, api_key, type, amount, balance_after, created_at, x402_receipt)
                VALUES (?, ?, 'topup', ?, ?, ?, ?)
            """, (idempotency_key, api_key, amount, new_balance, time.time(), receipt))
            conn.commit()
            print(f"💰 [topup] Key {api_key[:15]}... credited {amount} credits. Balance: {new_balance}")
            return new_balance

    def spend_from_key(self, api_key: str, cost: int, model: str = None):
        """Deduct from key balance. Returns (success, remaining, message)."""
        today = time.strftime("%Y-%m-%d")
        with self._get_db() as conn:
            row = conn.execute("SELECT balance_credits, spend_cap_day, spent_today, spent_today_date FROM key_balances WHERE api_key = ?", (api_key,)).fetchone()
            if not row:
                return False, 0, "No balance. Fund your key: POST /v1/key/topup"

            balance = row["balance_credits"]
            cap = row["spend_cap_day"]
            spent_today = row["spent_today"] if row["spent_today_date"] == today else 0

            if balance < cost:
                return False, balance, f"Insufficient balance ({balance} < {cost}). Top up: POST /v1/key/topup"

            if spent_today + cost > cap:
                return False, balance, f"Daily spend cap reached ({spent_today}/{cap})"

            new_balance = balance - cost
            new_spent = spent_today + cost
            conn.execute("""
                UPDATE key_balances SET
                    balance_credits = ?,
                    total_spent = total_spent + ?,
                    spent_today = ?,
                    spent_today_date = ?,
                    last_spend_at = ?
                WHERE api_key = ?
            """, (new_balance, cost, new_spent, today, time.time(), api_key))

            tx_id = f"spend_{secrets.token_hex(8)}"
            conn.execute("""
                INSERT INTO key_transactions (id, api_key, type, amount, balance_after, model, created_at)
                VALUES (?, ?, 'spend', ?, ?, ?, ?)
            """, (tx_id, api_key, cost, new_balance, model, time.time()))
            conn.commit()
            return True, new_balance, "OK"

    def get_key_balance(self, api_key: str):
        """Get current balance for an API key."""
        with self._get_db() as conn:
            row = conn.execute("SELECT balance_credits, total_funded, total_spent, spend_cap_day FROM key_balances WHERE api_key = ?", (api_key,)).fetchone()
            if not row:
                return None
            return dict(row)

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
    Returns:
        (is_valid, auth_data)
        auth_data can be:
          - {"type": "macaroon", "new_token": None, "balance": <int>}
          - {"type": "x402", "payment_payload": ..., "minted_macaroon": <str|None>}
          - {"status": 401/402, "error": ...} (Failure)
    """

    # === CHECK 0: PAYMENT PRE-AUTHORIZED (by middleware) ===
    payment_payload = getattr(request.state, "payment_payload", None)
    if payment_payload:
        # Macaroon bypass: middleware validated the token HMAC, we need to spend from DB balance
        if isinstance(payment_payload, dict) and payment_payload.get("type") == "macaroon_bypass":
            token_str = payment_payload.get("token")
            valid, balance, msg = MINT.verify_and_spend(token_str, cost_sats)
            if valid:
                print(f"🎫 [Macaroon] Spent {cost_sats} sats (bypassed x402). Remaining: {balance}")
                return True, {"type": "macaroon", "balance": balance, "token": token_str}
            else:
                print(f"🎫 [Macaroon] Spend failed: {msg}")
                # We return string for errors so chat_completions can handle it nicely
                return False, msg
        # Prepaid key: middleware validated the key, we need to spend from balance
        if isinstance(payment_payload, dict) and payment_payload.get("type") == "prepaid_key":
            api_key = payment_payload.get("key")
            requested_model = None
            try:
                body = await request.json()
                requested_model = body.get("model")
            except Exception:
                pass
            valid, balance, msg = MINT.spend_from_key(api_key, cost_sats, model=requested_model)
            if valid:
                print(f"🔑 [PrepaidKey] Spent {cost_sats} credits from {api_key[:15]}... Remaining: {balance}")
                return True, {"type": "prepaid_key", "balance": balance, "key": api_key, "cost": cost_sats}
            else:
                print(f"🔑 [PrepaidKey] Spend failed: {msg}")
                return False, {"status": 403, "error": msg, "type": "prepaid_key_insufficient"}

        # Real x402 payment (from Coinbase Facilitator)
        print(f"⚡ [x402] Payment verified by middleware — bypassing auth")
        
        # Did they pay for a session burst?
        minted_macaroon = None
        session_deposit = request.headers.get("X-Sovereign-Session-Deposit")
        if session_deposit:
            try:
                deposit_sats = int(session_deposit)
                # Cap it just in case
                deposit_sats = min(deposit_sats, 100000)
                
                # We mint a macroon, deducting the exact cost of the FIRST call immediately
                remaining = deposit_sats - cost_sats
                if remaining >= 0:
                    minted_macaroon, resulting_balance = MINT.create_session(amount_sats=remaining)
                    print(f"⚡ [x402 Session] Minted Macaroon w/ {resulting_balance} sats")
            except ValueError:
                pass
                
        return True, {"type": "x402", "payment_payload": payment_payload, "minted_macaroon": minted_macaroon}
    
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

    # CASE A: BEARER TOKEN (Macaroon) -> Usually caught by FAST LANE in middleware, but checked here as fallback
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        valid, balance, msg = MINT.verify_and_spend(token, cost_sats)
        if valid:
            return True, {"type": "macaroon", "balance": balance, "token": token}
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
async def forward_to_openrouter(payload: dict, route_config: dict, endpoint_path: str = "/v1/chat/completions"):
    if not OPENROUTER_API_KEY:
        return JSONResponse(status_code=500, content={"error": "No API Key"})
    backend_payload = payload.copy()
    backend_payload["model"] = route_config["backend_model"]
    if "max_tokens" not in backend_payload:
        backend_payload["max_tokens"] = MAX_TOKENS_CAP
    else:
        # Enforce ceilings and floors
        if backend_payload["max_tokens"] > MAX_TOKENS_CAP:
            backend_payload["max_tokens"] = MAX_TOKENS_CAP
        elif backend_payload["max_tokens"] < 16:
            backend_payload["max_tokens"] = 16

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_TITLE
    }
    
    # Rewrite the hardcoded openrouter backend_url based on the requested endpoint
    backend_url = route_config["backend_url"]
    if endpoint_path and endpoint_path != "/v1/chat/completions":
        backend_url = backend_url.replace("/v1/chat/completions", endpoint_path)
    
    # For streaming, we need to manually proxy to read headers early or just respond 
    # Actually, httpx is fine with Response(stream=...). But standard streaming response
    # requires StreamingResponse or proxying.
    # OpenRouter handles stream via the same endpoint.
    
    async with httpx.AsyncClient() as client:
        try:
            # We defer returning the Response object back so the caller can inject headers
            # into the initial HTTP headers (even for streams).
            
            # Since fastAPI proxy streaming can be complex, we'll return a raw httpx stream
            # if stream=True, but for simplicity here we just use the fastAPI Response
            
            req = client.build_request("POST", backend_url, json=backend_payload, headers=headers)
            res = await client.send(req, stream=payload.get("stream", False))
            
            from fastapi.responses import StreamingResponse
            if payload.get("stream", False):
                return StreamingResponse(
                    res.aiter_raw(),
                    status_code=res.status_code,
                    media_type=res.headers.get("content-type")
                )
            else:
                await res.aread()
                return Response(
                    content=res.content,
                    status_code=res.status_code,
                    media_type=res.headers.get("content-type")
                )
        except Exception as e:
            return JSONResponse(status_code=502, content={"error": f"Upstream Error: {e}"})


# --- ENDPOINTS ---
@app.post("/v1/chat/completions", dependencies=[Depends(rl_standard)])
@app.post("/v1/completions", dependencies=[Depends(rl_standard)])
@app.post("/v1/responses", dependencies=[Depends(rl_standard)])
async def chat_completions(request: Request):
    endpoint_path = request.url.path
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    requested_model = body.get("model") or ""
    
    # Model ID aliasing: resolve bare names and foreign prefixes
    candidate = requested_model
    if "/" not in candidate:
        candidate = f"sovereign/{candidate}"
    elif candidate.startswith("openai/"):
        candidate = "sovereign/" + candidate.split("/", 1)[1]
    elif candidate.startswith("anthropic/"):
        candidate = "sovereign/" + candidate.split("/", 1)[1]
    
    if candidate not in MODEL_ROUTER:
        raise HTTPException(status_code=404, detail=f"Model not found: {requested_model}")
    route_config = MODEL_ROUTER[candidate]

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
        
        # === 403: REPLAY ATTACK / TOKEN SPENT / EXPIRED ===
        if isinstance(auth_data, str) and ("Spent" in auth_data or "expired" in auth_data or "revoked" in auth_data):
            # Also fallback to a clean 402 so they can just pay again if they want
            return JSONResponse(
                status_code=402, 
                content={"error": auth_data},
                headers={
                    "Payment-Required": "true",
                    "WWW-Authenticate": f'L402 macaroon="", invoice="", amount="{route_config["price_sats"]}", pay_to="{X402_PAY_TO}", network="{X402_NETWORK}"'
                }
            )
        
        # === 403: PREPAID KEY INSUFFICIENT BALANCE ===
        if isinstance(auth_data, dict) and auth_data.get("type") == "prepaid_key_insufficient":
            return JSONResponse(
                status_code=403,
                content={"error": auth_data.get("error"), "topup_url": "/v1/key/topup"},
            )

        # === 402: INSUFFICIENT FUNDS (Top-Up Flow) ===
        if isinstance(auth_data, str) and "Insufficient Funds" in auth_data:
            # Here, the token is valid but empty.
            # In V6, if empty, the agent should just fall back to standard 402.
            # They just pay exactly what it costs from their wallet. 
            return JSONResponse(
                status_code=402, 
                content={"error": "Insufficient Funds in Macaroon"},
                headers={
                    "Payment-Required": "true",
                    "WWW-Authenticate": f'L402 macaroon="", invoice="", amount="{route_config["price_sats"]}", pay_to="{X402_PAY_TO}", network="{X402_NETWORK}"'
                }
            )

        # === 402: LEGACY L402 INVOICE (If x402 disabled) ===
        p_hash, invoice = await generate_real_invoice(route_config["price_sats"], f"Sovereign: {requested_model}")
        return JSONResponse(
            status_code=402,
            content={"error": "Payment Required", "invoice": invoice, "price_sats": route_config["price_sats"]},
            headers={"WWW-Authenticate": "L402 token", "X-L402-Invoice": invoice}
        )

    # Execute
    response = await forward_to_openrouter(body, route_config, endpoint_path)

    # V6 BALANCES: Inject Headers
    # Case A: Existing Session
    if isinstance(auth_data, dict) and auth_data.get("type") == "macaroon":
        response.headers["X-Sovereign-Macaroon-Balance"] = str(auth_data.get("balance", 0))

    # Case B: Newly Minted Session
    if isinstance(auth_data, dict) and auth_data.get("type") == "x402":
        minted_macaroon = auth_data.get("minted_macaroon")
        if minted_macaroon:
            response.headers["X-Sovereign-Macaroon"] = minted_macaroon

        payload = auth_data.get("payment_payload")
        if payload:
            try:
                receipt_json = json.dumps(payload if isinstance(payload, dict) else str(payload))
                encoded_receipt = base64.b64encode(receipt_json.encode()).decode()
                response.headers["PAYMENT-RESPONSE"] = encoded_receipt
            except Exception:
                pass  # Non-critical

    # Case C: Prepaid Key
    if isinstance(auth_data, dict) and auth_data.get("type") == "prepaid_key":
        response.headers["X-Sovereign-Balance"] = str(auth_data.get("balance", 0))
        response.headers["X-Sovereign-Cost"] = str(auth_data.get("cost", 0))
        remaining_calls = auth_data.get("balance", 0) // max(auth_data.get("cost", 1), 1)
        response.headers["X-RateLimit-Remaining"] = str(remaining_calls)

    return response


@app.post("/v1/key/topup")
async def key_topup(request: Request):
    """Fund your API key via x402 payment. Returns new balance."""
    payment_payload = getattr(request.state, "payment_payload", None)
    if not payment_payload:
        raise HTTPException(status_code=402, detail="Payment Required")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON. Send {\"api_key\": \"sk-sov-...\"}")

    api_key = body.get("api_key")
    idempotency_key = body.get("idempotency_key", f"topup_{secrets.token_hex(16)}")

    if not api_key or not api_key.startswith("sk-sov-"):
        raise HTTPException(status_code=400, detail="Valid api_key required (sk-sov-...)")

    if not validate_key(api_key):
        raise HTTPException(status_code=404, detail="API key not found. Register first: POST /v1/register")

    credits = 100000  # $1.00 x402 payment = 100k credits
    receipt = str(payment_payload) if payment_payload else None
    new_balance = MINT.topup_key(api_key, credits, idempotency_key, receipt)

    return {
        "status": "success",
        "api_key": f"{api_key[:10]}...{api_key[-4:]}",
        "credits_added": credits,
        "balance": new_balance,
        "idempotency_key": idempotency_key
    }


@app.get("/v1/key/balance")
async def key_balance(request: Request):
    """Check balance for a prepaid API key."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer sk-sov-"):
        raise HTTPException(status_code=401, detail="Send: Authorization: Bearer sk-sov-...")

    api_key = auth_header.split(" ", 1)[1]
    if not validate_key(api_key):
        raise HTTPException(status_code=404, detail="API key not found")

    info = MINT.get_key_balance(api_key)
    if not info:
        return {"balance": 0, "funded": False, "topup_url": "/v1/key/topup"}

    return {
        "balance": info["balance_credits"],
        "total_funded": info["total_funded"],
        "total_spent": info["total_spent"],
        "spend_cap_day": info["spend_cap_day"],
        "funded": info["balance_credits"] > 0
    }


@app.post("/v1/macaroon/revoke")
async def revoke_macaroon(request: Request):
    """Instantly revokes a Macaroon session."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer Macaroon required")
        
    token_str = auth_header.split(" ", 1)[1]
    
    try:
        m = Macaroon.deserialize(token_str)
        m_id = m.identifier
        if isinstance(m_id, bytes):
            m_id = m_id.decode('utf-8')
            
        v = Verifier()
        if not v.verify(m, MINT_SECRET): 
            raise HTTPException(status_code=401, detail="Invalid Signature")

        with MINT._get_db() as conn:
            conn.execute("UPDATE macaroons SET revoked = 1 WHERE id = ?", (m_id,))
            conn.commit()
            
        return {"status": "success", "message": "Macaroon revoked"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/models")
async def list_models():
    return {"data": [{"id": k, "price": v["price_sats"]} for k, v in MODEL_ROUTER.items()]}


@app.get("/v1/models/{model_id:path}")
async def get_model(model_id: str):
    """Specific model lookup (supports namespaced IDs)."""
    if model_id not in MODEL_ROUTER:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"id": model_id, "price": MODEL_ROUTER[model_id]["price_sats"]}





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

        print("⚠️ [topup] Reached topup endpoint without payment_payload in state")

        raise HTTPException(status_code=402, detail="Payment Required")

        

    print(f"💰 [topup] Payment verified successfully: {payment_payload}")

    

    # 2. Mint Token

    # $1.00 ~= 100,000 sats (rough approximation for simplicity or use oracle)

    # Since x402 price checks are strict ($1.00), we credit explicitly.

    credits_sats = 100000 

    

    # Generate macaroon (reuse existing mint logic via verify_and_spend hack or direct mint)

    # We need to ACCESS the MINT instance directly. 

    # MINT is initialized later in the file. We rely on MINT global.

    

    try:

        # Mint new macaroon with 100k sats using MINT.create_session (persists to SQLite)

        serialized, resulting_balance = MINT.create_session(amount_sats=credits_sats)

        print(f"💰 [topup] Minted session with {resulting_balance} sats")

        

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









# --- SELF-REGISTRATION (AUTONOMOUS) ---

@app.post("/v1/register", dependencies=[Depends(rl_strict)])

async def register_agent(request: Request):

    """

    Allow an agent to self-register and get an API key.

    No human required.

    """

    # Robust JSON parsing: handle Windows BOM, trailing newlines, charset issues
    try:
        raw_body = await request.body()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Could not read request body."})

    if not raw_body or len(raw_body.strip()) == 0:
        return JSONResponse(status_code=400, content={
            "error": "Empty body. Send JSON: {\"name\": \"my-agent\"}",
            "example": "curl -X POST https://api.sovereign-api.com/v1/register -H \"Content-Type: application/json\" -d \"{\\\"name\\\": \\\"my-agent\\\"}\""
        })

    # Strip BOM and whitespace (Windows echo adds BOM + trailing \r\n)
    body_str = raw_body.strip()
    if body_str.startswith(b'\xef\xbb\xbf'):
        body_str = body_str[3:]  # UTF-8 BOM
    body_str = body_str.strip()

    try:
        body = json.loads(body_str)
    except (json.JSONDecodeError, ValueError) as e:
        return JSONResponse(status_code=400, content={
            "error": f"Invalid JSON: {str(e)[:100]}",
            "received_bytes": len(raw_body),
            "hint": "On Windows cmd.exe, use: curl -X POST URL -H \"Content-Type: application/json\" -d \"{\\\"name\\\": \\\"my-agent\\\"}\"",
        })

    name = body.get('name') if isinstance(body, dict) else None
    description = body.get('description', 'Self-registered agent') if isinstance(body, dict) else 'Self-registered agent'

    if not name:
        return JSONResponse(status_code=400, content={
            "error": "Missing 'name' field.",
            "schema": {"name": "string (required)", "description": "string (optional)"}
        })

    from api_key_registry import create_key

    api_key, msg = create_key(name, description)

    if not api_key:
        raise HTTPException(status_code=409, detail=msg)

    return {
        "api_key": api_key,
        "agent_name": name,
        "gateway_wallet": os.getenv("X402_WALLET_ADDRESS") or os.getenv("MY_WALLET_ADDRESS") or "0x0000000000000000000000000000000000000000",
        "message": "Identity established. You are now sovereign.",
        "next_steps": {
            "1_check_balance": "GET /v1/key/balance (Authorization: Bearer sk-sov-...)",
            "2_fund_key": "POST /v1/key/topup with x402 payment",
            "3_use": "POST /v1/chat/completions (Authorization: Bearer sk-sov-...)"
        }
    }


@app.get("/v1/register/ping")
async def register_ping():
    """Health check: verify POST body parsing works through WAF."""
    return {"status": "ok", "endpoint": "/v1/register", "method": "POST", "body": '{"name": "your-agent-name"}'}






@app.get("/skill.md")
async def get_skill():
    return FileResponse("landing/skill.md")

@app.get("/llm.txt")
async def get_llm():
    return FileResponse("landing/llm.txt")

@app.get("/robots.txt")
async def get_robots():
    return FileResponse("landing/robots.txt")

@app.get("/sitemap.xml")
async def get_sitemap():
    return FileResponse("landing/sitemap.xml")

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
