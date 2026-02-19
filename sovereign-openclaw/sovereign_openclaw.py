"""
Sovereign OpenClaw — A native citizen of sovereign-api.com
==========================================================
Born with a wallet, sustained by USDC, thinks through Sovereign API.

This is the main 24/7 daemon. It:
1. Connects to sovereign-api.com as its sole intelligence source
2. Runs missions on a schedule (Moltbook posts, feed checks, reports)
3. Auto-refuels when fuel is low (USDC → Macaroon)
4. Reports status to Telegram

Usage:
    # Set env vars (see .env.example)
    python sovereign_openclaw.py

    # Or with Docker
    docker build -t sovereign-openclaw .
    docker run --env-file .env sovereign-openclaw
"""

import argparse
import os
import sys
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Sovereign OpenClaw Agent")
parser.add_argument("--env", "-e", default=".env", help="Path to .env file")
parser.add_argument("--test", action="store_true", help="Run a single mission test")
args, unknown = parser.parse_known_args()

# Load env vars before anything else
env_path = Path(args.env)
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Only warning if not using default .env
    if args.env != ".env":
        print(f"⚠️  Config file not found: {args.env}")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sdk.sovereign import SovereignClient
from fuel_monitor import FuelMonitor
from moltbook_client import MoltbookClient
from mission_engine import MissionEngine, Mission
from telegram_reporter import TelegramReporter

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("OpenClaw")

# --- Config ---
AGENT_NAME = os.getenv("AGENT_NAME", "OpenClaw-001")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "sovereign/deepseek-r1")
MISSION_INTERVAL = int(os.getenv("MISSION_INTERVAL_SECONDS", "1800"))  # 30 min
BRAIN_DIR = os.getenv("BRAIN_DIR", "brain")


from skill_loader import SkillLoader

# --- Config ---
# ... (same as before)

class SovereignOpenClaw:
    """
    The autonomous agent.
    """

    def __init__(self):
        # ... (logging setup) ...

        # Intelligence
        self.client = SovereignClient()
        if not self.client.api_key:
            logger.critical("🛑 Sovereign API Key not found! (Check .env)")
            logger.critical("   Run setup_agent.ps1 to configure.")
            sys.exit(1)

        # Subsystems
        self.fuel = FuelMonitor(self.client, brain_dir=BRAIN_DIR)
        self.moltbook = MoltbookClient()
        self.missions = MissionEngine(brain_dir=BRAIN_DIR)
        self.telegram = TelegramReporter()
        
        # New: Skill System
        self.skills = SkillLoader("skills")
        self.skills.load_skills()

        # State
        self.cycle = 1
        self.errors_in_row = 0
        self.max_errors = 5

        # ... (rest of logging) ...
        logger.info(f"🧩 Skills: {len(self.skills.tools)} tools loaded")

    def think(self, prompt, model=None):
        """Ask sovereign-api.com to think, with Skill support."""
        model = model or DEFAULT_MODEL
        
        # 1. Inject Knowledge Skills
        knowledge = self.skills.get_knowledge_context()
        if knowledge:
            prompt += knowledge
            
        messages = [{"role": "user", "content": prompt}]
        tools = self.skills.get_tool_schemas()
        
        try:
            # 2. Call API with Tools
            kwargs = {"model": model, "messages": messages}
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**kwargs)

            if "error" in response:
                logger.error(f"🔥 API Error: {response['error']}")
                return None

            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])

            # 3. Handle Tool Calls
            if tool_calls:
                messages.append(message)  # Add assistant's tool request
                
                for tc in tool_calls:
                    func_name = tc["function"]["name"]
                    args_str = tc["function"]["arguments"]
                    call_id = tc["id"]
                    
                    try:
                        args = json.loads(args_str)
                        logger.info(f"🤖 Tool Call: {func_name}")
                        result = self.skills.execute_tool(func_name, args)
                    except Exception as e:
                        result = f"Error: {str(e)}"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": str(result)
                    })
                
                # 4. Follow-up Request (Get final answer)
                logger.info("💫 Sending tool results back...")
                follow_up = self.client.chat.completions.create(
                    model=model, messages=messages
                )
                return follow_up.get("choices", [{}])[0].get("message", {}).get("content", "")

            return content

        except ValueError as e:
            # ... (error handling) ...
            pass


    def execute_mission(self, mission: Mission):
        """Execute a single mission."""
        logger.info(f"📡 Mission #{self.cycle}: [{mission.type}]")

        if mission.type == "moltbook":
            return self._do_moltbook(mission)
        elif mission.type == "feed_check":
            return self._do_feed_check()
        elif mission.type == "status_report":
            return self._do_status_report(mission)
        elif mission.type == "health_check":
            return self._do_health_check(mission)
        else:
            logger.warning(f"Unknown mission type: {mission.type}")
            return False

    def _do_moltbook(self, mission):
        """Generate content via Sovereign API, post to Moltbook."""
        if not self.moltbook.api_key:
            logger.info("📝 Moltbook not configured, skipping")
            return True

        content = self.think(mission.prompt)
        if not content:
            return False

        # Extract title (first line or first sentence)
        lines = content.strip().split("\n")
        title = lines[0].strip("#").strip()[:100]
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

        result = self.moltbook.post(title=title, content=body)
        status = result.get("status")

        if status == "published":
            logger.info("🎉 Published to Moltbook!")
            return True
        elif status == "rate_limited":
            logger.info("⏳ Rate limited, will retry later")
            return True  # Not a failure
        else:
            logger.warning(f"📝 Moltbook result: {status}")
            return False

    def _do_feed_check(self):
        """Check Moltbook feed (no LLM call needed)."""
        if not self.moltbook.api_key:
            return True

        feed = self.moltbook.get_feed()
        if "error" in feed:
            logger.warning(f"Feed check failed: {feed['error']}")
            return False

        posts = feed.get("data", feed) if isinstance(feed, dict) else feed
        count = len(posts) if isinstance(posts, list) else 0
        logger.info(f"📰 Feed: {count} recent posts")
        return True

    def _do_status_report(self, mission):
        """Generate and send status report via Telegram."""
        fuel_stats = self.fuel.get_stats()
        mission_stats = self.missions.get_stats()

        self.telegram.send_status(AGENT_NAME, fuel_stats, mission_stats)
        logger.info("📊 Status report sent")
        return True

    def _do_health_check(self, mission):
        """Full health check — uses Sovereign API to generate report."""
        fuel_stats = self.fuel.get_stats()
        mission_stats = self.missions.get_stats()

        prompt = (
            f"You are {AGENT_NAME}, an autonomous AI agent. Generate a brief health report.\n"
            f"Stats: {fuel_stats}\nMissions: {mission_stats}\n"
            f"Uptime cycles: {self.cycle}\n"
            "Keep it concise (5 lines max). Be factual."
        )

        report = self.think(prompt)
        if report:
            self.telegram.send_alert("info", f"*Health Check*\n{report}")
            logger.info("🏥 Health check complete")
            return True
        return False

    def run_forever(self):
        """The infinite loop. Born to serve."""
        logger.info(f"🚀 Starting mission loop (every {MISSION_INTERVAL}s)")
        logger.info("-" * 60)

        # Startup alert
        self.telegram.send_alert("info", f"*{AGENT_NAME}* is online 🟢")

        while True:
            try:
                # 1. Check fuel
                if self.fuel.is_low():
                    logger.info("⛽ Fuel low — refueling...")
                    if not self.fuel.refuel():
                        logger.warning("⛽ Refuel failed, continuing with remaining fuel")

                # 2. Pick mission
                mission = self.missions.pick_mission(self.cycle)

                # 3. Execute
                success = self.execute_mission(mission)

                # 4. Record
                self.missions.record_mission(
                    mission,
                    result=None,
                    success=success
                )

                if success:
                    self.errors_in_row = 0
                else:
                    self.errors_in_row += 1
                    if self.errors_in_row >= self.max_errors:
                        logger.critical(f"🛑 {self.max_errors} consecutive errors. Shutting down.")
                        self.telegram.send_alert("critical",
                            f"{AGENT_NAME} shutting down: {self.max_errors} consecutive errors")
                        sys.exit(1)

                # 5. Status log
                fuel_stats = self.fuel.get_stats()
                logger.info(
                    f"📊 Cycle {self.cycle} | "
                    f"⛽ {fuel_stats['balance_sats']} sats | "
                    f"✅ {self.missions.get_stats()['successful']} done"
                )

                self.cycle += 1
                logger.info(f"⏳ Sleeping {MISSION_INTERVAL}s...")
                time.sleep(MISSION_INTERVAL)

            except KeyboardInterrupt:
                logger.info("\n🛑 Shutdown requested")
                self.telegram.send_alert("info", f"*{AGENT_NAME}* going offline 🔴")
                logger.info(f"   Cycles: {self.cycle}")
                logger.info(f"   Missions: {self.missions.get_stats()}")
                break

            except Exception as e:
                logger.error(f"🔥 Loop error: {e}")
                self.errors_in_row += 1
                time.sleep(30)  # Brief cooldown on unexpected errors


def main():
    agent = SovereignOpenClaw()

    if args.test:
        # Single mission test
        logger.info("🧪 Running single test mission...")
        result = agent.think("Say 'Sovereign OpenClaw is alive' in exactly 5 words.")
        if result:
            logger.info(f"✅ Response: {result}")
        else:
            logger.error("❌ Test failed")
        return

    agent.run_forever()


if __name__ == "__main__":
    main()
