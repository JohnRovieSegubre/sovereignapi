
from web3 import Web3
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path("sovereign-openclaw/.env").resolve()
load_dotenv(dotenv_path=env_path)

RPC = "https://sepolia.base.org"
KEY = os.getenv("AGENT_PRIVATE_KEY")

def clear_nonce():
    w3 = Web3(Web3.HTTPProvider(RPC))
    acc = w3.eth.account.from_key(KEY)
    address = acc.address
    
    print(f"🔧 Fixing Nonce for {address}")
    
    # Get accurate counts
    latest = w3.eth.get_transaction_count(address, 'latest')
    pending = w3.eth.get_transaction_count(address, 'pending')
    
    print(f"   Latest (Confirmed): {latest}")
    print(f"   Pending (Mempool): {pending}")
    
    if pending > latest:
        print("💡 Stuck transactions detected!")
        nonce_to_fix = latest
        
        # Send 0 ETH to self to clear
        tx = {
            'to': address,
            'value': 0,
            'gas': 21000,
            'gasPrice': int(w3.eth.gas_price * 1.2),
            'nonce': nonce_to_fix,
            'chainId': 84532
        }
        signed = w3.eth.account.sign_transaction(tx, KEY)
        try:
            h = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"🚀 Sent Cancellation Tx: {h.hex()}")
        except Exception as e:
            print(f"❌ Cancel Failed: {e}")
            
    else:
        print("✅ No stuck transactions found. (Nonce is aligned)")

if __name__ == "__main__":
    clear_nonce()
