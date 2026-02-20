
from web3 import Web3

RPC_URL = "https://sepolia.base.org"
TX_HASH = "0xef2fe74a11da9d9f764415c8a68fcee84119a3566d5319a7bd11cb1014af5653"

def check_tx():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    print(f"🔗 Connected to {RPC_URL}: {w3.is_connected()}")
    
    try:
        receipt = w3.eth.get_transaction_receipt(TX_HASH)
        print(f"\n✅ Transaction Confirmed in Block: {receipt.blockNumber}")
        print(f"   Status: {'SUCCESS' if receipt.status == 1 else 'FAIL'}")
        
        # Check logs to see if Transfer event happened
        print(f"   Logs: {len(receipt.logs)}")
        for log in receipt.logs:
            print(f"   - {log.address} ({log.topics[0].hex()})")
            
    except Exception as e:
        print(f"\n⚠️ Transaction Receipt Error: {e}")
        # Try getting tx itself
        try:
            tx = w3.eth.get_transaction(TX_HASH)
            print("   Transaction exists in mempool/chain but no receipt yet.")
            print(f"   Nonce: {tx.nonce}")
        except Exception as e2:
            print(f"   Transaction NOT FOUND: {e2}")

if __name__ == "__main__":
    check_tx()
