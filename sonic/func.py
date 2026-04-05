import aiohttp
import asyncio


async def RUB():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://www.cbr-xml-daily.ru/daily_json.js') as res:
                if res.status == 200:
                    data = await res.json(content_type=None)
                    return round(float(data['Valute']['USD']['Value']), 2)
    except Exception as e:
        print(f'Exception caught: {e}')
    return 100.0  # Fallback

async def get_price(symbol):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://www.binance.com/fapi/v1/premiumIndex?symbol={symbol}') as res:
                if res.status == 200:
                    data = await res.json(content_type=None)
                    price = float(data.get('indexPrice', 0.0))
                    return round(float(price), 2)
    except Exception as e:
        print(f'Exception caught: {e}')
    return 0.0
