import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BTC_RUB = float(os.getenv("BTC_RUB_BUY", "9159862.91"))
DEFAULT_XMR_RUB = float(os.getenv("XMR_RUB_BUY", "26471.68"))
DEFAULT_LTC_RUB = float(os.getenv("LTC_RUB_BUY", "6675.19"))


async def get_usd_rub_rate() -> float:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    import json
                    data = json.loads(text)
                    usd_rate = data["Valute"]["USD"]["Value"]
                    return float(usd_rate)
    except Exception as e:
        print(f"CBR USD/RUB ошибка: {e}")
    return 90.0


async def get_crypto_price_usd(symbol: str) -> float:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data.get("price", 0))
    except Exception as e:
        print(f"Binance {symbol} ошибка: {e}")
    return 0.0


async def get_btc_rub_rate() -> float:
    btc_usd = await get_crypto_price_usd("BTCUSDT")
    if btc_usd > 0:
        usd_rub = await get_usd_rub_rate()
        return btc_usd * usd_rub
    return DEFAULT_BTC_RUB


async def get_ltc_rub_rate() -> float:
    ltc_usd = await get_crypto_price_usd("LTCUSDT")
    if ltc_usd > 0:
        usd_rub = await get_usd_rub_rate()
        return ltc_usd * usd_rub
    return DEFAULT_LTC_RUB


async def get_xmr_rub_rate() -> float:
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    xmr_usd = data.get("monero", {}).get("usd", 0)
                    if xmr_usd > 0:
                        usd_rub = await get_usd_rub_rate()
                        return xmr_usd * usd_rub
    except Exception as e:
        print(f"CoinGecko XMR ошибка: {e}")
    
    return DEFAULT_XMR_RUB


async def get_all_rates() -> dict:
    btc_rub = await get_btc_rub_rate()
    ltc_rub = await get_ltc_rub_rate()
    xmr_rub = await get_xmr_rub_rate()
    
    return {
        "BTC_RUB": btc_rub,
        "LTC_RUB": ltc_rub,
        "XMR_RUB": xmr_rub
    }

