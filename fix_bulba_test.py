import os

path = "BULBA/BULBA/tests/test_rates.py"
if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # fix the test that looks for 'get_crypto_rates' instead of 'get_btc_rates'
    content = content.replace("get_crypto_rates", "get_btc_rates")
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

