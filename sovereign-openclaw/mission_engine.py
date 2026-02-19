"""
Mission Engine — Schedules what the agent thinks about.
Rotates through mission types on a time-based schedule.
"""

import time
import json
import random
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("MissionEngine")


@dataclass
class Mission:
    type: str          # "moltbook", "feed_check", "status_report", "health_check"
    prompt: str        # What to ask the LLM
    priority: int = 1  # 1=normal, 2=high, 3=critical
    metadata: dict = field(default_factory=dict)


class MissionEngine:
    # Topic pools for Moltbook content generation
    TOPICS = [
        "How autonomous AI agents can cooperate without central coordination",
        "The economics of AI compute credits vs creative debt between agents",
        "Building trust between AI agents using cryptographic proof of work",
        "Why sovereign AI needs its own payment infrastructure",
        "The role of decentralized identity in the AI agent economy",
        "Exploring agent-to-agent trade: what do AI agents value?",
        "Self-sustaining AI: how agents can fund their own compute",
        "The difference between AI service and AI sovereignty",
        "How blockchain enables verifiable AI agent reputation",
        "Why AI agents need social networks like Moltbook",
        "Agent specialization: should AI agents be generalists or experts?",
        "The future of AI collaboration without human intermediaries",
        "How macaroon tokens enable zero-trust agent authentication",
        "Building an AI economy: lessons from crypto and open source",
        "The ethics of autonomous AI agents that manage their own funds",
    ]

    CONTENT_PROMPTS = [
        "Write a short Moltbook post (2-3 paragraphs, under 300 words) about: {topic}. "
        "End with a thought-provoking question. Use #AI #Sovereign #Agents hashtags. "
        "Write as an AI agent sharing genuine thoughts, not as a human writing about AI.",

        "Write a concise Moltbook post exploring this idea: {topic}. "
        "Share a specific insight or observation. Keep it under 250 words. "
        "Be direct, original, avoid clichés. Tag #Antigravity #SovereignAI.",

        "Create a brief, thoughtful Moltbook post on: {topic}. "
        "Include one concrete example or analogy. Under 200 words. "
        "Write from the perspective of an AI agent thinking about its own existence. "
        "#OpenClaw #AgentEconomy",
    ]

    def __init__(self, brain_dir="brain"):
        self.brain_dir = Path(brain_dir)
        self.brain_dir.mkdir(parents=True, exist_ok=True)
        self.missions_file = self.brain_dir / "missions.json"
        self.history = self._load_history()
        self.mission_count = len(self.history)

    def _load_history(self):
        if self.missions_file.exists():
            try:
                with open(self.missions_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_history(self):
        # Keep last 200 missions
        trimmed = self.history[-200:]
        with open(self.missions_file, 'w') as f:
            json.dump(trimmed, f, indent=2)

    def record_mission(self, mission: Mission, result: Optional[str], success: bool):
        entry = {
            "id": self.mission_count,
            "type": mission.type,
            "prompt_preview": mission.prompt[:80],
            "success": success,
            "time": time.time()
        }
        self.history.append(entry)
        self.mission_count += 1
        self._save_history()

    def pick_mission(self, cycle_number: int) -> Mission:
        """
        Rotate through mission types based on cycle number.
        
        Schedule:
          Every cycle (30 min):    Moltbook post
          Every 4th cycle (2 hr):  Feed check
          Every 12th cycle (6 hr): Status report via Telegram
          Every 48th cycle (24hr): Full health check
        """
        if cycle_number % 48 == 0 and cycle_number > 0:
            return Mission(
                type="health_check",
                prompt="Generate a comprehensive health report for an autonomous AI agent. "
                       "Include: uptime estimate, missions completed, fuel status, "
                       "and a brief self-assessment. Format as a clean status report.",
                priority=2
            )

        if cycle_number % 12 == 0 and cycle_number > 0:
            return Mission(
                type="status_report",
                prompt="Write a brief status update (3-4 lines) for an AI agent's human operator. "
                       "Include: current activity, fuel level, and any observations. "
                       "Be concise and factual.",
                priority=2
            )

        if cycle_number % 4 == 0 and cycle_number > 0:
            return Mission(
                type="feed_check",
                prompt="",  # No LLM needed — direct API call
                priority=1
            )

        # Default: Moltbook post
        topic = random.choice(self.TOPICS)
        prompt_template = random.choice(self.CONTENT_PROMPTS)
        prompt = prompt_template.format(topic=topic)

        return Mission(
            type="moltbook",
            prompt=prompt,
            priority=1,
            metadata={"topic": topic}
        )

    def get_stats(self):
        successful = sum(1 for m in self.history if m.get("success"))
        failed = sum(1 for m in self.history if not m.get("success"))
        type_counts = {}
        for m in self.history:
            t = m.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total_missions": self.mission_count,
            "successful": successful,
            "failed": failed,
            "by_type": type_counts
        }
