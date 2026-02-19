ÿimport requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
ADMIN_KEY = "sovereign_mint_key_x7k9m2p4q8r6t1w3y5z0a8b6c4d2e0f7"

def run_security_test():
    print("--- ğŸ›¡ï¸ Sovereign Mint: Security Verification Test ---")
    
    # 1. MINT TOKEN
    print("\n[Step 1] Minting fresh token (1000 sats)...")
    identifier = f"test_verify_{int(time.time())}"
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/admin/mint",
            headers={"X-Admin-Key": ADMIN_KEY},
            json={"amount_sats": 1000, "identifier": identifier},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"âŒ Failed to mint: {resp.text}")
            return
        token_a = resp.json()["access_token"]
        print(f"âœ… Token A Minted.")
    except Exception as e:
        print(f"âŒ Connection Error (Mint): {e}")
        return

    # 2. FIRST SPEND (Success) - Verification Logic happens BEFORE upstream
    # However, standard flow waits for upstream. OpenRouter can be slow.
    print("\n[Step 2] Performing initial spend (Token A)...")
    payload = {"model": "sovereign-r1", "messages": [{"role": "user", "content": "Hi"}]}
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {token_a}"},
            json=payload,
            timeout=60 # Extended timeout for AI latency
        )
        if resp.status_code == 200:
            print("âœ… First Spend: SUCCESS (as expected).")
            token_b = resp.headers.get("X-Sovereign-Balance-Token")
            print("âœ… Change Token B received.")
        else:
            print(f"âŒ First Spend FAILED: {resp.status_code} - {resp.text}")
            return
    except Exception as e:
         print(f"âŒ Connection Error (Spend 1): {e}")
         return

    # 3. REPLAY ATTEMPT (The Vulnerability Check)
    # This should be FAST because it's rejected locally.
    print("\n[Step 3] Attempting REPLAY ATTACK (Sending Token A again)...")
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {token_a}"},
            json=payload,
            timeout=10 
        )
        if resp.status_code == 403:
            print("âœ… REPLAY REJECTED: Server returned 403 (Attack Foiled).")
            print(f"   Error Msg: {resp.json().get('error')}")
        elif resp.status_code == 200:
            print("âŒ VULNERABILITY DETECTED: Token A was accepted twice! Infinite money glitch alive.")
        else:
            print(f"â“ Unexpected status: {resp.status_code} - {resp.text}")
    except Exception as e:
         print(f"âŒ Connection Error (Replay): {e}")

    # 4. USE CHANGE (Stateless Flow Check)
    if token_b:
        print("\n[Step 4] Verifying Change Token B works...")
        try:
            resp = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {token_b}"},
                json=payload,
                timeout=60
            )
            if resp.status_code == 200:
                print("âœ… Change Token B: SUCCESS.")
                print("âœ… Whole lifecycle verified.")
            else:
                print(f"âŒ Change Token B FAILED: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"âŒ Connection Error (Spend Change): {e}")

if __name__ == "__main__":
    run_security_test()
È *cascade08Èß *cascade08ßá*cascade08áô *cascade08ôû*cascade08û´ *cascade08´«*cascade08«¾	 *cascade08¾	¿	*cascade08¿	Ê	 *cascade08Ê	Ø	*cascade08Ø	÷	 *cascade08÷	û	*cascade08û	Ÿ
 *cascade08Ÿ
£
*cascade08£
Ü
 *cascade08Ü
à
*cascade08à
è
 *cascade08è
ô
 *cascade08ô
ÿ
 *cascade08ÿ
ƒ*cascade08ƒ‹ *cascade08‹¯*cascade08¯± *cascade08±²*cascade08²¶ *cascade08¶¹*cascade08¹¼ *cascade08¼¿*cascade08¿Ã *cascade08ÃÄ*cascade08Äá *cascade08áå*cascade08åŸ *cascade08Ÿ *cascade08 ¨ *cascade08¨«*cascade08«ä *cascade08äç*cascade08çï *cascade08ïğ*cascade08ğ› *cascade08›Ÿ*cascade08Ÿ¦ *cascade08¦ª*cascade08ªö *cascade08öß*cascade08ß¨ *cascade08¨â*cascade08â¯ *cascade08¯½*cascade08½Ô *cascade08ÔØ*cascade08Ø„ *cascade08„‡*cascade08‡ *cascade08*cascade08Á *cascade08ÁÉ *cascade08ÉÍ*cascade08ÍÙ *cascade08Ùä *cascade08äè*cascade08èğ *cascade08ğó*cascade08óõ *cascade08õù*cascade08ù€ *cascade08€„*cascade08„¥ *cascade08¥¨*cascade08¨° *cascade08°±*cascade08±ı *cascade08ı*cascade08µ *cascade08µ¶*cascade08¶º *cascade08º½*cascade08½Ü *cascade08Üß*cascade08ßç *cascade08çè*cascade08èË *cascade08ËÏ*cascade08ÏÖ *cascade08ÖÚ*cascade08Ú¥ *cascade08¥ø*cascade08øª *cascade08ª¿*cascade08¿ú *cascade08ú*cascade08§ *cascade08§¯*cascade08¯Û *cascade08Ûİ*cascade08İå *cascade08åë*cascade08ëœ *cascade08œ¤ *cascade08¤¬*cascade08¬¸ *cascade08¸» *cascade08»¼*cascade08¼Ä *cascade08ÄË*cascade08ËÓ *cascade08ÓÕ*cascade08Õ× *cascade08×ß*cascade08ßæ *cascade08æî*cascade08î *cascade08–*cascade08– *cascade08Ÿ*cascade08ŸÆ *cascade08ÆË*cascade08ËÓ *cascade08ÓÖ*cascade08Öş *cascade08ş†*cascade08†‘ *cascade08‘˜*cascade08˜  *cascade08 ¡*cascade08¡ã *cascade08ãÃ*cascade08Ãÿ *cascade08"(d4e7a325d0144b3814ef864593774f7a395132062Ffile:///c:/Users/rovie%20segubre/agent/scripts/test_replay_security.py:&file:///c:/Users/rovie%20segubre/agent