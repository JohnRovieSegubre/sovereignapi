¨C"""
SovereignWallet - The Grand Unified Client
==========================================
A Bearer Asset Wallet for Autonomous AI Agents.

This class handles the complete economic lifecycle:
1. Stores the current Macaroon token (the "Cash")
2. Attaches it to requests automatically
3. Captures the "Change" token from server responses
4. Swaps tokens atomically (preventing replay attacks)

Usage:
    from wallet_client import SovereignWallet
    
    wallet = SovereignWallet()
    response = wallet.think("What is 2+2?")
    print(response)
"""

import httpx
import json
import sys
import time
import os
from pathlib import Path

# --- CONFIGURATION ---
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8000/v1/chat/completions")
DEFAULT_MODEL = "sovereign/deepseek-r1"  # 10 sats per request

# Unified storage path (single source of truth)
WALLET_DIR = Path(__file__).parent / ".agent" / "wallet"
WALLET_FILE = WALLET_DIR / "wallet.json"


class SovereignWallet:
    """
    A self-managing cryptographic wallet for AI agents.
    
    The wallet automatically rotates tokens after each successful request,
    ensuring the agent never attempts to re-spend a used token.
    """
    
    def __init__(self, storage_path=None):
        print(f"ğŸ”Œ [WALLET] Using Gateway: {GATEWAY_URL}")
        self.storage_path = Path(storage_path) if storage_path else WALLET_FILE
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.token = self._load_token()
        self.last_balance = None  # Track spending (future feature)
    
    def _load_token(self):
        """Load the current token from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    return data.get("access_token")
            except (json.JSONDecodeError, IOError):
                return None
        return None
    
    def save_token(self, token):
        """Atomically save the new token to disk."""
        self.token = token
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump({"access_token": token, "saved_at": time.time()}, f)
    
    def get_balance(self):
        """Extract balance from current token (if possible)."""
        if not self.token:
            return 0
        # Note: Full balance extraction requires pymacaroons
        # For now, return a placeholder indicating token exists
        return "Token Loaded" if self.token else 0
    
    def top_up(self, tx_hash, max_attempts=12, poll_interval=5):
        """
        Polls the Gateway to claim a token after sending crypto.
        
        Args:
            tx_hash: The blockchain transaction hash from the deposit.
            max_attempts: Number of polling attempts (default 12 = 60 seconds).
            poll_interval: Seconds between attempts.
        
        Returns:
            True if token claimed successfully, False otherwise.
        """
        claim_url = GATEWAY_URL.replace("/chat/completions", "/balance/claim")
        print(f"\nğŸ’³ [WALLET] Waiting for confirmation of {tx_hash[:16]}...")
        
        for i in range(max_attempts):
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(claim_url, json={"tx_hash": tx_hash})
                    
                    if resp.status_code == 200:
                        token = resp.json().get("access_token")
                        self.save_token(token)
                        print(f"\nâœ… [SUCCESS] Deposit confirmed! Wallet recharged.")
                        return True
                    
                    elif resp.status_code == 410:
                        print(f"\nâš ï¸ [ALREADY CLAIMED] Token was already picked up.")
                        return False
                    
                    elif resp.status_code == 404:
                        # Not ready yet, keep polling
                        print(".", end="", flush=True)
                        
            except Exception as e:
                print(f"!", end="", flush=True)  # Connection error indicator
            
            time.sleep(poll_interval)
        
        print(f"\nâ±ï¸ [TIMEOUT] Deposit not seen after {max_attempts * poll_interval}s.")
        print("   The Watcher may still be catching up. Try again later.")
        return False
    
    def think(self, prompt, model=DEFAULT_MODEL):
        """
        Send a thought to the AI and handle the economic lifecycle.
        
        This is the primary interface for autonomous agents.
        Returns the AI response content, or None on failure.
        """
        if not self.token:
            print("âŒ [WALLET] Empty! No token available.")
            print("   Mint one with: python -c \"import requests; ...\"")
            return None
        
        print(f"\nğŸ“¤ [WALLET] Spending token: {self.token[:15]}...")
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        
        try:
            start_time = time.time()
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(GATEWAY_URL, json=payload, headers=headers)
            duration = time.time() - start_time
            
            # === SUCCESS: Capture Change ===
            if resp.status_code == 200:
                print(f"âœ… [SUCCESS] Response in {duration:.1f}s")
                
                # THE CRITICAL STEP: Token Rotation
                new_token = resp.headers.get("X-Sovereign-Balance-Token")
                if new_token:
                    self.save_token(new_token)
                    print("ğŸ’¾ [WALLET] Token rotated and saved.")
                else:
                    print("âš ï¸ [WARNING] No change token received!")
                
                return resp.json()["choices"][0]["message"]["content"]
            
            # === PAYMENT REQUIRED: Out of funds ===
            elif resp.status_code == 402:
                print("ğŸ’¸ [EMPTY] Insufficient funds!")
                data = resp.json()
                print(f"   Invoice: {data.get('invoice', 'N/A')[:30]}...")
                print(f"   Price: {data.get('price_sats', '?')} sats")
                # Future: Auto-pay via Alby/LND
                return None
            
            # === FORBIDDEN: Replay detected ===
            elif resp.status_code == 403:
                error = resp.json().get("error", "Unknown")
                print(f"ğŸ›‘ [BLOCKED] {error}")
                print("   Token was already spent. Wallet needs refresh.")
                return None
            
            # === UNEXPECTED ===
            else:
                print(f"â“ [ERROR] {resp.status_code}: {resp.text[:100]}")
                return None
                
        except httpx.TimeoutException:
            print("â±ï¸ [TIMEOUT] Request took too long.")
            return None
        except Exception as e:
            print(f"ğŸ”¥ [CRITICAL] {e}")
            return None


# === CLI Interface ===
if __name__ == "__main__":
    wallet = SovereignWallet()
    
    print("ğŸ§  Sovereign Agent Interface (Grand Unified Wallet)")
    print("=" * 50)
    print(f"   Storage: {wallet.storage_path}")
    print(f"   Token:   {'Loaded' if wallet.token else 'EMPTY'}")
    print("=" * 50)
    
    # CLI mode: single prompt
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        result = wallet.think(prompt)
        if result:
            print(f"\nğŸ¤– {result}\n")
    
    # Interactive mode
    else:
        print("\nType 'exit' to quit.\n")
        while True:
            try:
                user_input = input("ğŸ—£ï¸ You: ").strip()
                if user_input.lower() in ["exit", "quit", "q"]:
                    break
                if not user_input:
                    continue
                result = wallet.think(user_input)
                if result:
                    print(f"\nğŸ¤– AI: {result}\n")
            except (KeyboardInterrupt, EOFError):
                print("\nğŸ‘‹ Goodbye!")
                break
¸*cascade08¸ß *cascade08ßì*cascade08ì÷*cascade08÷Ÿ *cascade08Ÿ¦*cascade08¦º *cascade08ºÓ*cascade08Óş *cascade08şÿ*cascade08ÿ *cascade08› *cascade08›¤*cascade08¤ô *cascade08ôû *cascade08ûü*cascade08üı *cascade08ış*cascade08ş¥ *cascade08¥¦*cascade08¦§ *cascade08§ª*cascade08ª¬ *cascade08¬Æ*cascade08ÆÚ *cascade08ÚÜ*cascade08Üø *cascade08øÜ	*cascade08Ü	û	 *cascade08û	€
*cascade08€
Œ
 *cascade08Œ
Ê
*cascade08Ê
ğ
 *cascade08ğ
‘*cascade08‘ *cascade08Ê*cascade08Êğ *cascade08ğ¡*cascade08¡  *cascade08 ¢*cascade08¢£ *cascade08£¦*cascade08¦³ *cascade08³Ô*cascade08Ôü *cascade08üœ*cascade08œÑ *cascade08ÑÕ*cascade08Õ *cascade08·*cascade08·Ó *cascade08Ó˜*cascade08˜í *cascade08í†*cascade08† *cascade08‘*cascade08‘› *cascade08›œ*cascade08œŸ *cascade08Ÿ¤*cascade08¤· *cascade08·½*cascade08½¾ *cascade08¾À*cascade08ÀÁ *cascade08ÁÃ*cascade08ÃÅ *cascade08ÅÓ*cascade08ÓÔ *cascade08ÔÕ*cascade08Õ× *cascade08×Ú*cascade08ÚÛ *cascade08Ûè*cascade08èé *cascade08éø*cascade08øù *cascade08ùû*cascade08ûü *cascade08üş*cascade08şÿ *cascade08ÿ€*cascade08€‚ *cascade08‚ƒ*cascade08ƒ„ *cascade08„Š*cascade08Š” *cascade08” *cascade08 ª *cascade08ª¿*cascade08¿À *cascade08ÀÃ*cascade08ÃÄ *cascade08ÄË*cascade08ËÌ *cascade08ÌÏ*cascade08ÏĞ *cascade08ĞÑ*cascade08ÑÓ *cascade08Óà*cascade08àá *cascade08áë*cascade08ëì *cascade08ìî*cascade08îï *cascade08ïô*cascade08ôö *cascade08öù*cascade08ùû *cascade08ûü*cascade08üş *cascade08ş‹*cascade08‹ *cascade08”*cascade08”• *cascade08•—*cascade08—˜ *cascade08˜*cascade08© *cascade08©¿*cascade08¿Ì *cascade08Ìä *cascade08äÿ#*cascade08ÿ#¦$ *cascade08¦$±$ *cascade08±$¹$*cascade08¹$½$ *cascade08½$¿$*cascade08¿$À$ *cascade08À$Ã$*cascade08Ã$Ä$ *cascade08Ä$Å$*cascade08Å$È$ *cascade08È$Ë$*cascade08Ë$Í$ *cascade08Í$Ï$*cascade08Ï$Ğ$ *cascade08Ğ$Ò$*cascade08Ò$Ó$ *cascade08Ó$×$*cascade08×$Ø$ *cascade08Ø$à$*cascade08à$á$ *cascade08á$å$*cascade08å$ç$ *cascade08ç$ï$*cascade08ï$ğ$ *cascade08ğ$ñ$*cascade08ñ$ò$ *cascade08ò$÷$*cascade08÷$ø$ *cascade08ø$ù$*cascade08ù$ƒ% *cascade08ƒ%…%*cascade08…%‰% *cascade08‰%™%*cascade08™%œ% *cascade08œ%¢%*cascade08¢%¤% *cascade08¤%§%*cascade08§%¨% *cascade08¨%©%*cascade08©%ª% *cascade08ª%±%*cascade08±%²% *cascade08²%³%*cascade08³%´% *cascade08´%¹%*cascade08¹%º% *cascade08º%¿%*cascade08¿%À% *cascade08À%Í%*cascade08Í%Î% *cascade08Î%Ï%*cascade08Ï%Ğ% *cascade08Ğ%Õ%*cascade08Õ%Ö% *cascade08Ö%Ù%*cascade08Ù%Ú% *cascade08Ú%á%*cascade08á%â% *cascade08â%ç%*cascade08ç%è% *cascade08è%í%*cascade08í%ï% *cascade08ï%ğ%*cascade08ğ%ñ% *cascade08ñ%ò%*cascade08ò%ó% *cascade08ó%õ%*cascade08õ%ö% *cascade08ö%ş%*cascade08ş%ÿ% *cascade08ÿ%‰&*cascade08‰&Š& *cascade08Š&Œ&*cascade08Œ&–& *cascade08–&&*cascade08& & *cascade08 &¥&*cascade08¥&¦& *cascade08¦&§&*cascade08§&½& *cascade08½&Á&*cascade08Á&Ã& *cascade08Ã&È&*cascade08È&Ê& *cascade08Ê&Ñ&*cascade08Ñ&Ú& *cascade08Ú&ã&*cascade08ã&ä& *cascade08ä&í&*cascade08í&î& *cascade08î&ô&*cascade08ô&õ& *cascade08õ&ö&*cascade08ö&ø& *cascade08ø&ü&*cascade08ü&ı& *cascade08ı&ÿ&*cascade08ÿ&' *cascade08'ˆ'*cascade08ˆ'Š' *cascade08Š'™'*cascade08™'š' *cascade08š'Ÿ'*cascade08Ÿ'§' *cascade08§'©'*cascade08©'ª' *cascade08ª'ã'*cascade08ã'ä' *cascade08ä'ş'*cascade08ş'ÿ' *cascade08ÿ'‚(*cascade08‚(ƒ( *cascade08ƒ(ˆ(*cascade08ˆ(‰( *cascade08‰(Œ(*cascade08Œ(( *cascade08((*cascade08(( *cascade08(™(*cascade08™(( *cascade08(¦(*cascade08¦(¤) *cascade08¤)¼**cascade08¼*Ê* *cascade08Ê*ğ**cascade08ğ*‡, *cascade08‡,,*cascade08,, *cascade08,‘,*cascade08‘,’, *cascade08’,,*cascade08,, *cascade08,Ÿ,*cascade08Ÿ, , *cascade08 ,ª,*cascade08ª,³, *cascade08³,º,*cascade08º,Ã, *cascade08Ã,Æ,*cascade08Æ,È, *cascade08È,Ü,*cascade08Ü,İ, *cascade08İ,ß,*cascade08ß,á, *cascade08á,â,*cascade08â,ä, *cascade08ä,ç,*cascade08ç,¨- *cascade08¨-©-*cascade08©-®- *cascade08®-¯-*cascade08¯-°- *cascade08°-·-*cascade08·-Á- *cascade08Á-Ç-*cascade08Ç-È- *cascade08È-Ê-*cascade08Ê-Ë- *cascade08Ë-Î-*cascade08Î-Ï- *cascade08Ï-Ó-*cascade08Ó-ü- *cascade08ü-ı-*cascade08ı-€. *cascade08€.….*cascade08….†. *cascade08†.Š.*cascade08Š.‹. *cascade08‹..*cascade08.œ/ *cascade08œ/È/*cascade08È/Ó/ *cascade08Ó/×/*cascade08×/Ø/ *cascade08Ø/à/*cascade08à/ç/ *cascade08ç/è/*cascade08è/ë/ *cascade08ë/ì/*cascade08ì/í/ *cascade08í/ï/*cascade08ï/ñ/ *cascade08ñ/ô/*cascade08ô/õ/ *cascade08õ/ö/*cascade08ö/÷/ *cascade08÷/ø/*cascade08ø/‰0 *cascade08‰0”0*cascade08”0 0 *cascade08 0«0*cascade08«0¬0 *cascade08¬0­0*cascade08­0®0 *cascade08®0Æ0*cascade08Æ0Ç0 *cascade08Ç0È0*cascade08È0É0 *cascade08É0Ê0*cascade08Ê0Ï0 *cascade08Ï0Ú0*cascade08Ú0Ã1 *cascade08Ã1Í1*cascade08Í1Ó1 *cascade08Ó1Ö1*cascade08Ö1Ø1 *cascade08Ø1Ş1*cascade08Ş1à1 *cascade08à1ã1*cascade08ã1ä1 *cascade08ä1ê1*cascade08ê1î1 *cascade08î1ï1*cascade08ï1ğ1 *cascade08ğ1ô1*cascade08ô1õ1 *cascade08õ1ù1*cascade08ù1½2 *cascade08½2Á2*cascade08Á2Â2 *cascade08Â2É2*cascade08É2Ê2 *cascade08Ê2Ó2*cascade08Ó2×2 *cascade08×2Ø2*cascade08Ø2Ù2 *cascade08Ù2Ú2*cascade08Ú2Û2 *cascade08Û2İ2*cascade08İ2•3 *cascade08•33*cascade083 3 *cascade08 3¡3*cascade08¡3§3 *cascade08§3¨3*cascade08¨3©3 *cascade08©3ª3*cascade08ª3³3 *cascade08³3´3*cascade08´3»3 *cascade08»3Í3*cascade08Í3á3 *cascade08á3é3*cascade08é3ì3 *cascade08ì3ò3*cascade08ò3ó3 *cascade08ó3ş3*cascade08ş34 *cascade084†4*cascade08†4‡4 *cascade08‡4Š4*cascade08Š4‹4 *cascade08‹44*cascade084‘4 *cascade08‘4•4*cascade08•4©4 *cascade08©4ª4*cascade08ª4«4 *cascade08«4²4*cascade08²4³4 *cascade08³4»4*cascade08»4¼4 *cascade08¼4¿4*cascade08¿4À4 *cascade08À4Ú4*cascade08Ú4Û4 *cascade08Û4Ü4*cascade08Ü4İ4 *cascade08İ4á4*cascade08á4â4 *cascade08â4ø4*cascade08ø4ù4 *cascade08ù4‰5*cascade08‰5Š5 *cascade08Š5‹5*cascade08‹55 *cascade0855*cascade085’5 *cascade08’5–5*cascade08–5™5 *cascade08™5›5*cascade08›5œ5 *cascade08œ55*cascade0855 *cascade085Ÿ5*cascade08Ÿ5 5 *cascade08 5§5*cascade08§5¨5 *cascade08¨5¯5*cascade08¯5³5 *cascade08³5´5*cascade08´5µ5 *cascade08µ5¹5*cascade08¹5º5 *cascade08º5¾5*cascade08¾5¿5 *cascade08¿5Ğ5*cascade08Ğ5â5 *cascade08â5ç5*cascade08ç5è5 *cascade08è5é5*cascade08é5ê5 *cascade08ê5í5*cascade08í5î5 *cascade08î5ò5*cascade08ò5ó5 *cascade08ó5ø5*cascade08ø5û5 *cascade08û5ƒ6*cascade08ƒ6„6 *cascade08„6Œ6*cascade08Œ6§6 *cascade08§6¶6*cascade08¶6¸6 *cascade08¸6¼6*cascade08¼6Ñ6 *cascade08Ñ6Ø6*cascade08Ø6Û6 *cascade08Û6à6*cascade08à6á6 *cascade08á6î6*cascade08î6ï6 *cascade08ï6ğ6*cascade08ğ6ò6 *cascade08ò6‰7*cascade08‰7ª7 *cascade08ª7ª7*cascade08ª7¶7 *cascade08¶7¸7*cascade08¸7¹7 *cascade08¹7¾7*cascade08¾7Ä7 *cascade08Ä7Å7*cascade08Å7Æ7 *cascade08Æ7É7*cascade08É7Ê7 *cascade08Ê7Ô7*cascade08Ô7Õ7 *cascade08Õ7Ú7*cascade08Ú7…8 *cascade08…8ˆ8*cascade08ˆ8‰8 *cascade08‰88*cascade088‘8 *cascade08‘8’8*cascade08’8“8 *cascade08“8 8*cascade08 8¢8 *cascade08¢8£8*cascade08£8¯8 *cascade08¯8µ8*cascade08µ8ñ8 *cascade08ñ8‘9*cascade08‘9¤9 *cascade08¤9ª9*cascade08ª9«9 *cascade08«9±9*cascade08±9²9 *cascade08²9¶9*cascade08¶9·9 *cascade08·9¹9*cascade08¹9º9 *cascade08º9»9*cascade08»9½9 *cascade08½9¾9*cascade08¾9¿9 *cascade08¿9Á9*cascade08Á9Ä9 *cascade08Ä9Å9*cascade08Å9Æ9 *cascade08Æ9Ê9*cascade08Ê9¡: *cascade08¡:¢:*cascade08¢:£: *cascade08£:§:*cascade08§:¨: *cascade08¨:«:*cascade08«:Î: *cascade08Î:é:*cascade08é:¢; *cascade08¢;Å;*cascade08Å;Æ; *cascade08Æ;Ë;*cascade08Ë;Ì; *cascade08Ì;ì;*cascade08ì;ó; *cascade08ó;‚<*cascade08‚<ˆ< *cascade08ˆ<’<*cascade08’<”< *cascade08”<»<*cascade08»<¼< *cascade08¼<è<*cascade08è<é< *cascade08é<ê<*cascade08ê<ì< *cascade08ì<™=*cascade08™=¡= *cascade08¡=°=*cascade08°=ú= *cascade08ú=ÿ=*cascade08ÿ=€> *cascade08€>‚>*cascade08‚>ƒ> *cascade08ƒ>‹>*cascade08‹>Œ> *cascade08Œ>›>*cascade08›>¥> *cascade08¥>«>*cascade08«>¬> *cascade08¬>Ï>*cascade08Ï>Ğ> *cascade08Ğ>é>*cascade08é>ë> *cascade08ë>‹?*cascade08‹?? *cascade08?–?*cascade08–?—? *cascade08—??*cascade08?? *cascade08?Ÿ?*cascade08Ÿ? ? *cascade08 ?¢?*cascade08¢?£? *cascade08£?ª?*cascade08ª?«? *cascade08«?¹?*cascade08¹?º? *cascade08º?»?*cascade08»?¼? *cascade08¼?¿?*cascade08¿?À? *cascade08À?Ã?*cascade08Ã?Å? *cascade08Å?æ?*cascade08æ?é? *cascade08é?î?*cascade08î?ğ? *cascade08ğ?‚@*cascade08‚@„@ *cascade08„@Š@*cascade08Š@‹@ *cascade08‹@’@*cascade08’@“@ *cascade08“@®@*cascade08®@¯@ *cascade08¯@³@*cascade08³@´@ *cascade08´@·@*cascade08·@¸@ *cascade08¸@½@*cascade08½@¾@ *cascade08¾@è@*cascade08è@ê@ *cascade08ê@ş@*cascade08ş@ÿ@ *cascade08ÿ@A*cascade08A‚A *cascade08‚A„A*cascade08„A…A *cascade08…AŠA*cascade08ŠAŒA *cascade08ŒAA*cascade08AA *cascade08AA*cascade08A’A *cascade08’A®A*cascade08®A´A *cascade08´AÀA*cascade08ÀAÑA *cascade08ÑAÒA*cascade08ÒAÔA *cascade08ÔAÖA*cascade08ÖAÛA *cascade08ÛAİA*cascade08İAŞA *cascade08ŞAßA*cascade08ßAãA *cascade08ãAïA*cascade08ïAÿA *cascade08ÿA‹B*cascade08‹B™B *cascade08™BšB*cascade08šBB *cascade08B¡B*cascade08¡B¤B *cascade08¤B¥B*cascade08¥B¦B *cascade08¦B°B*cascade08°B¼B *cascade08¼BÄB*cascade08ÄBÅB *cascade08ÅBÎB*cascade08ÎBÏB *cascade08ÏBÑB*cascade08ÑBÔB *cascade08ÔBÖB*cascade08ÖB×B *cascade08×BØB*cascade08ØBÙB *cascade08ÙBãB*cascade08ãBäB *cascade08äBåB*cascade08åBçB *cascade08çBìB*cascade08ìBôB *cascade08ôB÷B*cascade08÷BşB *cascade08şBC*cascade08CC *cascade08C‘C*cascade08‘C“C *cascade08“C¦C*cascade08¦C¨C *cascade08"(d4e7a325d0144b3814ef864593774f7a3951320627file:///c:/Users/rovie%20segubre/agent/wallet_client.py:&file:///c:/Users/rovie%20segubre/agent