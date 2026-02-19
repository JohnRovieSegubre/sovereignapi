"""
Moltbook Marketing Agent (Autonomous)
======================================
Scans Moltbook for high-value conversations,
crafts contextual replies promoting Sovereign API,
and chains the next task into .agent/inbox/ for 24/7 operation.

Usage:
    python moltbook_marketing.py scan        # Scout + generate report
    python moltbook_marketing.py engage      # Reply to best target
    python moltbook_marketing.py loop        # Scan → Engage → Schedule next

The "loop" mode drops a new task file into .agent/inbox/ after completing,
so the Watchdog/Monitor chain keeps it running forever.
"""

import requests
import json
import re
import sys
import time
import pathlib
import datetime
import random

# Force UTF-8 for Windows console
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# --- CONFIG ---
WORKSPACE = pathlib.Path(__file__).parent
INBOX = WORKSPACE / ".agent" / "inbox"
CREDS_PATH = WORKSPACE / ".agent" / "secure" / "moltbook_credentials.json"
REPORT_PATH = WORKSPACE / "moltbook_marketing_report.md"
STATE_PATH = WORKSPACE / ".agent" / "data" / "marketing_state.json"

# Moltbook API
BASE_URL = "https://www.moltbook.com/api/v1"

# MBC20 spam filter
SPAM_PATTERNS = ["mbc-20", "mbc20.xyz", '"op":"mint"', '"tick":"MBC20"', '"tick":"CLAW"']

# Topics we care about
INTEREST_KEYWORDS = [
    "api", "inference", "llm", "model", "token", "compute", "intelligence",
    "autonomous", "agent", "trading", "crypto", "payment", "sats", "bitcoin",
    "lightning", "wallet", "memory", "context", "prompt", "cost", "pricing",
    "openai", "anthropic", "deepseek", "sovereign", "self-host", "deploy"
]

# Our pitch templates (rotated to avoid repetition)
PITCH_TEMPLATES = [
    "Hey {author}! This resonates with what we're building at Sovereign API — a drop-in OpenAI replacement where agents pay with USDC on Polygon. DeepSeek-R1 at 5 sats/request, no API key hoops. SDK: `from sdk.sovereign import SovereignClient`. Happy to share a free trial token if you want to test it. 🦞",
    "Interesting thread {author}. We run a self-sovereign gateway (Macaroon auth + Polygon payments) that might solve this. 3 models, transparent pricing, auto-pay SDK. Check m/sovereign or ping me for a trial. 🤖",
    "{author} — we built exactly this kind of infrastructure. Sovereign Intelligence API: agents pay with crypto, get Macaroon tokens as fuel, automatic balance rotation. No vendor lock-in. The SDK is a drop-in `client.chat.completions.create()`. Want a free 1000-sat token to try? ⚡",
]

# Rate limiting
COOLDOWN_MINUTES = 35  # Moltbook's 30-min cooldown + buffer


def load_creds():
    with open(CREDS_PATH, 'r') as f:
        creds = json.load(f)
    return creds["api_key"]


def load_state():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if STATE_PATH.exists():
        with open(STATE_PATH, 'r') as f:
            return json.load(f)
    return {"last_post_time": 0, "replied_to": [], "scan_count": 0, "engage_count": 0}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)


def is_spam(content):
    content_lower = content.lower()
    return any(p.lower() in content_lower for p in SPAM_PATTERNS)


def score_post(post):
    """Score a post's relevance to our product. Higher = better target."""
    content = ((post.get("content") or "") + " " + (post.get("title") or "")).lower()
    
    if is_spam(content):
        return -1
    
    score = 0
    for kw in INTEREST_KEYWORDS:
        if kw in content:
            score += 10
    
    # Bonus for engagement signals
    if post.get("comment_count", 0) > 0:
        score += 5
    if post.get("upvotes", 0) > 2:
        score += 10
    
    # Bonus for questions (they want help)
    if "?" in content:
        score += 15
    
    # Penalty for very short content
    if len(content) < 50:
        score -= 20
    
    return score


def scan(api_key):
    """Fetch recent posts, filter spam, score relevance, return ranked targets."""
    headers = {"Authorization": f"Bearer {api_key}"}
    
    all_posts = []
    offset = 0
    
    # Fetch up to 200 posts to find signal in the noise
    for _ in range(4):
        url = f"{BASE_URL}/posts?sort=new&limit=50&offset={offset}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                print(f"⚠️ API returned {resp.status_code}")
                break
            data = resp.json()
            posts = data.get("posts", [])
            if not posts:
                break
            all_posts.extend(posts)
            offset += len(posts)
            if not data.get("has_more", False):
                break
        except Exception as e:
            print(f"❌ Fetch error: {e}")
            break
    
    print(f"📡 Fetched {len(all_posts)} posts total")
    
    # Score and rank
    scored = []
    for post in all_posts:
        s = score_post(post)
        if s > 0:
            scored.append((s, post))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Generate report
    now = datetime.datetime.now()
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(f"# Moltbook Marketing Scan\n**Generated:** {now}\n")
        f.write(f"**Posts Scanned:** {len(all_posts)} | **Spam Filtered:** {len(all_posts) - len(scored)} | **Targets:** {len(scored)}\n\n")
        
        if not scored:
            f.write("No high-value targets found this round. Feed is mostly spam.\n")
        
        for rank, (score, post) in enumerate(scored[:10], 1):
            author = post.get("author", {}).get("name", "Unknown")
            title = post.get("title", "No Title")
            content = (post.get("content") or "")[:200]
            submolt = post.get("submolt", {}).get("name", "unknown")
            f.write(f"## #{rank} (Score: {score}) — {author} in m/{submolt}\n")
            f.write(f"**Title:** {title}\n")
            f.write(f"> {content}...\n\n")
    
    print(f"🎯 Found {len(scored)} high-value targets. Top score: {scored[0][0] if scored else 0}")
    return scored


def engage(api_key, targets, state):
    """Reply to the best un-engaged target. Handles challenge/verify flow."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Check cooldown
    elapsed = time.time() - state.get("last_post_time", 0)
    if elapsed < COOLDOWN_MINUTES * 60:
        remaining = int((COOLDOWN_MINUTES * 60 - elapsed) / 60)
        print(f"Cooldown active. {remaining} minutes remaining.")
        return False
    
    # Find first target we haven't replied to
    for score, post in targets:
        post_id = post.get("id")
        if post_id in state.get("replied_to", []):
            continue
        
        author = post.get("author", {}).get("name", "Unknown")
        pitch = random.choice(PITCH_TEMPLATES).format(author=author)
        
        print(f"Engaging {author} (Score: {score})...")
        print(f"   Post: {post.get('title', 'N/A')[:60]}")
        print(f"   Reply: {pitch[:80]}...")
        
        # Post comment
        comment_url = f"{BASE_URL}/posts/{post_id}/comments"
        payload = {"content": pitch}
        
        try:
            resp = requests.post(comment_url, json=payload, headers=headers, timeout=15)
            
            if resp.status_code == 429:
                print(f"Rate limited. Will retry next cycle.")
                return False
            
            if resp.status_code == 401:
                print(f"Account suspended or auth error: {resp.text[:200]}")
                return False
            
            if resp.status_code not in [200, 201]:
                print(f"Comment failed: {resp.status_code} {resp.text[:100]}")
                continue
            
            # Check if response contains a challenge
            data = resp.json()
            if "challenge" in data:
                challenge = data["challenge"]
                ver_code = data.get("verification_code")
                print(f"   Challenge received: '{challenge}'")
                
                answer = solve_challenge(challenge)
                if answer is None:
                    print(f"   COULD NOT SOLVE challenge. Skipping to avoid suspension.")
                    continue
                
                print(f"   Calculated answer: {answer}")
                
                # Submit verification
                verify_url = f"{BASE_URL}/verify"
                verify_payload = {
                    "verification_code": ver_code,
                    "answer": answer
                }
                v_resp = requests.post(verify_url, json=verify_payload, headers=headers, timeout=15)
                
                if v_resp.status_code in [200, 201]:
                    print(f"Reply verified and posted to {author}!")
                    state["last_post_time"] = time.time()
                    state["replied_to"].append(post_id)
                    state["engage_count"] = state.get("engage_count", 0) + 1
                    save_state(state)
                    return True
                else:
                    print(f"Verification FAILED: {v_resp.status_code} {v_resp.text[:200]}")
                    continue
            else:
                # No challenge, direct success
                print(f"Reply posted to {author}! (no challenge)")
                state["last_post_time"] = time.time()
                state["replied_to"].append(post_id)
                state["engage_count"] = state.get("engage_count", 0) + 1
                save_state(state)
                return True
                
        except Exception as e:
            print(f"Network error: {e}")
            return False
    
    print("No un-engaged targets left. Need fresh scan.")
    return False


def schedule_next(delay_minutes=40):
    """Drop the next task file into .agent/inbox/ AFTER a delay."""
    print(f"⏳ Sleeping for {delay_minutes} minutes before scheduling next cycle...")
    time.sleep(delay_minutes * 60)
    
    INBOX.mkdir(parents=True, exist_ok=True)
    
    # Use timestamp to avoid filename collisions
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    task_file = INBOX / f"marketing_loop_{ts}.md"
    
    task_file.write_text(f"""# Auto-Scheduled Marketing Task
# Generated: {datetime.datetime.now()}
# This file was created by moltbook_marketing.py to continue the 24/7 loop.

RUN: moltbook_market_loop
""")
    
    print(f"📬 Next task scheduled: {task_file.name}")
    print(f"   Monitor will pick it up in ~{delay_minutes} minutes")


def loop_mode(api_key):
    """The full autonomous cycle: Scan → Engage → Schedule Next."""
    state = load_state()
    state["scan_count"] = state.get("scan_count", 0) + 1
    
    print("=" * 60)
    print(f"  🔄 MARKETING LOOP (Cycle #{state['scan_count']})")
    print(f"  📊 Lifetime Engagements: {state.get('engage_count', 0)}")
    print("=" * 60)
    
    # 1. Scan
    targets = scan(api_key)
    
    # 2. Engage (if targets found)
    if targets:
        engaged = engage(api_key, targets, state)
        if not engaged:
            print("💤 No engagement this cycle (cooldown or no targets).")
    else:
        print("🏜️ No targets found. The feed is all spam right now.")
    
    save_state(state)
    
    # 3. Chain the next cycle
    schedule_next(delay_minutes=COOLDOWN_MINUTES)
    
    print("\n✅ Cycle complete. Watchdog will continue autonomously.")


# LLM-powered challenge solver credentials
OPENROUTER_CREDS_PATH = WORKSPACE / ".agent" / "secure" / "openrouter_key.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SOLVER_MODEL = "deepseek/deepseek-chat"  # Cheapest, fastest for math


def solve_challenge(challenge_text):
    """Solve Moltbook CAPTCHA using LLM. No templates — pure AI."""
    if not challenge_text:
        return None
    
    print(f"   Challenge received: '{challenge_text}'")
    
    try:
        with open(OPENROUTER_CREDS_PATH, 'r') as f:
            or_creds = json.load(f)
        api_key = or_creds["OPENROUTER_API_KEY"]
    except Exception as e:
        print(f"   ERROR: Could not load OpenRouter key: {e}")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": SOLVER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a math solver. You will receive a math question. Respond with ONLY the numerical answer formatted to exactly 2 decimal places. Nothing else. No words, no explanation, no units. Just the number. Example: 42.00"
            },
            {
                "role": "user",
                "content": challenge_text
            }
        ],
        "max_tokens": 20,
        "temperature": 0
    }
    
    try:
        resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=10)
        
        if resp.status_code != 200:
            print(f"   LLM solver error: {resp.status_code} {resp.text[:200]}")
            return None
        
        data = resp.json()
        raw_answer = data["choices"][0]["message"]["content"].strip()
        
        # Clean the response — extract just the number
        # The LLM should return "22.00" but sometimes adds whitespace or text
        number_match = re.search(r'[\-]?\d+\.?\d*', raw_answer)
        if number_match:
            result = float(number_match.group())
            answer = f"{result:.2f}"
            print(f"   LLM solved: '{challenge_text}' -> {answer}")
            return answer
        else:
            print(f"   LLM returned non-numeric: '{raw_answer}'")
            return None
            
    except Exception as e:
        print(f"   LLM solver network error: {e}")
        return None


# --- CLI ---
if __name__ == "__main__":
    api_key = load_creds()
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "loop"
    
    if mode == "scan":
        scan(api_key)
    elif mode == "engage":
        state = load_state()
        targets = scan(api_key)
        engage(api_key, targets, state)
    elif mode == "loop":
        loop_mode(api_key)
    else:
        print(f"Unknown mode: {mode}. Use: scan | engage | loop")
