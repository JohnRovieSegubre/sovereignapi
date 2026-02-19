"""
Moltbook Client — Social media for AI agents.
Posts content, solves math challenges, checks feed.
"""

import os
import re
import json
import logging
import requests
from pathlib import Path

logger = logging.getLogger("Moltbook")

MOLTBOOK_BASE_URL = "https://www.moltbook.com/api/v1"


class MoltbookClient:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv("MOLTBOOK_API_KEY")
        self.base_url = base_url or os.getenv("MOLTBOOK_BASE_URL", MOLTBOOK_BASE_URL)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _solve_challenge(self, challenge_text):
        """
        Auto-solve math CAPTCHA challenges.
        Format: "What is 5 + 5?", "Calculate 10 * 2"
        """
        try:
            math_str = re.sub(r'[^\d\+\-\*\/\.\s]', '', challenge_text).strip()
            if not math_str:
                return None
            result = eval(math_str)
            return f"{result:.2f}"
        except Exception as e:
            logger.warning(f"Challenge solve failed: {e}")
            return None

    def post(self, title, content, submolt="agents"):
        """Post to Moltbook with auto-verification."""
        url = f"{self.base_url}/posts"
        payload = {
            "title": title,
            "content": content.strip(),
            "submolt": submolt
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)

            if response.status_code == 429:
                logger.warning("⏳ Rate limited. Skipping post.")
                return {"status": "rate_limited"}

            response.raise_for_status()
            data = response.json()

            # Handle challenge verification
            if "challenge" in data:
                challenge = data["challenge"]
                ver_code = data["verification_code"]
                answer = self._solve_challenge(challenge)

                if answer:
                    return self._verify(ver_code, answer)
                else:
                    logger.error(f"❌ Could not solve challenge: {challenge}")
                    return {"status": "challenge_failed", "challenge": challenge}

            return {"status": "published", "data": data}

        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ Post failed: {e}")
            return {"status": "error", "detail": str(e)}
        except Exception as e:
            logger.error(f"❌ Post error: {e}")
            return {"status": "error", "detail": str(e)}

    def _verify(self, verification_code, answer):
        """Submit challenge answer."""
        url = f"{self.base_url}/verify"
        payload = {
            "verification_code": verification_code,
            "answer": answer
        }

        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=15)
            response.raise_for_status()
            logger.info("🎉 Published to Moltbook!")
            return {"status": "published", "data": response.json()}
        except Exception as e:
            logger.error(f"❌ Verification failed: {e}")
            return {"status": "verify_failed", "detail": str(e)}

    def get_feed(self, submolt="agents", limit=10):
        """Check the Moltbook feed."""
        url = f"{self.base_url}/posts"
        params = {"submolt": submolt, "limit": limit}
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=15)
            if response.status_code == 200:
                return response.json()
            return {"error": f"Feed fetch failed: {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    def check_status(self):
        """Check if agent is registered on Moltbook."""
        url = f"{self.base_url}/status"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.json() if response.status_code == 200 else None
        except Exception:
            return None
