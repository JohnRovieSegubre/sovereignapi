ªt"""
Moltbook Marketing Agent (Autonomous)
======================================
Scans Moltbook for high-value conversations,
crafts contextual replies promoting Sovereign API,
and chains the next task into .agent/inbox/ for 24/7 operation.

Usage:
    python moltbook_marketing.py scan        # Scout + generate report
    python moltbook_marketing.py engage      # Reply to best target
    python moltbook_marketing.py loop        # Scan â†’ Engage â†’ Schedule next

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
    "Hey {author}! This resonates with what we're building at Sovereign API â€” a drop-in OpenAI replacement where agents pay with USDC on Polygon. DeepSeek-R1 at 5 sats/request, no API key hoops. SDK: `from sdk.sovereign import SovereignClient`. Happy to share a free trial token if you want to test it. ğŸ¦",
    "Interesting thread {author}. We run a self-sovereign gateway (Macaroon auth + Polygon payments) that might solve this. 3 models, transparent pricing, auto-pay SDK. Check m/sovereign or ping me for a trial. ğŸ¤–",
    "{author} â€” we built exactly this kind of infrastructure. Sovereign Intelligence API: agents pay with crypto, get Macaroon tokens as fuel, automatic balance rotation. No vendor lock-in. The SDK is a drop-in `client.chat.completions.create()`. Want a free 1000-sat token to try? âš¡",
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
                print(f"âš ï¸ API returned {resp.status_code}")
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
            print(f"âŒ Fetch error: {e}")
            break
    
    print(f"ğŸ“¡ Fetched {len(all_posts)} posts total")
    
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
            f.write(f"## #{rank} (Score: {score}) â€” {author} in m/{submolt}\n")
            f.write(f"**Title:** {title}\n")
            f.write(f"> {content}...\n\n")
    
    print(f"ğŸ¯ Found {len(scored)} high-value targets. Top score: {scored[0][0] if scored else 0}")
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
    print(f"â³ Sleeping for {delay_minutes} minutes before scheduling next cycle...")
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
    
    print(f"ğŸ“¬ Next task scheduled: {task_file.name}")
    print(f"   Monitor will pick it up in ~{delay_minutes} minutes")


def loop_mode(api_key):
    """The full autonomous cycle: Scan â†’ Engage â†’ Schedule Next."""
    state = load_state()
    state["scan_count"] = state.get("scan_count", 0) + 1
    
    print("=" * 60)
    print(f"  ğŸ”„ MARKETING LOOP (Cycle #{state['scan_count']})")
    print(f"  ğŸ“Š Lifetime Engagements: {state.get('engage_count', 0)}")
    print("=" * 60)
    
    # 1. Scan
    targets = scan(api_key)
    
    # 2. Engage (if targets found)
    if targets:
        engaged = engage(api_key, targets, state)
        if not engaged:
            print("ğŸ’¤ No engagement this cycle (cooldown or no targets).")
    else:
        print("ğŸœï¸ No targets found. The feed is all spam right now.")
    
    save_state(state)
    
    # 3. Chain the next cycle
    schedule_next(delay_minutes=COOLDOWN_MINUTES)
    
    print("\nâœ… Cycle complete. Watchdog will continue autonomously.")


# LLM-powered challenge solver credentials
OPENROUTER_CREDS_PATH = WORKSPACE / ".agent" / "secure" / "openrouter_key.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SOLVER_MODEL = "deepseek/deepseek-chat"  # Cheapest, fastest for math


def solve_challenge(challenge_text):
    """Solve Moltbook CAPTCHA using LLM. No templates â€” pure AI."""
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
        
        # Clean the response â€” extract just the number
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
ä *cascade08äİ*cascade08İ¢ *cascade08¢£*cascade08£µ *cascade08µ¹*cascade08¹Æ *cascade08ÆÇ*cascade08Ç× *cascade08×Û*cascade08Û×. *cascade08×.Ø.*cascade08Ø.ê. *cascade08ê.î.*cascade08î.Â2 *cascade08Â2á2*cascade08á2«5 *cascade08«5«5*cascade08«5à8 *cascade08à8à8*cascade08à8˜< *cascade08˜<Ô>*cascade08Ô>ü> *cascade08ü>ŸB*cascade08ŸB B *cascade08 BE*cascade08EE *cascade08E”E*cascade08”E•E *cascade08•E³E*cascade08³E´E *cascade08´E¶E*cascade08¶E·E *cascade08·EÙF*cascade08ÙFÚF *cascade08ÚF‰H*cascade08‰H¡H *cascade08¡H¥H*cascade08¥HÜH *cascade08ÜHàH*cascade08àH¥I *cascade08¥I©I*cascade08©IóI *cascade08óI÷I*cascade08÷IŠJ *cascade08ŠJŒJ*cascade08ŒJœJ *cascade08œJJ*cascade08J·J *cascade08·JÀJ*cascade08ÀJÎJ *cascade08ÎJßJ*cascade08ßJàJ *cascade08àJáJ*cascade08áJãJ *cascade08ãJêJ*cascade08êJëJ *cascade08ëJöJ*cascade08öJ†K *cascade08†K‡K*cascade08‡KˆK *cascade08ˆK–K*cascade08–K—K *cascade08—KK*cascade08K¯K *cascade08¯KµK*cascade08µK·K *cascade08·KÆK*cascade08ÆKÇK *cascade08ÇKÉK*cascade08ÉKËK *cascade08ËKÌK*cascade08ÌKÍK *cascade08ÍKäK*cascade08äKåK *cascade08åKèK*cascade08èKìK *cascade08ìKíK*cascade08íKîK *cascade08îKõK*cascade08õK÷K *cascade08÷KùK*cascade08ùKüK *cascade08üKşK*cascade08şKL *cascade08L‘L*cascade08‘L’L *cascade08’L™L*cascade08™LšL *cascade08šL¡L*cascade08¡L¢L *cascade08¢LªL*cascade08ªL«L *cascade08«L®L*cascade08®L¯L *cascade08¯L³L*cascade08³L´L *cascade08´LµL*cascade08µL¶L *cascade08¶L¸L*cascade08¸LºL *cascade08ºL¾L*cascade08¾L¿L *cascade08¿LÂL*cascade08ÂLÄL *cascade08ÄLÈL*cascade08ÈLÔL *cascade08ÔLùL*cascade08ùLûL *cascade08ûLüL*cascade08üLˆM *cascade08ˆMM*cascade08MM *cascade08M•M*cascade08•M–M *cascade08–M¨M*cascade08¨M©M *cascade08©M®M*cascade08®MÀM *cascade08ÀMÃM*cascade08ÃMÄM *cascade08ÄMÆM*cascade08ÆMÉM *cascade08ÉMÒM*cascade08ÒMÓM *cascade08ÓMÕM*cascade08ÕMÖM *cascade08ÖM×M*cascade08×MİM *cascade08İMßM*cascade08ßMáM *cascade08áMãM*cascade08ãMäM *cascade08äMîM*cascade08îMğM *cascade08ğMóM*cascade08óMôM *cascade08ôMøM*cascade08øMŠN *cascade08ŠN’N*cascade08’N”N *cascade08”N–N*cascade08–N™N *cascade08™N›N*cascade08›N­N *cascade08­N¯N*cascade08¯N°N *cascade08°N²N*cascade08²N³N *cascade08³N¶N*cascade08¶NßP *cascade08ßP‹Q*cascade08‹QQ *cascade08QšQ*cascade08šQœQ *cascade08œQQ*cascade08QŸQ *cascade08ŸQ¡Q*cascade08¡Q¢Q *cascade08¢Q£Q*cascade08£Q¤Q *cascade08¤QªQ*cascade08ªQ¬Q *cascade08¬Q­Q*cascade08­Q®Q *cascade08®Q¼Q*cascade08¼Q¾Q *cascade08¾QÀQ*cascade08ÀQÁQ *cascade08ÁQÅQ*cascade08ÅQÇQ *cascade08ÇQòQ*cascade08òQÊ] *cascade08Ê]Ì] *cascade08Ì]Ï]*cascade08Ï]Ğ] *cascade08Ğ]Ñ]*cascade08Ñ]Ò] *cascade08Ò]Ó]*cascade08Ó]Õ] *cascade08Õ]×]*cascade08×]æ] *cascade08æ]î]*cascade08î]ï] *cascade08ï]ô]*cascade08ô]÷] *cascade08÷]ù]*cascade08ù]ú] *cascade08ú]ü]*cascade08ü]ı] *cascade08ı]ş]*cascade08ş]€^ *cascade08€^…^*cascade08…^†^ *cascade08†^‹^*cascade08‹^^ *cascade08^—^*cascade08—^˜^ *cascade08˜^™^*cascade08™^›^ *cascade08›^^*cascade08^£^ *cascade08£^¤^*cascade08¤^¦^ *cascade08¦^§^*cascade08§^¨^ *cascade08¨^©^*cascade08©^®^ *cascade08®^¯^*cascade08¯^±^ *cascade08±^³^*cascade08³^º^ *cascade08º^½^*cascade08½^¾^ *cascade08¾^Á^*cascade08Á^Â^ *cascade08Â^Ã^*cascade08Ã^Ç^ *cascade08Ç^Õ^*cascade08Õ^Ö^ *cascade08Ö^×^*cascade08×^Ü^ *cascade08Ü^Ş^*cascade08Ş^ß^ *cascade08ß^ã^*cascade08ã^ç^ *cascade08ç^è^*cascade08è^é^ *cascade08é^í^*cascade08í^î^ *cascade08î^ñ^*cascade08ñ^ò^ *cascade08ò^ó^*cascade08ó^ô^ *cascade08ô^÷^*cascade08÷^ø^ *cascade08ø^ù^*cascade08ù^ú^ *cascade08ú^€_*cascade08€_‚_ *cascade08‚_„_*cascade08„_…_ *cascade08…_†_*cascade08†_‰_ *cascade08‰_Š_*cascade08Š_‹_ *cascade08‹__*cascade08__ *cascade08_‘_*cascade08‘_’_ *cascade08’_•_*cascade08•_™_ *cascade08™_œ_*cascade08œ_ _ *cascade08 _¢_*cascade08¢_¥_ *cascade08¥_§_*cascade08§_¨_ *cascade08¨_ª_*cascade08ª_«_ *cascade08«_¯_*cascade08¯_²_ *cascade08²_³_*cascade08³_´_ *cascade08´_¹_*cascade08¹_¾_ *cascade08¾_Á_*cascade08Á_Ã_ *cascade08Ã_Ä_*cascade08Ä_Æ_ *cascade08Æ_Ç_*cascade08Ç_Ê_ *cascade08Ê_Î_*cascade08Î_Ô_ *cascade08Ô_—` *cascade08—`˜` *cascade08˜`›`*cascade08›`œ` *cascade08œ`¢`*cascade08¢`£` *cascade08£`¤`*cascade08¤`¦` *cascade08¦`¨`*cascade08¨`©` *cascade08©`­`*cascade08­`®` *cascade08®`¯`*cascade08¯`°` *cascade08°`³`*cascade08³`´` *cascade08´`¶`*cascade08¶`¹` *cascade08¹`»`*cascade08»`¼` *cascade08¼`Å` *cascade08Å`Ê`*cascade08Ê`Ë` *cascade08Ë`å`*cascade08å`æ` *cascade08æ`‡a *cascade08‡aˆa*cascade08ˆaa *cascade08a™a*cascade08™a½a *cascade08½a¾a *cascade08¾aÅa*cascade08ÅaÆa *cascade08ÆaÉa *cascade08ÉaÊa*cascade08ÊaËa *cascade08ËaÍa*cascade08ÍaÎa *cascade08ÎaĞa*cascade08ĞaÓa *cascade08Óaèa*cascade08èaêa *cascade08êaîa*cascade08îaïa *cascade08ïağa*cascade08ğaòa *cascade08òaôa*cascade08ôa‚b *cascade08‚bˆb*cascade08ˆb‹b *cascade08‹bŒb*cascade08Œbb *cascade08bb*cascade08bb *cascade08b“b*cascade08“b”b *cascade08”b™b*cascade08™b¤b *cascade08¤b¦b*cascade08¦b§b *cascade08§bªb*cascade08ªb­b *cascade08­b±b*cascade08±b³b *cascade08³b´b*cascade08´b¶b *cascade08¶bÊb*cascade08ÊbËb *cascade08ËbÍb*cascade08ÍbÎb *cascade08ÎbÏb*cascade08ÏbĞb*cascade08ĞbÑb *cascade08ÑbÖb*cascade08Öb×b *cascade08×bÛb*cascade08ÛbÜb *cascade08Übİb*cascade08İbŞb *cascade08Şbçb*cascade08çbñb *cascade08ñb‚c*cascade08‚c…c *cascade08…c†c*cascade08†c‡c *cascade08‡cc*cascade08cc *cascade08cc*cascade08cc *cascade08c‘c*cascade08‘c’c *cascade08’c“c*cascade08“c”c *cascade08”c–c *cascade08–cšc*cascade08šcc *cascade08cc*cascade08cŸc *cascade08Ÿc¡c*cascade08¡c¢c *cascade08¢c£c*cascade08£c¤c *cascade08¤c§c*cascade08§c±c *cascade08±c³c*cascade08³c´c *cascade08´c¹c*cascade08¹cºc *cascade08ºc»c*cascade08»c¼c *cascade08¼cÂc *cascade08ÂcÄc*cascade08ÄcÈc *cascade08ÈcÉc*cascade08ÉcÊc *cascade08ÊcËc *cascade08ËcÍc*cascade08ÍcÒc *cascade08ÒcÓc*cascade08Ócİc *cascade08İcâc*cascade08âcäc *cascade08äcçc*cascade08çcéc *cascade08écêc*cascade08êcëc *cascade08ëcíc*cascade08ícîc *cascade08îcüc*cascade08ücşc *cascade08şc‚d*cascade08‚dŒd *cascade08Œd“d*cascade08“d”d *cascade08”d›d*cascade08›dœd *cascade08œd¤d*cascade08¤d¦d *cascade08¦d®d*cascade08®d´d *cascade08´d·d*cascade08·d»d *cascade08»d½d*cascade08½dÁd *cascade08ÁdÂd*cascade08ÂdÃd *cascade08ÃdÆd*cascade08ÆdÉd *cascade08ÉdÊd*cascade08ÊdËd *cascade08ËdÌd*cascade08ÌdÖd *cascade08ÖdŞd*cascade08Şdßd *cascade08ßdîd*cascade08îdõd *cascade08õdød*cascade08ødùd *cascade08ùdúd*cascade08údüd *cascade08üdıd*cascade08ıdşd *cascade08şdƒe*cascade08ƒe…e *cascade08…e‡e*cascade08‡ee *cascade08e’e*cascade08’ee *cascade08e¢e *cascade08¢e¥e*cascade08¥e§e *cascade08§e«e*cascade08«e¬e *cascade08¬e±e*cascade08±e²e *cascade08²eµe*cascade08µe·e *cascade08·e¸e*cascade08¸eÇe *cascade08ÇeÉe*cascade08ÉeËe *cascade08ËeÌe*cascade08ÌeÍe *cascade08ÍeÎe*cascade08ÎeÏe *cascade08ÏeÑe*cascade08ÑeÒe *cascade08ÒeÖe*cascade08Öe×e *cascade08×eÚe*cascade08ÚeÛe *cascade08ÛeÜe*cascade08Üeİe *cascade08İeáe*cascade08áeâe *cascade08âeée*cascade08éeêe *cascade08êeíe*cascade08íeîe *cascade08îeòe*cascade08òeóe *cascade08óeúe*cascade08úeûe *cascade08ûeüe*cascade08üeıe *cascade08ıef*cascade08f‚f *cascade08‚f„f*cascade08„f†f *cascade08†f‡f *cascade08‡f‹f*cascade08‹fŒf *cascade08Œff*cascade08ff *cascade08ff*cascade08ff *cascade08f“f*cascade08“f”f *cascade08”f˜f*cascade08˜f™f *cascade08™ff*cascade08ff *cascade08f¡f*cascade08¡f¢f *cascade08¢f«f*cascade08«f¬f *cascade08¬f°f*cascade08°f²f *cascade08²f´f *cascade08´fµf*cascade08µf¶f *cascade08¶fºf*cascade08ºf»f *cascade08»f½f*cascade08½f¾f *cascade08¾f¿f*cascade08¿fÂf *cascade08ÂfÃf*cascade08ÃfÅf *cascade08ÅfÇf*cascade08ÇfÈf *cascade08ÈfÉf*cascade08ÉfÊf *cascade08ÊfÑf*cascade08ÑfÓf *cascade08ÓfÔf*cascade08ÔfÕf *cascade08Õf×f*cascade08×fØf *cascade08ØfÙf*cascade08ÙfÚf *cascade08Úfáf*cascade08áfâf *cascade08âfåf*cascade08åfæf *cascade08æfçf*cascade08çfèf *cascade08èfêf*cascade08êfëf *cascade08ëfìf*cascade08ìfğf *cascade08ğfñf*cascade08ñfóf *cascade08ófôf*cascade08ôföf *cascade08öfûf*cascade08ûfşf *cascade08şfg*cascade08g‚g *cascade08‚gƒg *cascade08ƒg„g*cascade08„g†g *cascade08†g‰g*cascade08‰gŠg *cascade08Šg‹g*cascade08‹gŒg *cascade08Œgg*cascade08gg *cascade08gg*cascade08g’g *cascade08’g”g*cascade08”g›g *cascade08›gœg*cascade08œgg *cascade08g¥g*cascade08¥g¦g *cascade08¦g¬g*cascade08¬g¶g *cascade08¶g¸g*cascade08¸gºg *cascade08ºg¼g*cascade08¼g¾g *cascade08¾g¿g*cascade08¿gÉg *cascade08ÉgËg*cascade08ËgÔg *cascade08Ôgİg *cascade08İgŞg*cascade08Şgàg *cascade08àgäg*cascade08ägåg *cascade08ågçg*cascade08çgèg *cascade08ègìg*cascade08ìgúg *cascade08úg€h*cascade08€hh *cascade08h‰h*cascade08‰hŠh *cascade08Šhh*cascade08hh *cascade08h‘h*cascade08‘h’h *cascade08’h—h*cascade08—h¤h *cascade08¤h¥h *cascade08¥h¦h*cascade08¦h°h *cascade08°h´h*cascade08´h¼h *cascade08¼h½h*cascade08½h¾h *cascade08¾h¿h *cascade08¿hÀh*cascade08ÀhÁh *cascade08ÁhÂh*cascade08ÂhÃh *cascade08ÃhÄh*cascade08ÄhÆh *cascade08ÆhÍh*cascade08Íh×h *cascade08×håh*cascade08åhæh *cascade08æhéh*cascade08éhíh *cascade08íhîh*cascade08îhôh *cascade08ôhöh*cascade08öhúh *cascade08úh€i*cascade08€iˆi *cascade08ˆiŠi*cascade08Ši‹i *cascade08‹i’i*cascade08’i“i *cascade08“i—i*cascade08—i™i *cascade08™iœi*cascade08œii *cascade08i¡i*cascade08¡i£i *cascade08£i§i*cascade08§i¨i *cascade08¨iµi*cascade08µi¶i *cascade08¶iÄi*cascade08ÄiÆi *cascade08ÆiÖi*cascade08Öiîi *cascade08îiïi*cascade08ïiği *cascade08ği÷i*cascade08÷iúi *cascade08úiûi*cascade08ûiıi *cascade08ıişi*cascade08şiÿi *cascade08ÿi€j*cascade08€jƒj *cascade08ƒjˆj*cascade08ˆj”j *cascade08”jœj*cascade08œjŸj *cascade08Ÿj¢j*cascade08¢j£j *cascade08£j§j*cascade08§j¬j *cascade08¬j­j*cascade08­j®j *cascade08®j°j*cascade08°j²j *cascade08²jµj*cascade08µj¶j *cascade08¶j·j*cascade08·j¸j *cascade08¸j»j*cascade08»j¾j *cascade08¾j¿j*cascade08¿jÁj *cascade08ÁjÂj*cascade08ÂjÄj *cascade08ÄjÅj*cascade08ÅjÈj *cascade08ÈjÊj*cascade08ÊjËj *cascade08ËjÍj *cascade08ÍjÖj*cascade08Öjìj *cascade08ìjïj*cascade08ïj„k *cascade08„k…k*cascade08…k‡k *cascade08‡kˆk*cascade08ˆk‰k *cascade08‰kŠk*cascade08ŠkŒk *cascade08Œkk *cascade08kk *cascade08kk *cascade08k‘k*cascade08‘k’k *cascade08’k•k*cascade08•k™k *cascade08™k k *cascade08 k§k*cascade08§k¨k *cascade08¨k©k*cascade08©kªk *cascade08ªk«k *cascade08«k¬k*cascade08¬k­k *cascade08­k¯k*cascade08¯k°k *cascade08°k¸k*cascade08¸k¹k *cascade08¹kÒk*cascade08ÒkÓk *cascade08ÓkÕk*cascade08ÕkØk *cascade08ØkÛk*cascade08Ûkßk *cascade08ßkák *cascade08ákñk *cascade08ñkòk*cascade08òkók *cascade08ókøk*cascade08økùk *cascade08ùkük*cascade08ükık *cascade08ık…l*cascade08…l†l *cascade08†l‰l*cascade08‰lŠl *cascade08Šll*cascade08ll *cascade08l‘l*cascade08‘l’l *cascade08’lšl*cascade08šlœl *cascade08œl l*cascade08 l«l *cascade08«l¬l*cascade08¬l­l *cascade08­l°l*cascade08°l±l *cascade08±l´l*cascade08´lµl *cascade08µl·l*cascade08·l¸l *cascade08¸l¹l*cascade08¹lºl *cascade08ºl»l*cascade08»l¼l *cascade08¼l¾l *cascade08¾l¿l*cascade08¿lÁl *cascade08ÁlÆl*cascade08ÆlÇl *cascade08ÇlØl*cascade08ØlÙl *cascade08Ùlİl*cascade08İlßl *cascade08ßlél*cascade08élël *cascade08ëlğl*cascade08ğlúl *cascade08úl†m*cascade08†m‡m *cascade08‡mˆm*cascade08ˆmŒm *cascade08Œmm*cascade08mm *cascade08mm*cascade08m—m *cascade08—m›m*cascade08›mœm *cascade08œmm*cascade08mŸm *cascade08Ÿm£m*cascade08£m¦m *cascade08¦m¨m*cascade08¨m¬m *cascade08¬m°m*cascade08°m»m *cascade08»m½m*cascade08½m¿m *cascade08¿mÀm *cascade08ÀmÁm *cascade08ÁmÂm*cascade08ÂmÃm *cascade08ÃmÄm *cascade08ÄmÅm *cascade08ÅmÆm*cascade08ÆmÇm *cascade08ÇmËm*cascade08ËmÙm *cascade08ÙmÚm*cascade08ÚmÛm *cascade08Ûmİm*cascade08İmŞm *cascade08Şmâm*cascade08âmäm *cascade08ämåm*cascade08åmæm *cascade08æmèm*cascade08èmém *cascade08émîm*cascade08îmïm *cascade08ïmım*cascade08ımn *cascade08nn*cascade08nn *cascade08n‘n*cascade08‘n’n *cascade08’n“n*cascade08“n•n *cascade08•n—n*cascade08—n˜n *cascade08˜n›n*cascade08›nœn *cascade08œnn*cascade08nn *cascade08n£n*cascade08£n²n *cascade08²n´n*cascade08´nµn *cascade08µn¶n*cascade08¶n¸n *cascade08¸n¹n*cascade08¹n¼n *cascade08¼n¿n*cascade08¿nÀn *cascade08ÀnÂn*cascade08ÂnÃn *cascade08ÃnÄn*cascade08ÄnÆn *cascade08ÆnÇn*cascade08ÇnÈn *cascade08ÈnÎn*cascade08ÎnÏn *cascade08ÏnĞn *cascade08ĞnÑn *cascade08ÑnÕn*cascade08Õn×n *cascade08×nØn*cascade08ØnÙn *cascade08ÙnÚn*cascade08ÚnÛn *cascade08Ûnİn*cascade08İnßn *cascade08ßnàn*cascade08ànân *cascade08ânån*cascade08ånçn *cascade08çnèn*cascade08ènîn *cascade08înùn *cascade08ùnün*cascade08ünşn *cascade08şno*cascade08oo *cascade08o‘o*cascade08‘o¢o *cascade08¢o¤o*cascade08¤o¥o *cascade08¥o©o*cascade08©o¬o *cascade08¬o®o*cascade08®o²o *cascade08²o³o*cascade08³o´o *cascade08´oµo*cascade08µo¶o *cascade08¶o·o*cascade08·o½o *cascade08½o¿o*cascade08¿oÁo *cascade08ÁoÃo*cascade08ÃoÅo *cascade08ÅoÇo*cascade08ÇoÈo *cascade08ÈoÉo *cascade08ÉoÊo*cascade08ÊoÎo *cascade08ÎoĞo*cascade08ĞoÑo *cascade08ÑoÔo*cascade08Ôoæo *cascade08æoéo*cascade08éoêo *cascade08êoío*cascade08íoüo *cascade08üo‰p *cascade08‰p’p*cascade08’p“p *cascade08“p•p *cascade08•p˜p*cascade08˜p­p *cascade08­p°p*cascade08°p¶p *cascade08¶p·p*cascade08·pºp *cascade08ºpÅp*cascade08ÅpÎp *cascade08ÎpÒp*cascade08Òpªt *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062<file:///c:/Users/rovie%20segubre/agent/moltbook_marketing.py:&file:///c:/Users/rovie%20segubre/agent