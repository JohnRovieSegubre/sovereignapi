"""
Example Action Skill: Crypto Price Checker
Drop this in 'skills/' to give the agent price checking powers.
"""

import requests
from skill_loader import tool

@tool
def get_crypto_price(coin_id="bitcoin", currency="usd"):
    """
    Get the current price of a cryptocurrency from CoinGecko.
    
    Args:
        coin_id: The ID of the coin (e.g. 'bitcoin', 'ethereum', 'solana')
        currency: The target currency (default 'usd')
    """
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies={currency}"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if coin_id in data:
            price = data[coin_id][currency]
            return f"The price of {coin_id} is {price} {currency.upper()}"
        else:
            return f"Could not find price for {coin_id}"
    except Exception as e:
        return f"Error checking price: {e}"
