import requests


async def RUB():
    data = requests.get('https://www.cbr-xml-daily.ru/daily_json.js').json()
    return round(float(data['Valute']['USD']['Value']), 2)

async def get_price(symbol):
    res = requests.get(f'https://www.binance.com/fapi/v1/premiumIndex?symbol={symbol}')
    if res.status_code == 200:
        price = float(res.json()['indexPrice'])
        return round(float(price), 2)