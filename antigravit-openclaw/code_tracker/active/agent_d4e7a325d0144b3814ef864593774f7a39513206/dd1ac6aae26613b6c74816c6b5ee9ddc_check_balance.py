›import sys
from pymacaroons import Macaroon

def check_balance(token_str):
    try:
        m = Macaroon.deserialize(token_str)
        print(f"\n--- üè¶ Sovereign Token Inspector ---")
        print(f"Location:   {m.location}")
        print(f"Identifier: {m.identifier}")
        
        balance = "Unknown"
        for caveat in m.caveats:
            if caveat.caveat_id.startswith("balance = "):
                balance = caveat.caveat_id.split(" = ")[1]
        
        print(f"Balance:    {balance} sats")
        print(f"Status:     Valid Serialized Format")
        print("-" * 35)
    except Exception as e:
        print(f"Error decoding token: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_balance.py <TOKEN_STRING>")
    else:
        check_balance(sys.argv[1])
›*cascade08"(d4e7a325d0144b3814ef864593774f7a395132062?file:///c:/Users/rovie%20segubre/agent/scripts/check_balance.py:&file:///c:/Users/rovie%20segubre/agent