�+"""
Autonomous Core - The Sovereign Soul
=====================================
A 24/7 intelligence unit that manages its own identity and fuel.

This script:
1. Holds a persistent API Key (sk-sov-xxx) - Your license
2. Manages Macaroon "Fuel" - Liquid credits
3. Auto-refuels when balance is low
4. Runs forever, replacing OpenAI entirely

Usage:
    # Real Mode (requires funded wallet)
    set SOVEREIGN_API_KEY=sk-sov-xxx
    set AGENT_PRIVATE_KEY=0x...
    python autonomous_core.py
    
    # Mock Mode (for development)
    set SOVEREIGN_API_KEY=sk-sov-xxx
    set MOCK_MODE=1
    python autonomous_core.py
"""

import os
import sys
import time

# Add parent directory for SDK import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sdk.sovereign import SovereignClient


class AutonomousCore:
    """
    The 'Ghost in the Machine' - A self-sustaining intelligence unit.
    """
    
    def __init__(self):
        print("=" * 60)
        print("  AUTONOMOUS CORE - Sovereign Soul (Phase 7)")
        print("=" * 60)
        
        # Initialize Client (reads from env vars)
        self.client = SovereignClient()
        
        # Validate Configuration
        if not self.client.api_key:
            print("\n❌ ERROR: SOVEREIGN_API_KEY not set!")
            print("   Get your key: python api_key_registry.py create 'MyAgent'")
            sys.exit(1)
        
        # Mission Counter
        self.missions_completed = 0
        self.errors = 0
        
        print()
        print(f"🔑 API Key: {self.client.api_key[:12]}...")
        print(f"💰 Fuel: {'Loaded' if self.client.token else 'Empty (will refuel on first request)'}")
        print(f"🎭 Mock Mode: {'ON' if self.client.mock_mode else 'OFF'}")
        print()
    
    def think(self, prompt, model="sovereign/deepseek-r1"):
        """
        Execute a thinking mission.
        Returns the AI response or None on failure.
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            
            if "error" in response:
                self.errors += 1
                return None
            
            # Extract content
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            self.missions_completed += 1
            return content
            
        except ValueError as e:
            # 401 - API Key rejected
            print(f"🛑 FATAL: {e}")
            sys.exit(1)
        except Exception as e:
            self.errors += 1
            print(f"🔥 Error: {e}")
            return None
    
    def run_forever(self, mission_function, interval_seconds=60):
        """
        Run a mission loop forever.
        
        Args:
            mission_function: A callable that returns a prompt string
            interval_seconds: Delay between missions
        """
        print(f"🚀 Starting infinite loop (every {interval_seconds}s)")
        print("-" * 60)
        
        while True:
            try:
                # Get mission prompt
                prompt = mission_function()
                
                if prompt:
                    print(f"\n📡 Mission #{self.missions_completed + 1}: {prompt[:50]}...")
                    
                    result = self.think(prompt)
                    
                    if result:
                        print(f"✅ Response: {result[:100]}...")
                    else:
                        print("❌ Mission failed")
                
                # Status Report
                print(f"\n📊 Status: {self.missions_completed} completed, {self.errors} errors")
                
                # Wait for next cycle
                print(f"⏳ Waiting {interval_seconds}s...")
                time.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Shutdown requested. Final stats:")
                print(f"   Missions: {self.missions_completed}")
                print(f"   Errors: {self.errors}")
                break
    
    def get_fuel_level(self):
        """
        Estimate remaining fuel (requires parsing macaroon).
        For now, returns a simple status.
        """
        if not self.client.token:
            return "EMPTY"
        return "LOADED"


# --- DEMO MISSION ---
def demo_mission():
    """A simple demo mission that asks the time."""
    import random
    prompts = [
        "What is 2 + 2?",
        "Say 'Hello Sovereign World' in 3 words or less.",
        "Complete this sentence: The future of AI is...",
        "Give me a random number between 1 and 100.",
    ]
    return random.choice(prompts)


def main():
    core = AutonomousCore()
    
    # Check for interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        # Run demo loop
        core.run_forever(demo_mission, interval_seconds=30)
    else:
        # Single mission (for testing)
        print("\n🧪 Running single mission test...")
        result = core.think("What is the capital of France?")
        
        if result:
            print(f"\n✅ SUCCESS: {result}")
        else:
            print("\n❌ FAILED: No result")
        
        print("\nTo run forever: python autonomous_core.py --demo")


if __name__ == "__main__":
    main()
� *cascade08��*cascade08��+ *cascade08"(d4e7a325d0144b3814ef864593774f7a3951320629file:///c:/Users/rovie%20segubre/agent/autonomous_core.py:&file:///c:/Users/rovie%20segubre/agent