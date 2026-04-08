import re

def parse_currency(value):
    # Typical pattern found in bots
    value = str(value).strip().lower().replace(',', '.')
    # Naive extraction often used
    match = re.search(r'([\d\.]+)', value)
    if match:
        return float(match.group(1))
    return None

test_cases = ['1000rub', '0.001 btc', '1000', ' 1000 ', '1.000,50']
for t in test_cases:
    print(f"'{t}' -> {parse_currency(t)}")
