
import os
import json
from web3 import Web3

# Config
POLYGON_RPC = "https://polygon-mainnet.g.alchemy.com/v2/S__e1JUkM03zL4EonOpfV"
USDC_CONTRACT_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USER_WALLET_ADDRESS = "0xbCFa5fe7d4c4908B23537C1b97113327bE6f4c93" 

# ABI
ERC20_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"payable":false,"stateMutability":"view","type":"function"}]')

def check_balance():
    print(f"🔌 Connecting to {POLYGON_RPC}...")
    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    if not w3.is_connected():
        print("❌ Failed to connect.")
        return

    contract = w3.eth.contract(address=USDC_CONTRACT_ADDRESS, abi=ERC20_ABI)
    
    print(f"🔍 Checking USDC balance for {USER_WALLET_ADDRESS}...")
    try:
        balance_units = contract.functions.balanceOf(USER_WALLET_ADDRESS).call()
        balance_usdc = balance_units / 1_000_000 # 6 decimals
        
        print(f"💰 Balance: {balance_usdc} USDC")
        
        if balance_usdc < 1.0:
            print("❌ INSUFFICIENT USDC! (Need >= 1.0 USDC)")
        else:
            print("✅ Sufficient USDC available.")

    except Exception as e:
        print(f"❌ Error checking USDC: {e}")

    print(f"🔍 Checking POL (Gas) balance for {USER_WALLET_ADDRESS}...")
    try:
        balance_wei = w3.eth.get_balance(USER_WALLET_ADDRESS)
        balance_pol = w3.from_wei(balance_wei, 'ether')
        print(f"⛽ Balance: {balance_pol} POL")
    except Exception as e:
        print(f"❌ Error checking POL: {e}")

if __name__ == "__main__":
    check_balance()
