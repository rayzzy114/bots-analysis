
import httpx


async def RUB():
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get('https://www.cbr-xml-daily.ru/daily_json.js')
            if res.status_code == 200:
                data = res.json()
                return round(float(data['Valute']['USD']['Value']), 2)
    except Exception as e:
        print(f'Exception caught: {e}')
    return 100.0  # Fallback

async def get_price(symbol):
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(f'https://www.binance.com/fapi/v1/premiumIndex?symbol={symbol}')
            if res.status_code == 200:
                data = res.json()
                price = float(data.get('indexPrice', 0.0))
                return round(float(price), 2)
    except Exception as e:
        print(f'Exception caught: {e}')
    return 0.0
