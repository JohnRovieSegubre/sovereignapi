"""
Wallet Helper for Onboarding
----------------------------
Generates new Polygon wallets or validates existing private keys.
Generates QR codes for funding.
"""

import sys
import argparse
from eth_account import Account
def create_new():
    acct = Account.create()
    print(f"\nNEW WALLET CREATED")
    print(f"Address:     {acct.address}")
    print(f"Private Key: {acct.key.hex()}")
    print("-" * 60)
    print("Action Required: Send at least $1 USDC (Polygon) to this address.")
    print("-" * 60)
    
    # Return formatted for PowerShell capture
    return f"ADDRESS={acct.address}\nPRIVATE_KEY={acct.key.hex()}"

def validate_existing(private_key):
    try:
        if not private_key.startswith("0x"):
            private_key = "0x" + private_key
        acct = Account.from_key(private_key)
        print(f"\n[OK] VALID PRIVATE KEY")
        print(f"Address: {acct.address}")
        return f"ADDRESS={acct.address}\nPRIVATE_KEY={acct.key.hex()}"
    except Exception as e:
        print(f"[ERROR] Invalid Private Key: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--validate", type=str)
    args = parser.parse_args()

    if args.create:
        print(create_new())
    elif args.validate:
        print(validate_existing(args.validate))
