™import pandas as pd
import pandas_ta as ta

# Create SHORT dummy data (20 rows)
df = pd.DataFrame({'close': [100.0 + i for i in range(20)]})

# Calculate MACD
macd = ta.macd(df['close'], fast=12, slow=26, signal=9)

print("Rows:", len(df))
print("MACD Result:\n", macd)
™"(6d04cb5ffe1de1de2eb6272290c705f4e147b7d92Ifile:///c:/Users/rovie%20segubre/btc_15min_options_bot/test_macd_short.py:6file:///c:/Users/rovie%20segubre/btc_15min_options_bot