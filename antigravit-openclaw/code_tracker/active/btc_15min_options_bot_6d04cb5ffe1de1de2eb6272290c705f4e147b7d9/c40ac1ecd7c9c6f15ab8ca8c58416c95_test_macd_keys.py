‘import pandas as pd
import pandas_ta as ta

# Create dummy data
df = pd.DataFrame({'close': [100.0 + i for i in range(50)]})

# Calculate MACD
macd = ta.macd(df['close'], fast=12, slow=26, signal=9)

# Print columns
print("MACD Columns:", macd.columns.tolist())
‘"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Hfile:///c:/Users/rovie%20segubre/btc_15min_options_bot/test_macd_keys.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot