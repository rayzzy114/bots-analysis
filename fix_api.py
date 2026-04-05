import os
import re

files_to_fix = [
    './VortexExchange/utils/valute.py'
]

def fix_valute(filepath):
    if not os.path.exists(filepath):
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # The issue here is that response may not contain expected keys or be successful
    # It already checks status_code == 200, but lacks checking missing keys like `['price']` or `['data']` etc.
    # I will replace dict access with .get() and default values.
    
    # 1. Binance BTCUSDT
    content = content.replace("float(data['price'])", "float(data.get('price', 0))")
    
    # 2. Coinbase BTC
    content = content.replace("float(data['data']['rates']['BTC'])", "float(data.get('data', {}).get('rates', {}).get('BTC', 0))")
    
    # 3. CoinGecko BTC
    content = content.replace("data['bitcoin']['usd']", "data.get('bitcoin', {}).get('usd', 0)")
    
    # 4. CoinGecko XMR
    content = content.replace("data['monero']['usd']", "data.get('monero', {}).get('usd', 0)")
    
    # 5. CBR USD
    content = content.replace("data['Valute']['USD']['Value']", "data.get('Valute', {}).get('USD', {}).get('Value', 0)")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

fix_valute('./VortexExchange/utils/valute.py')

