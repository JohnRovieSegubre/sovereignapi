import os
from pathlib import Path
from dotenv import load_dotenv
import sys

# Add sovereign-openclaw to path
sys.path.insert(0, str(Path("sovereign-openclaw").absolute()))

from sdk.sovereign import SovereignClient

# Load env
load_dotenv(dotenv_path="sovereign-openclaw/.env")

print(f"Environment SOVEREIGN_API_KEY: {os.getenv('SOVEREIGN_API_KEY')}")
print(f"Environment GATEWAY_URL: {os.getenv('GATEWAY_URL')}")

client = SovereignClient()
print(f"Client API Key: {client.api_key}")
print(f"Client Gateway: {client.base_url}")
