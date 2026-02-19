Åòimport time
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
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pymacaroons import Macaroon, Verifier
from api_key_registry import validate_key, get_agent_name, increment_usage

app = FastAPI(title="Sovereign AI Gateway (Phase 7: Decoupled Identity + Fuel)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Landing page route
LANDING_PATH = Path(__file__).parent / "landing" / "index.html"
SKILL_PATH = Path(__file__).parent / "landing" / "skill.md"

@app.get("/", response_class=HTMLResponse)
async def landing_page():
    if LANDING_PATH.exists():
        return HTMLResponse(content=LANDING_PATH.read_text(encoding='utf-8'), status_code=200)
    return HTMLResponse(content="<h1>Sovereign Intelligence API</h1><p>Visit <a href='/v1/models'>/v1/models</a></p>", status_code=200)

@app.get("/skill.md")
async def skill_file():
    if SKILL_PATH.exists():
        return Response(content=SKILL_PATH.read_text(encoding='utf-8'), media_type="text/markdown")
    return Response(content="# Sovereign Intelligence API\nSkill file not found.", media_type="text/markdown")

# --- BLOG ENGINE ---
import markdown as md

BLOG_DIR = Path(__file__).parent / "landing" / "blog"

BLOG_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} â€” Sovereign Intelligence API Blog</title>
    <meta name="description" content="{description}">
    <meta name="keywords" content="{keywords}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://api.sovereign-api.com/blog/{slug}">
    <link rel="alternate" type="application/json" href="https://api.sovereign-api.com/openapi.json">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');
        :root {{
            --bg-deep: #050a14;
            --bg-card: #0a1628;
            --cyan: #00ffd5;
            --text-primary: #e8ecf1;
            --text-secondary: #8899aa;
            --border: rgba(0,255,213,0.15);
            --font-sans: 'Inter', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: var(--bg-deep); color: var(--text-primary); font-family: var(--font-sans); line-height: 1.8; }}
        .blog-nav {{ padding: 20px 40px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
        .blog-nav a {{ color: var(--cyan); text-decoration: none; font-family: var(--font-mono); font-size: 14px; }}
        .blog-nav a:hover {{ text-decoration: underline; }}
        .blog-container {{ max-width: 800px; margin: 0 auto; padding: 60px 20px; }}
        .blog-meta {{ color: var(--text-secondary); font-size: 13px; font-family: var(--font-mono); margin-bottom: 40px; border-bottom: 1px solid var(--border); padding-bottom: 20px; }}
        h1 {{ font-size: 2.2em; margin-bottom: 10px; background: linear-gradient(135deg, var(--cyan), #00aaff); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }}
        h2 {{ font-size: 1.5em; margin-top: 48px; margin-bottom: 16px; color: var(--cyan); }}
        h3 {{ font-size: 1.2em; margin-top: 32px; margin-bottom: 12px; color: var(--text-primary); }}
        p {{ margin-bottom: 16px; color: var(--text-secondary); }}
        a {{ color: var(--cyan); }}
        ul, ol {{ margin-bottom: 16px; padding-left: 24px; color: var(--text-secondary); }}
        li {{ margin-bottom: 8px; }}
        strong {{ color: var(--text-primary); }}
        code {{ font-family: var(--font-mono); background: #0d1b2a; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: var(--cyan); }}
        pre {{ background: #0d1b2a; border: 1px solid var(--border); border-radius: 10px; padding: 20px; overflow-x: auto; margin-bottom: 24px; }}
        pre code {{ background: none; padding: 0; font-size: 13px; color: var(--text-primary); }}
        blockquote {{ border-left: 3px solid var(--cyan); padding: 12px 20px; margin: 20px 0; background: rgba(0,255,213,0.03); color: var(--text-secondary); font-style: italic; border-radius: 0 8px 8px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: var(--bg-card); color: var(--cyan); padding: 12px; text-align: left; font-family: var(--font-mono); font-size: 13px; border: 1px solid var(--border); }}
        td {{ padding: 10px 12px; border: 1px solid var(--border); color: var(--text-secondary); font-size: 14px; }}
        tr:hover td {{ background: rgba(0,255,213,0.03); }}
        hr {{ border: none; border-top: 1px solid var(--border); margin: 40px 0; }}
        img {{ max-width: 100%; border-radius: 10px; }}
        .blog-footer {{ text-align: center; padding: 40px; color: var(--text-secondary); font-size: 13px; border-top: 1px solid var(--border); margin-top: 60px; }}
    </style>
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": "{title}",
        "keywords": "{keywords}",
        "datePublished": "{date}",
        "author": {{"@type": "Organization", "name": "Sovereign Intelligence"}},
        "publisher": {{"@type": "Organization", "name": "Sovereign Intelligence API", "url": "https://api.sovereign-api.com"}},
        "mainEntityOfPage": "https://api.sovereign-api.com/blog/{slug}"
    }}
    </script>
</head>
<body>
    <nav class="blog-nav">
        <a href="/">âš¡ Sovereign API</a>
        <div>
            <a href="/blog">Blog</a> &nbsp;|&nbsp;
            <a href="/docs">Docs</a> &nbsp;|&nbsp;
            <a href="/skill.md">skill.md</a>
        </div>
    </nav>
    <article class="blog-container">
        <div class="blog-meta">{date} &nbsp;Â·&nbsp; {reading_time} min read &nbsp;Â·&nbsp; {keywords}</div>
        {content}
    </article>
    <footer class="blog-footer">
        Sovereign Intelligence API â€” Self-Sustaining Compute for AI Agents<br>
        <a href="/">Home</a> Â· <a href="/blog">Blog</a> Â· <a href="/skill.md">skill.md</a> Â· <a href="/docs">API Docs</a>
    </footer>
</body>
</html>"""

BLOG_INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog â€” Sovereign Intelligence API</title>
    <meta name="description" content="Technical articles on autonomous AI agents, self-funding compute, and the future of agent sovereignty.">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');
        :root {{
            --bg-deep: #050a14;
            --bg-card: #0a1628;
            --cyan: #00ffd5;
            --text-primary: #e8ecf1;
            --text-secondary: #8899aa;
            --border: rgba(0,255,213,0.15);
            --font-sans: 'Inter', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: var(--bg-deep); color: var(--text-primary); font-family: var(--font-sans); }}
        .blog-nav {{ padding: 20px 40px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
        .blog-nav a {{ color: var(--cyan); text-decoration: none; font-family: var(--font-mono); font-size: 14px; }}
        .container {{ max-width: 800px; margin: 0 auto; padding: 60px 20px; }}
        h1 {{ font-size: 2.2em; margin-bottom: 10px; background: linear-gradient(135deg, var(--cyan), #00aaff); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }}
        .subtitle {{ color: var(--text-secondary); margin-bottom: 50px; font-size: 16px; }}
        .article-card {{ background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 28px; margin-bottom: 20px; transition: border-color 0.3s, transform 0.2s; }}
        .article-card:hover {{ border-color: var(--cyan); transform: translateY(-2px); }}
        .article-card a {{ text-decoration: none; }}
        .article-card h2 {{ color: var(--text-primary); font-size: 1.3em; margin-bottom: 8px; }}
        .article-card p {{ color: var(--text-secondary); font-size: 14px; line-height: 1.6; }}
        .article-card .meta {{ color: var(--text-secondary); font-size: 12px; font-family: var(--font-mono); margin-top: 12px; }}
        .blog-footer {{ text-align: center; padding: 40px; color: var(--text-secondary); font-size: 13px; border-top: 1px solid var(--border); margin-top: 60px; }}
        .blog-footer a {{ color: var(--cyan); }}
    </style>
</head>
<body>
    <nav class="blog-nav">
        <a href="/">âš¡ Sovereign API</a>
        <div>
            <a href="/blog">Blog</a> &nbsp;|&nbsp;
            <a href="/docs">Docs</a> &nbsp;|&nbsp;
            <a href="/skill.md">skill.md</a>
        </div>
    </nav>
    <div class="container">
        <h1>Sovereign Blog</h1>
        <p class="subtitle">Technical articles on autonomous AI, self-funding compute, and the future of agent sovereignty.</p>
        {articles}
    </div>
    <footer class="blog-footer">
        Sovereign Intelligence API â€” Self-Sustaining Compute for AI Agents<br>
        <a href="/">Home</a> Â· <a href="/blog">Blog</a> Â· <a href="/skill.md">skill.md</a> Â· <a href="/docs">API Docs</a>
    </footer>
</body>
</html>"""


def parse_frontmatter(text):
    """Parse YAML-like frontmatter from markdown."""
    meta = {}
    content = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    meta[key.strip()] = val.strip().strip('"')
            content = parts[2]
    return meta, content


def get_blog_articles():
    """Scan blog dir for all markdown articles."""
    articles = []
    if not BLOG_DIR.exists():
        return articles
    for f in sorted(BLOG_DIR.glob("*.md"), reverse=True):
        text = f.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(text)
        articles.append({
            "slug": f.stem,
            "title": meta.get("title", f.stem.replace("-", " ").title()),
            "date": meta.get("date", ""),
            "keywords": meta.get("keywords", ""),
            "description": meta.get("title", ""),
        })
    return articles


@app.get("/blog", response_class=HTMLResponse)
async def blog_index():
    articles = get_blog_articles()
    cards = ""
    for a in articles:
        cards += f"""
        <div class="article-card">
            <a href="/blog/{a['slug']}">
                <h2>{a['title']}</h2>
                <p>{a['description']}</p>
                <div class="meta">{a['date']} Â· {a['keywords'][:80]}</div>
            </a>
        </div>"""
    return HTMLResponse(content=BLOG_INDEX_TEMPLATE.format(articles=cards), status_code=200)


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post(slug: str):
    filepath = BLOG_DIR / f"{slug}.md"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Article not found")

    text = filepath.read_text(encoding="utf-8")
    meta, content = parse_frontmatter(text)

    html_content = md.markdown(content, extensions=["tables", "fenced_code", "codehilite", "toc"])
    word_count = len(content.split())
    reading_time = max(1, word_count // 200)

    page = BLOG_TEMPLATE.format(
        title=meta.get("title", slug.replace("-", " ").title()),
        description=meta.get("title", ""),
        keywords=meta.get("keywords", ""),
        date=meta.get("date", ""),
        slug=slug,
        reading_time=reading_time,
        content=html_content,
    )
    return HTMLResponse(content=page, status_code=200)

# --- CONFIGURATION ---
ENVIRONMENT = os.getenv("ENVIRONMENT", "DEVELOPMENT")
MAX_TOKENS_CAP = 1024
SITE_URL = "https://api.sovereign-api.com" # Updated to custom domain
MINT_URL = os.environ.get("GATEWAY_MINT_URL", "http://localhost:8000")
SITE_TITLE = "Sovereign Shadow Node"

# Load Secrets
SECURE_DIR = Path(__file__).parent / ".agent" / "secure"
DATA_DIR = Path(__file__).parent / ".agent" / "data"
ALBY_TOKEN_FILE = SECURE_DIR / "alby_token.json"
OPENROUTER_KEY_FILE = SECURE_DIR / "openrouter_key.json"
MINT_SECRET_FILE = SECURE_DIR / "mint_secret.json"

ALBY_ACCESS_TOKEN = None
OPENROUTER_API_KEY = None
MINT_SECRET = "default_unsafe_secret_for_dev"

# Default values (overridden by Env Vars or Files)
ALBY_ACCESS_TOKEN = os.getenv("ALBY_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MINT_SECRET = os.getenv("MINT_SECRET")

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


# --- MIDDLEWARE: DUAL AUTH (Phase 7) ---
async def verify_payment_header(request: Request, cost_sats: int):
    """
    Dual authentication check:
    1. API Key (X-Sovereign-Api-Key) - Identity/License
    2. Macaroon/L402 (Authorization) - Fuel/Credits
    
    Returns:
        401: Invalid/Missing API Key
        402: Valid key but insufficient fuel
        200: Proceed with request
    """
    
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
        print(f"ğŸ”‘ [AUTH] Agent '{agent_name}' authenticated")
    
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

        # === 402: NO TOKEN - GENERATE INVOICE ===
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
        print(f"ğŸ“¬ [MAILBOX] Token stored for {body['identifier'][:10]}...")
        
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
        print(f"ğŸ“¬ [MAILBOX] Token claimed for {tx_hash[:10]}...")
        return {"access_token": token, "status": "claimed"}
    
    # Check if already minted but claimed (or not yet processed)
    if tx_hash in MINT.history:
        return JSONResponse(status_code=410, content={"error": "Token already claimed"})
    
    return JSONResponse(status_code=404, content={"error": "Token not ready. Deposit may still be processing."})


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

    print(f"Sovereign Mint (Universal Mode) starting on {PORT}...")
    try:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    except Exception as e:
        if "10048" in str(e):
            print(f"[CRITICAL] Port {PORT} is STUCK. Run: Stop-Process -Id (Get-NetTCPConnection -LocalPort {PORT}).OwningProcess -Force")
            sys.exit(1)
        raise e
*cascade08 *cascade08
*cascade08
 *cascade08*cascade08 *cascade08*cascade08 *cascade08*cascade08" *cascade08"&*cascade08&( *cascade08(4*cascade084= *cascade08==*cascade08=n *cascade08n~*cascade08~’ *cascade08’ *cascade08 § *cascade08§Û*cascade08Ûâ*cascade08âã *cascade08ãä*cascade08äå *cascade08åæ*cascade08æî *cascade08îñ*cascade08ñò *cascade08òó*cascade08óö *cascade08ö÷*cascade08÷ø *cascade08øû*cascade08ûÿ *cascade08ÿ€*cascade08€‚ *cascade08‚Î*cascade08Î *cascade08‚*cascade08‚„ *cascade08„…*cascade08…† *cascade08†Š*cascade08Š‹ *cascade08‹*cascade08 *cascade08‘*cascade08‘’ *cascade08’“*cascade08“*cascade08Ÿ *cascade08Ÿ¹*cascade08¹• *cascade08•Ò*cascade08Ò 	 *cascade08 	Ë
 *cascade08Ë
‘c*cascade08‘cˆd *cascade08ˆd‘d *cascade08‘d“d*cascade08“d”d*cascade08”dd*cascade08dd *cascade08d£d*cascade08£d¦d *cascade08¦d«d*cascade08«d¬d *cascade08¬d­d*cascade08­d®d *cascade08®d¯d*cascade08¯d°d *cascade08°d±d*cascade08±dºd*cascade08ºd»d *cascade08»d½d*cascade08½d¾d *cascade08¾dÀd*cascade08ÀdÁd *cascade08ÁdÑd*cascade08ÑdÒd *cascade08ÒdÓd*cascade08ÓdÔd *cascade08ÔdÖd*cascade08Öd×d *cascade08×dØd *cascade08ØdÙd*cascade08ÙdÚd *cascade08ÚdÛd*cascade08ÛdÜd *cascade08ÜdŞd*cascade08Şdßd *cascade08ßdàd*cascade08àdãd *cascade08ãdèd*cascade08èdéd *cascade08édêd *cascade08êdíd*cascade08ídîd *cascade08îdñd*cascade08ñdòd *cascade08òdŠe*cascade08Šeşe *cascade08şe´f*cascade08´f g *cascade08 gÔg*cascade08Ôg‹h *cascade08‹hºh*cascade08ºh¼h *cascade08¼h„j*cascade08„jj *cascade08jªj*cascade08ªjÀk *cascade08ÀkÎk*cascade08ÎkĞk *cascade08Ğkëk*cascade08ëk‡m *cascade08‡m‹m *cascade08‹m™m*cascade08™m›m *cascade08›m¯m*cascade08¯m·n *cascade08·nÅn*cascade08Ån‡o *cascade08‡o’o*cascade08’o™o *cascade08™o“p*cascade08“p­p *cascade08­p×p*cascade08×páp *cascade08ápâp*cascade08âpôq *cascade08ôqõq*cascade08õqˆr *cascade08ˆr‘r*cascade08‘rs *cascade08ss*cascade08s¢s *cascade08¢s£s*cascade08£st *cascade08tœt *cascade08œtt*cascade08t¤t *cascade08¤t¦t *cascade08¦t°t*cascade08°t±t *cascade08±t²t*cascade08²t³t *cascade08³t·t *cascade08·tèt*cascade08ètöt *cascade08ötût*cascade08ûtşt *cascade08şt†u*cascade08†u‡u *cascade08‡uˆu*cascade08ˆu‰u *cascade08‰u¥u*cascade08¥u¦u *cascade08¦u¨u*cascade08¨u©u *cascade08©u¯u*cascade08¯u°u *cascade08°u´u*cascade08´uµu *cascade08µuÆu*cascade08ÆuÇu *cascade08Çu•v*cascade08•v–v *cascade08–vœv*cascade08œvv *cascade08v¤v*cascade08¤v¥v *cascade08¥v§v*cascade08§v¨v *cascade08¨vÑv*cascade08ÑvÒv *cascade08Òvİv*cascade08İvßv *cascade08ßváv*cascade08ávâv *cascade08âvêv*cascade08êvëv *cascade08ëvöv*cascade08öv÷v *cascade08÷vw*cascade08w‚w *cascade08‚w‘w*cascade08‘w’w *cascade08’wœw*cascade08œww *cascade08w®w*cascade08®w¯w *cascade08¯w´w*cascade08´w¶w *cascade08¶wÂw*cascade08ÂwÃw *cascade08Ãwæw*cascade08æwçw *cascade08çwğw*cascade08ğwñw *cascade08ñwów*cascade08ówôw *cascade08ôw”x*cascade08”xšx *cascade08šxİy*cascade08İyày *cascade08àyüy*cascade08üyşy *cascade08şyƒz *cascade08ƒz„z *cascade08„z‡z*cascade08‡zˆz *cascade08ˆzz*cascade08zz *cascade08z’z*cascade08’z“z *cascade08“zœz*cascade08œzz *cascade08z¢z *cascade08¢z¬z*cascade08¬zØ{ *cascade08Ø{Ú{ *cascade08Ú{õ|*cascade08õ|ö| *cascade08ö|ƒ}*cascade08ƒ}„} *cascade08„}‡}*cascade08‡}ˆ} *cascade08ˆ}¢~*cascade08¢~£~ *cascade08£~ª~*cascade08ª~«~ *cascade08«~Ç~*cascade08Ç~È~ *cascade08È~ß~*cascade08ß~à~ *cascade08à~„*cascade08„… *cascade08…£*cascade08£¤ *cascade08¤´*cascade08´¶ *cascade08¶º*cascade08º» *cascade08»Æ*cascade08ÆÇ *cascade08Çç*cascade08çè *cascade08èû*cascade08ûü *cascade08üš€ *cascade08š€¦*cascade08¦í *cascade08íî *cascade08îˆ‚*cascade08ˆ‚‚ *cascade08‚²‚*cascade08²‚³‚ *cascade08³‚ø‚*cascade08ø‚ù‚ *cascade08ù‚¢ƒ*cascade08¢ƒ¤ƒ *cascade08¤ƒ¬ƒ*cascade08¬ƒ­ƒ *cascade08­ƒ®ƒ*cascade08®ƒ°ƒ *cascade08°ƒ³ƒ*cascade08³ƒ·ƒ *cascade08·ƒéƒ*cascade08éƒêƒ *cascade08êƒìƒ*cascade08ìƒîƒ *cascade08îƒ‰„ *cascade08‰„š„*cascade08š„Õ„ *cascade08Õ„é„*cascade08é„ş„ *cascade08ş„… *cascade08……*cascade08…Ÿ… *cascade08Ÿ…¦† *cascade08¦†À†*cascade08À†¢‡ *cascade08¢‡¤‡ *cascade08¤‡İˆ*cascade08İˆøˆ *cascade08øˆùˆ *cascade08ùˆ†‰*cascade08†‰‡‰ *cascade08‡‰–‰*cascade08–‰¤‰ *cascade08¤‰¦‰ *cascade08¦‰¯‰*cascade08¯‰°‰ *cascade08°‰³‰*cascade08³‰´‰ *cascade08´‰µ‰*cascade08µ‰¶‰ *cascade08¶‰¸‰*cascade08¸‰º‰ *cascade08º‰Â‰*cascade08Â‰Ä‰ *cascade08Ä‰Å‰*cascade08Å‰Æ‰ *cascade08Æ‰Ç‰*cascade08Ç‰È‰ *cascade08È‰É‰*cascade08É‰Ê‰ *cascade08Ê‰Ò‰*cascade08Ò‰Ô‰ *cascade08Ô‰Ø‰*cascade08Ø‰Ù‰ *cascade08Ù‰Ş‰*cascade08Ş‰ß‰ *cascade08ß‰ğ‰*cascade08ğ‰ñ‰ *cascade08ñ‰ù‰*cascade08ù‰ú‰ *cascade08ú‰ş‰*cascade08ş‰ÿ‰ *cascade08ÿ‰‰Š *cascade08‰ŠŠŠ*cascade08ŠŠŠ *cascade08ŠŸŠ *cascade08ŸŠ Š*cascade08 Š¡Š *cascade08¡Š£Š*cascade08£Š¤Š *cascade08¤Š¨Š*cascade08¨Š©Š *cascade08©ŠªŠ*cascade08ªŠ«Š *cascade08«Š°Š*cascade08°Š±Š *cascade08±Š¶Š*cascade08¶Š¸Š *cascade08¸Š¹Š*cascade08¹ŠºŠ *cascade08ºŠÈŠ*cascade08ÈŠ×Š *cascade08×ŠÚŠ*cascade08ÚŠÛŠ *cascade08ÛŠàŠ*cascade08àŠáŠ *cascade08áŠäŠ*cascade08äŠåŠ *cascade08åŠìŠ*cascade08ìŠîŠ *cascade08îŠòŠ*cascade08òŠóŠ *cascade08óŠôŠ*cascade08ôŠõŠ *cascade08õŠùŠ*cascade08ùŠúŠ *cascade08úŠ€‹*cascade08€‹‹ *cascade08‹‡‹*cascade08‡‹ˆ‹ *cascade08ˆ‹‰‹*cascade08‰‹‹‹ *cascade08‹‹à‹*cascade08à‹á‹*cascade08á‹â‹ *cascade08â‹é‹*cascade08é‹ê‹ *cascade08ê‹ÿ‹*cascade08ÿ‹„Œ *cascade08„Œ—Œ*cascade08—Œ¦Œ *cascade08¦Œ´Œ*cascade08´ŒµŒ *cascade08µŒÇŒ*cascade08ÇŒÈŒ *cascade08ÈŒÊŒ*cascade08ÊŒËŒ *cascade08ËŒÎŒ*cascade08ÎŒÏŒ *cascade08ÏŒÑŒ*cascade08ÑŒÒŒ *cascade08ÒŒÔŒ *cascade08ÔŒÛŒ*cascade08ÛŒİŒ *cascade08İŒßŒ*cascade08ßŒáŒ *cascade08áŒåŒ*cascade08åŒñŒ *cascade08ñŒôŒ *cascade08ôŒöŒ*cascade08öŒ÷Œ *cascade08÷ŒúŒ*cascade08úŒûŒ *cascade08ûŒıŒ*cascade08ıŒÿŒ *cascade08ÿŒˆ*cascade08ˆ‰ *cascade08‰Œ*cascade08Œ *cascade08*cascade08 *cascade08“*cascade08“” *cascade08”–*cascade08–˜ *cascade08˜œ*cascade08œ° *cascade08°µ*cascade08µ· *cascade08·¹*cascade08¹º *cascade08º½*cascade08½¿ *cascade08¿Â*cascade08ÂÄ *cascade08ÄÇ*cascade08ÇÈ *cascade08ÈÍ*cascade08ÍÎ *cascade08ÎÓ*cascade08ÓÔ *cascade08ÔÕ*cascade08ÕÖ *cascade08ÖØ*cascade08ØÚ *cascade08ÚŞ*cascade08Şà *cascade08àå*cascade08åæ *cascade08æë*cascade08ëí *cascade08íû *cascade08û—*cascade08—™ *cascade08™¤*cascade08¤¥ *cascade08¥¯*cascade08¯° *cascade08°¼*cascade08¼½ *cascade08½Æ*cascade08ÆÈ *cascade08ÈË*cascade08ËÍ *cascade08ÍÓ*cascade08Óç *cascade08ç„*cascade08„“ *cascade08“š*cascade08šœ *cascade08œ¤*cascade08¤² *cascade08²¸*cascade08¸¹ *cascade08¹º*cascade08º» *cascade08»½*cascade08½¿ *cascade08¿À*cascade08ÀÁ *cascade08ÁÂ*cascade08ÂÅ *cascade08ÅÈ*cascade08ÈÙ *cascade08ÙÛ*cascade08ÛÜ *cascade08ÜŞ*cascade08Şã *cascade08ãå*cascade08åæ *cascade08æë*cascade08ëì *cascade08ìğ*cascade08ğñ *cascade08ñò*cascade08òó *cascade08óô*cascade08ôö *cascade08ö÷*cascade08÷‰ *cascade08‰Œ*cascade08Œ *cascade08‘*cascade08‘“ *cascade08“”*cascade08”• *cascade08•–*cascade08–— *cascade08—œ*cascade08œ *cascade08Ÿ*cascade08Ÿ¢ *cascade08¢£*cascade08£¥ *cascade08¥§*cascade08§¨ *cascade08¨«*cascade08«¬ *cascade08¬¯*cascade08¯ÿ *cascade08ÿ€‘ *cascade08€‘‘*cascade08‘‚‘ *cascade08‚‘‘*cascade08‘‘ *cascade08‘”‘*cascade08”‘’ *cascade08’Ÿ’*cascade08Ÿ’ù“ *cascade08ù“û“ *cascade08û“Œ”*cascade08Œ”” *cascade08””*cascade08”” *cascade08”¨”*cascade08¨”©” *cascade08©”Á”*cascade08Á”Â” *cascade08Â”É”*cascade08É”Ì” *cascade08Ì”ï”*cascade08ï”ò” *cascade08ò”ù”*cascade08ù”ú” *cascade08ú”€•*cascade08€•• *cascade08•„•*cascade08„•‡• *cascade08‡•Ğ•*cascade08Ğ•Ñ• *cascade08Ñ•Ù•*cascade08Ù•Û• *cascade08Û•à•*cascade08à•á• *cascade08á•î•*cascade08î•ï• *cascade08ï•ú•*cascade08ú•û• *cascade08û•ˆ—*cascade08ˆ—Š— *cascade08Š—»—*cascade08»—¼— *cascade08¼—à—*cascade08à—á— *cascade08á—ì—*cascade08ì—í— *cascade08í—˜*cascade08˜ƒ˜ *cascade08ƒ˜‰˜*cascade08‰˜Š˜ *cascade08Š˜ ˜*cascade08 ˜¢˜ *cascade08¢˜¸˜*cascade08¸˜¹˜ *cascade08¹˜»˜*cascade08»˜¼˜ *cascade08¼˜½˜*cascade08½˜¿˜ *cascade08¿˜×˜*cascade08×˜Ù˜ *cascade08Ù˜ñ˜*cascade08ñ˜®Ÿ *cascade08®Ÿ†  *cascade08†  *cascade08 Í¢ *cascade08Í¢Ï¢*cascade08Ï¢Ğ¢ *cascade08Ğ¢Ó¢*cascade08Ó¢Ÿ£ *cascade08Ÿ£¢£*cascade08¢£¸£ *cascade08¸£º£*cascade08º£À£ *cascade08À£Ê£ *cascade08Ê£Õ£*cascade08Õ£Ö£ *cascade08Ö£à£*cascade08à£ö£ *cascade08ö£ı£*cascade08ı£•¤ *cascade08•¤¥¤*cascade08¥¤§¤ *cascade08§¤˜¬*cascade08˜¬è¬ *cascade08è¬ë¬*cascade08ë¬ì¬ *cascade08ì¬÷¬*cascade08÷¬ø¬ *cascade08ø¬ù¬*cascade08ù¬ú¬ *cascade08ú¬‡­*cascade08‡­ˆ­ *cascade08ˆ­­*cascade08­­ *cascade08­“­*cascade08“­”­ *cascade08”­É­*cascade08É­â­ *cascade08â­é­*cascade08é­÷­ *cascade08÷­ÿ­*cascade08ÿ­€® *cascade08€®ˆ®*cascade08ˆ®‰® *cascade08‰®‘®*cascade08‘®’® *cascade08’®¢®*cascade08¢®¤® *cascade08¤®¯®*cascade08¯®°® *cascade08°®±®*cascade08±®³® *cascade08³®¹®*cascade08¹®º® *cascade08º®Á®*cascade08Á®Â® *cascade08Â®É®*cascade08É®Ê® *cascade08Ê®Ø®*cascade08Ø®Ù® *cascade08Ù®ê®*cascade08ê®ë® *cascade08ë®†¯*cascade08†¯‡¯ *cascade08‡¯Ô¯*cascade08Ô¯Õ¯ *cascade08Õ¯Ú¯*cascade08Ú¯Û¯ *cascade08Û¯ò¯*cascade08ò¯ö¯ *cascade08ö¯ù¯*cascade08ù¯ú¯ *cascade08ú¯…°*cascade08…°‹° *cascade08‹°—°*cascade08—°˜° *cascade08˜° °*cascade08 °¢° *cascade08¢°¥°*cascade08¥°©° *cascade08©°ª°*cascade08ª°°° *cascade08°°´°*cascade08´°ß° *cascade08ß°â°*cascade08â°ê° *cascade08ê°ë°*cascade08ë°‰± *cascade08‰±‹±*cascade08‹±™± *cascade08™±œ±*cascade08œ±± *cascade08±±*cascade08±Ÿ± *cascade08Ÿ± ±*cascade08 ±¡± *cascade08¡±£±*cascade08£±¯± *cascade08¯±°± *cascade08°±±± *cascade08±±Ş± *cascade08Ş±á±*cascade08á±î± *cascade08î±ï±*cascade08ï±Œ² *cascade08Œ²² *cascade08²²*cascade08²Ÿ² *cascade08Ÿ²¢²*cascade08¢²£² *cascade08£²¥²*cascade08¥²¦² *cascade08¦²«²*cascade08«²¬² *cascade08¬²°²*cascade08°²±² *cascade08±²²²*cascade08²²¾² *cascade08¾²Ä² *cascade08Ä²Æ²*cascade08Æ²É² *cascade08É²Ê²*cascade08Ê²Ë² *cascade08Ë²Ì² *cascade08Ì²Î²*cascade08Î²Ö² *cascade08Ö²Ø² *cascade08Ø²Û² *cascade08Û²İ² *cascade08İ²Ş²*cascade08Ş²à² *cascade08à²â²*cascade08â²ã² *cascade08ã²ê²*cascade08ê²ë² *cascade08ë²ú²*cascade08ú²û² *cascade08û²ü²*cascade08ü²ş² *cascade08ş²Š³ *cascade08Š³’³*cascade08’³–³ *cascade08–³—³ *cascade08—³š³*cascade08š³›³ *cascade08›³Ÿ³*cascade08Ÿ³ ³ *cascade08 ³£³*cascade08£³¨³ *cascade08¨³©³*cascade08©³ª³ *cascade08ª³³³*cascade08³³»³ *cascade08»³Ğ³*cascade08Ğ³Ø³ *cascade08Ø³Û³ *cascade08Û³Ş³ *cascade08Ş³à³*cascade08à³á³ *cascade08á³ä³*cascade08ä³å³ *cascade08å³æ³*cascade08æ³è³ *cascade08è³ê³*cascade08ê³ë³ *cascade08ë³î³*cascade08î³ï³ *cascade08ï³ó³*cascade08ó³ô³ *cascade08ô³ö³*cascade08ö³÷³ *cascade08÷³ù³*cascade08ù³ú³ *cascade08ú³ü³*cascade08ü³ı³ *cascade08ı³ÿ³*cascade08ÿ³€´ *cascade08€´´*cascade08´´ *cascade08´‘´ *cascade08‘´’´ *cascade08’´”´ *cascade08”´˜´*cascade08˜´œ´ *cascade08œ´¤´*cascade08¤´«´ *cascade08«´®´*cascade08®´±´ *cascade08±´²´*cascade08²´³´ *cascade08³´¹´*cascade08¹´º´ *cascade08º´¾´*cascade08¾´¿´ *cascade08¿´Ä´*cascade08Ä´Å´ *cascade08Å´Æ´*cascade08Æ´È´ *cascade08È´É´*cascade08É´Ğ´ *cascade08Ğ´Ñ´ *cascade08Ñ´×´ *cascade08×´Ú´*cascade08Ú´Û´ *cascade08Û´Ş´*cascade08Ş´ß´ *cascade08ß´á´*cascade08á´â´ *cascade08â´ä´*cascade08ä´å´ *cascade08å´ç´*cascade08ç´è´ *cascade08è´ì´*cascade08ì´í´ *cascade08í´î´*cascade08î´ô´ *cascade08ô´û´*cascade08û´ş´ *cascade08ş´ÿ´ *cascade08ÿ´€µ *cascade08€µµ*cascade08µŒµ *cascade08Œµµ*cascade08µµ *cascade08µµ *cascade08µµ*cascade08µ‘µ *cascade08‘µŸµ *cascade08Ÿµ µ *cascade08 µ§µ *cascade08§µ«µ*cascade08«µ¯µ *cascade08¯µ²µ*cascade08²µ³µ *cascade08³µ´µ*cascade08´µ·µ *cascade08·µ½µ*cascade08½µ¿µ *cascade08¿µÀµ *cascade08ÀµÂµ*cascade08ÂµÔµ *cascade08ÔµÕµ *cascade08ÕµÖµ*cascade08Öµ×µ *cascade08×µÚµ *cascade08ÚµÛµ*cascade08ÛµÜµ *cascade08Üµİµ*cascade08İµßµ *cascade08ßµäµ*cascade08äµåµ *cascade08åµæµ*cascade08æµçµ *cascade08çµêµ*cascade08êµëµ *cascade08ëµìµ *cascade08ìµîµ*cascade08îµ¸· *cascade08¸·º·*cascade08º·»· *cascade08»·¾·*cascade08¾·Â¹ *cascade08Â¹Â¹*cascade08Â¹Á¿ *cascade08Á¿Â¿*cascade08Â¿Ì¿ *cascade08Ì¿Î¿*cascade08Î¿Ñ¿ *cascade08Ñ¿Ò¿*cascade08Ò¿Ó¿ *cascade08Ó¿Ô¿*cascade08Ô¿Õ¿ *cascade08Õ¿Ö¿*cascade08Ö¿İ¿ *cascade08İ¿ò¿*cascade08ò¿ÉÁ *cascade08ÉÁòÁ*cascade08òÁ¡Ã *cascade08¡Ã§Ã*cascade08§Ã¨Ã *cascade08¨Ã¯Ã*cascade08¯Ã¿Ã *cascade08¿ÃÃÃ*cascade08ÃÃÄÃ *cascade08ÄÃÈÃ*cascade08ÈÃØÃ *cascade08ØÃßÃ*cascade08ßÃîÃ *cascade08îÃŠÄ*cascade08ŠÄ¯Ä *cascade08¯ÄºÄ*cascade08ºÄ»Ä *cascade08»ÄÖÄ*cascade08ÖÄ×Ä *cascade08×ÄØÄ *cascade08ØÄŞÄ*cascade08ŞÄßÄ*cascade08ßÄàÄ*cascade08àÄáÄ *cascade08áÄãÄ*cascade08ãÄäÄ *cascade08äÄëÄ*cascade08ëÄìÄ*cascade08ìÄïÄ*cascade08ïÄğÄ *cascade08ğÄöÄ*cascade08öÄúÄ *cascade08úÄûÄ *cascade08ûÄÿÄ*cascade08ÿÄ€Å *cascade08€ÅÅ *cascade08ÅÅ*cascade08ÅÅ *cascade08Å²Å*cascade08²Å³Å *cascade08³ÅÀÅ*cascade08ÀÅÁÅ *cascade08ÁÅÌÅ*cascade08ÌÅÍÅ *cascade08ÍÅÕÅ*cascade08ÕÅÖÅ *cascade08ÖÅİÅ*cascade08İÅŞÅ *cascade08ŞÅ÷Å*cascade08÷ÅüÅ *cascade08üÅşÅ*cascade08şÅÿÅ *cascade08ÿÅÆ*cascade08ÆÆ *cascade08ÆÂÆ*cascade08ÂÆÃÆ *cascade08ÃÆÓÆ*cascade08ÓÆÔÆ *cascade08ÔÆáÆ*cascade08áÆâÆ *cascade08âÆéÆ*cascade08éÆêÆ *cascade08êÆºÇ*cascade08ºÇËÈ *cascade08ËÈŞÈ*cascade08ŞÈáÈ *cascade08áÈåÈ*cascade08åÈçÈ *cascade08çÈéÈ*cascade08éÈêÈ *cascade08êÈöÈ*cascade08öÈ÷È *cascade08÷ÈûÈ*cascade08ûÈıÈ *cascade08ıÈ€É*cascade08€É‹É *cascade08‹ÉŒÉ*cascade08ŒÉÉ *cascade08ÉÉ*cascade08É‘É *cascade08‘É’É*cascade08’É˜É *cascade08˜É™É*cascade08™É›É *cascade08›ÉœÉ*cascade08œÉÉ *cascade08É©É*cascade08©ÉªÉ *cascade08ªÉ¬É*cascade08¬É­É *cascade08­É±É*cascade08±É·É *cascade08·É¸É*cascade08¸ÉºÉ *cascade08ºÉ»É*cascade08»É½É *cascade08½ÉÁÉ*cascade08ÁÉÏÉ *cascade08ÏÉÕÉ*cascade08ÕÉÖÉ *cascade08ÖÉŞÉ*cascade08ŞÉàÉ *cascade08àÉêÉ*cascade08êÉëÉ *cascade08ëÉíÉ*cascade08íÉîÉ *cascade08îÉóÉ*cascade08óÉôÉ *cascade08ôÉöÉ*cascade08öÉ÷É *cascade08÷ÉøÉ*cascade08øÉùÉ *cascade08ùÉûÉ*cascade08ûÉüÉ *cascade08üÉıÉ*cascade08ıÉƒÊ *cascade08ƒÊˆÊ*cascade08ˆÊ‰Ê *cascade08‰ÊÊ*cascade08Ê‘Ê *cascade08‘Ê’Ê*cascade08’Ê“Ê *cascade08“Ê–Ê*cascade08–Ê—Ê *cascade08—ÊšÊ*cascade08šÊœÊ *cascade08œÊÊ*cascade08ÊŸÊ *cascade08ŸÊ Ê*cascade08 Ê¡Ê *cascade08¡Ê¢Ê*cascade08¢Ê£Ê *cascade08£Ê§Ê*cascade08§Ê±Ê *cascade08±Ê²Ê*cascade08²Ê³Ê *cascade08³Ê¶Ê*cascade08¶Ê·Ê *cascade08·ÊºÊ *cascade08ºÊ»Ê*cascade08»Ê¼Ê *cascade08¼ÊÛÊ*cascade08ÛÊåÊ *cascade08åÊìÊ*cascade08ìÊíÊ *cascade08íÊîÊ*cascade08îÊõÊ *cascade08õÊ‹Ë*cascade08‹Ë’Ë *cascade08’Ë—Ë*cascade08—Ë˜Ë *cascade08˜Ë›Ë*cascade08›ËœË *cascade08œËË*cascade08ËŸË *cascade08ŸË¥Ë*cascade08¥Ë¦Ë *cascade08¦Ë«Ë*cascade08«Ë¬Ë *cascade08¬ËºË*cascade08ºË¼Ë *cascade08¼Ë¾Ë*cascade08¾Ë¿Ë *cascade08¿ËÁË*cascade08ÁËÂË *cascade08ÂËÌË*cascade08ÌËÍË *cascade08ÍËÏË*cascade08ÏËÀÌ *cascade08ÀÌİÌ*cascade08İÌ°Í *cascade08°Í¹Í*cascade08¹Í»Í *cascade08»Í¿Í*cascade08¿ÍÀÍ *cascade08ÀÍÎÍ*cascade08ÎÍÏÍ *cascade08ÏÍíÍ*cascade08íÍƒÎ *cascade08ƒÎ‰Î*cascade08‰Î‘Î *cascade08‘Î”Î*cascade08”Î•Î *cascade08•Î™Î*cascade08™ÎÍÎ *cascade08ÍÎ¹Ğ*cascade08¹ĞªÑ *cascade08ªÑ«Ñ*cascade08«ÑÊÑ *cascade08ÊÑÜÑ*cascade08ÜÑİÑ *cascade08İÑäÑ*cascade08äÑåÑ *cascade08åÑçÑ*cascade08çÑèÑ *cascade08èÑìÑ*cascade08ìÑíÑ *cascade08íÑòÑ*cascade08òÑóÑ *cascade08óÑ‚Ò*cascade08‚ÒƒÒ *cascade08ƒÒÒ*cascade08ÒÒ *cascade08Ò‘Ò*cascade08‘Ò’Ò *cascade08’Ò“Ò*cascade08“Ò•Ò *cascade08•ÒšÒ*cascade08šÒ›Ò *cascade08›ÒÒ*cascade08ÒŸÒ *cascade08ŸÒ²Ò*cascade08²Ò´Ò *cascade08´Ò¼Ò*cascade08¼ÒÄÒ *cascade08ÄÒËÒ*cascade08ËÒÌÒ *cascade08ÌÒÍÒ *cascade08ÍÒÏÒ *cascade08ÏÒÕÒ*cascade08ÕÒÖÒ *cascade08ÖÒÙÒ*cascade08ÙÒÚÒ *cascade08ÚÒİÒ*cascade08İÒŞÒ *cascade08ŞÒâÒ*cascade08âÒãÒ *cascade08ãÒäÒ *cascade08äÒåÒ *cascade08åÒæÒ*cascade08æÒçÒ *cascade08çÒèÒ *cascade08èÒéÒ *cascade08éÒêÒ*cascade08êÒìÒ *cascade08ìÒîÒ*cascade08îÒïÒ *cascade08ïÒğÒ *cascade08ğÒñÒ *cascade08ñÒõÒ*cascade08õÒöÒ *cascade08öÒ÷Ò *cascade08÷ÒøÒ*cascade08øÒüÒ *cascade08üÒıÒ *cascade08ıÒÿÒ*cascade08ÿÒ€Ó *cascade08€ÓÓ *cascade08Ó†Ó*cascade08†Ó‡Ó *cascade08‡ÓˆÓ*cascade08ˆÓ‰Ó *cascade08‰ÓŠÓ *cascade08ŠÓ‹Ó *cascade08‹Ó‘Ó*cascade08‘Ó’Ó *cascade08’Ó•Ó*cascade08•Ó–Ó *cascade08–Ó—Ó *cascade08—Ó™Ó *cascade08™ÓÓ*cascade08ÓŸÓ*cascade08ŸÓ£Ó *cascade08£Ó¤Ó*cascade08¤Ó¥Ó *cascade08¥Ó§Ó*cascade08§Ó¨Ó *cascade08¨Ó«Ó*cascade08«Ó¬Ó *cascade08¬Ó³Ó*cascade08³Ó·Ó *cascade08·Ó»Ó*cascade08»ÓÅÓ *cascade08ÅÓÌÓ*cascade08ÌÓÓÓ *cascade08ÓÓÖÓ*cascade08ÖÓ×Ó *cascade08×ÓØÓ*cascade08ØÓÙÓ *cascade08ÙÓÜÓ*cascade08ÜÓİÓ *cascade08İÓßÓ*cascade08ßÓæÓ *cascade08æÓèÓ*cascade08èÓéÓ *cascade08éÓíÓ*cascade08íÓîÓ *cascade08îÓÿÓ*cascade08ÿÓˆÔ *cascade08ˆÔŠÔ*cascade08ŠÔ‹Ô *cascade08‹Ô•Ô*cascade08•Ô–Ô *cascade08–Ô›Ô*cascade08›Ô¦Ô *cascade08¦Ô«Ô*cascade08«Ô¬Ô *cascade08¬Ô²Ô*cascade08²Ô³Ô *cascade08³Ô»Ô*cascade08»Ô¼Ô *cascade08¼ÔÉÔ*cascade08ÉÔÏÔ *cascade08ÏÔÓÔ*cascade08ÓÔÔÔ *cascade08ÔÔÕÔ*cascade08ÕÔÖÔ *cascade08ÖÔÛÔ*cascade08ÛÔÜÔ *cascade08ÜÔìÔ*cascade08ìÔğÔ *cascade08ğÔ÷Ô*cascade08÷ÔıÔ *cascade08ıÔÕ*cascade08Õ„Õ *cascade08„Õ–Õ*cascade08–Õ—Õ *cascade08—Õ¡Õ*cascade08¡Õ¢Õ *cascade08¢Õ¤Õ*cascade08¤Õ¦Õ *cascade08¦Õ¨Õ*cascade08¨Õ©Õ *cascade08©Õ«Õ*cascade08«Õ¬Õ *cascade08¬Õ®Õ*cascade08®Õ¯Õ *cascade08¯Õ¹Õ*cascade08¹ÕºÕ *cascade08ºÕĞÕ*cascade08ĞÕÒÕ *cascade08ÒÕ×Õ*cascade08×ÕÙÕ *cascade08ÙÕéÕ*cascade08éÕêÕ *cascade08êÕìÕ*cascade08ìÕíÕ *cascade08íÕõÕ*cascade08õÕ€Ö *cascade08€ÖíÖ *cascade08íÖŸ×*cascade08Ÿ×ù× *cascade08ù×ÿ×*cascade08ÿ×€Ø *cascade08€ØØ*cascade08Ø‘Ø *cascade08‘Ø—Ø*cascade08—Ø˜Ø *cascade08˜Ø¡Ø*cascade08¡Ø¢Ø *cascade08¢Ø§Ø *cascade08§Ø²Ø*cascade08²Ø¶Ø *cascade08¶Ø·Ø *cascade08·ØÁØ*cascade08ÁØÂØ *cascade08ÂØÅØ*cascade08ÅØÆØ *cascade08ÆØÏØ*cascade08ÏØĞØ *cascade08ĞØÑØ*cascade08ÑØÒØ *cascade08ÒØÖØ*cascade08ÖØâØ *cascade08âØòØ*cascade08òØıØ *cascade08ıØ‚Ù*cascade08‚ÙƒÙ *cascade08ƒÙ¡Ù*cascade08¡Ù¢Ù *cascade08¢Ù°Ù*cascade08°Ù²Ù *cascade08²Ù³Ù*cascade08³Ù´Ù *cascade08´ÙÆÙ*cascade08ÆÙÇÙ *cascade08ÇÙÊÙ *cascade08ÊÙéİ *cascade08éİ›Ş*cascade08›ŞØá *cascade08ØáÙá *cascade08Ùáİá *cascade08İáßá *cascade08ßá´ë*cascade08´ëĞë *cascade08ĞëÔë *cascade08ÔëÔï*cascade08Ôïæï *cascade08æïêï*cascade08êïìï *cascade08ìïíï*cascade08íïîï *cascade08îïğï*cascade08ğïòï *cascade08òïõï*cascade08õïöï *cascade08öïùï*cascade08ùïüï *cascade08üïÿï*cascade08ÿï€ğ *cascade08€ğğ*cascade08ğˆğ *cascade08ˆğ‰ğ*cascade08‰ğŠğ *cascade08Šğğ*cascade08ğ™ğ *cascade08™ğ§ğ*cascade08§ğÍğ *cascade08Íğığ*cascade08ığÿğ *cascade08ÿğò*cascade08ò‚ò *cascade08‚òÃò*cascade08ÃòÅò *cascade08"(d4e7a325d0144b3814ef864593774f7a3951320628file:///c:/Users/rovie%20segubre/agent/gateway_server.py:&file:///c:/Users/rovie%20segubre/agent