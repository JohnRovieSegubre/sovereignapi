
import os
import json
import sys
from web3 import Web3

# Config from Watcher
POLYGON_RPC = os.getenv("POLYGON_RPC", "https://polygon-mainnet.g.alchemy.com/v2/S__e1JUkM03zL4EonOpfV")
USDC_CONTRACT_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
MY_WALLET_ADDRESS = "0xC8Dc2795352cdedEF3a11f1fC9E360D85C5aAC4d"

# TX to check (from user log)
TX_HASH = "fbedeb207f40a733b125f9a09218d8dbfc1bc159f07c2b3d99bc8a3943b057c0"

def check_tx():
    print(f"🔌 Connecting to {POLYGON_RPC}...")
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    
    if not w3.is_connected():
        print("❌ Failed to connect.")
        return

    print(f"🔍 Checking TX: {TX_HASH}")
    try:
        # 1. Get Receipt
        receipt = w3.eth.get_transaction_receipt(TX_HASH)
        print(f"✅ Receipt Found! Status: {receipt['status']}")
        print(f"   Block Number: {receipt['blockNumber']}")
        print(f"   From: {receipt['from']}")
        print(f"   To: {receipt['to']}")
        
        # 2. Check Logs in Receipt
        print(f"\n📜 Examining {len(receipt['logs'])} Logs in Receipt:")
        found_transfer = False
        
        for i, log in enumerate(receipt['logs']):
            # Check if it's USDC
            if log.address.lower() == USDC_CONTRACT_ADDRESS.lower():
                print(f"   [Log {i}] USDC Event Detected")
                # Try to decode topics
                # Topic 0: Signature (Transfer)
                # Topic 1: From
                # Topic 2: To
                if len(log['topics']) >= 3:
                    topic_to = "0x" + log['topics'][2].hex()[-40:]
                    print(f"       Topic To: {topic_to}")
                    
                    if topic_to.lower() == MY_WALLET_ADDRESS.lower():
                        print("       🎯 MATCHES MY_WALLET_ADDRESS!")
                        found_transfer = True
                    else:
                        print(f"       ⚠️ DOES NOT MATCH {MY_WALLET_ADDRESS}")
                else:
                    print("       ⚠️ Not a standard Transfer event (topics < 3)")
            else:
                print(f"   [Log {i}] Contract: {log.address} (Not USDC)")

        if found_transfer:
            print("\n✅ CONCLUSION: Valid Transfer DID occur. Watcher SHOULD have seen it.")
        else:
            print("\n❌ CONCLUSION: No matching Transfer found in receipt.")

    except Exception as e:
        print(f"❌ Error getting receipt: {e}")
        # Try getting tx just in case
        try:
            tx = w3.eth.get_transaction(TX_HASH)
            print("   (Transaction exists in mempool/chain but receipt failed?)")
        except:
            print("   (Transaction not found at all)")

if __name__ == "__main__":
    check_tx()
