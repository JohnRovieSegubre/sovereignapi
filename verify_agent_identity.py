
import os
from eth_account import Account
from dotenv import load_dotenv

# Load the agent's specific env file
env_path = os.path.join("sovereign-openclaw", ".env")
load_dotenv(env_path)

def verify_identity():
    private_key = os.getenv("AGENT_PRIVATE_KEY")
    if not private_key:
        print("❌ Error: AGENT_PRIVATE_KEY not found in sovereign-openclaw/.env")
        return

    try:
        # Derive address
        account = Account.from_key(private_key)
        print(f"🔐 Private Key Loaded from: {env_path}")
        print(f"🤖 Agent Public Address:   {account.address}")
        
        target = "0xbCFa5fe7d4c4908B23537C1b97113327bE6f4c93"
        if account.address.lower() == target.lower():
            print("\n✅ MATCH CONFIRMED: This IS the Sovereign OpenClaw Agent.")
        else:
            print(f"\n❌ MISMATCH: The key belongs to {account.address}, not {target}")

    except Exception as e:
        print(f"❌ Error deriving key: {e}")

if __name__ == "__main__":
    verify_identity()
