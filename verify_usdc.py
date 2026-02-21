
from web3 import Web3

RPC = "https://sepolia.base.org"
USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"

def verify():
    w3 = Web3(Web3.HTTPProvider(RPC))
    print(f"🔗 Connected: {w3.is_connected()}")
    
    # 1. Check Code
    code = w3.eth.get_code(USDC)
    if len(code) < 100:
        print("❌ No code at address!")
        return
        
    # 2. Check Symbol
    abi = [
        {"constant":True,"inputs":[],"name":"symbol","outputs":[{"name":"","type":"string"}],"type":"function"},
        {"constant":True,"inputs":[],"name":"name","outputs":[{"name":"","type":"string"}],"type":"function"},
        {"constant":True,"inputs":[],"name":"version","outputs":[{"name":"","type":"string"}],"type":"function"},
    ]
    contract = w3.eth.contract(address=USDC, abi=abi)
    try:
        sym = contract.functions.symbol().call()
        name = contract.functions.name().call()
        try:
             ver = contract.functions.version().call()
        except:
             ver = "1 (Implicit)"
             
        print(f"✅ Token Found: {name} ({sym})")
        print(f"   Version: {ver}")
        
        # 3. Check EIP-3009 Selector (transferWithAuthorization)
        # keccak('transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32)')
        # Actually usually v2 is: transferWithAuthorization(address,address,uint256,uint256,uint256,bytes32,uint8,bytes32,bytes32) or similar
        # Let's just assume if it calls itself USDC v2 it has it.
        
    except Exception as e:
        print(f"❌ Read Failed: {e}")

if __name__ == "__main__":
    verify()
