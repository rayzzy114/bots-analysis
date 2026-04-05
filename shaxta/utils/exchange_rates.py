import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional

import aiohttp

from config import DEFAULT_BTC_RATE, DEFAULT_LTC_RATE, DEFAULT_ETH_RATE, DEFAULT_USDT_RATE, DEFAULT_XMR_RATE


class ExchangeRates:
    def __init__(self):
        self.market_rates: Dict[str, float] = {
            "BTC": DEFAULT_BTC_RATE,
            "LTC": DEFAULT_LTC_RATE,
            "USDT": DEFAULT_USDT_RATE,
            "ETH": DEFAULT_ETH_RATE,
            "XMR": DEFAULT_XMR_RATE,
        }
        self.last_update: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def _fetch_symbol_price(self, session: aiohttp.ClientSession, symbol: str) -> Optional[float]:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                data = await response.json()
                price = float(data["price"])
                return price if price > 0 else None
        except Exception as error:
            print(f"Binance fetch error for {symbol}: {error}")
            return None

    async def _fetch_coingecko_prices(self, session: aiohttp.ClientSession) -> Dict[str, float]:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=bitcoin,litecoin,ethereum,tether,monero&vs_currencies=rub"
        )
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return {}
                data = await response.json()
        except Exception as error:
            print(f"CoinGecko fetch error: {error}")
            return {}

        mapping = {
            "bitcoin": "BTC",
            "litecoin": "LTC",
            "ethereum": "ETH",
            "tether": "USDT",
            "monero": "XMR",
        }
        resolved: Dict[str, float] = {}
        for source_id, code in mapping.items():
            value = data.get(source_id, {}).get("rub")
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if price > 0:
                resolved[code] = price
        return resolved

    async def update_rates(self) -> Dict[str, float]:
        async with self._lock:
            timeout = aiohttp.ClientTimeout(total=10)

            async with aiohttp.ClientSession(timeout=timeout) as session:
                coingecko_rates = await self._fetch_coingecko_prices(session)

            if coingecko_rates:
                updated_any = False
                for currency, value in coingecko_rates.items():
                    rounded = round(value, 2)
                    if rounded > 0:
                        self.market_rates[currency] = rounded
                        updated_any = True

                if updated_any:
                    self.last_update = datetime.now(timezone.utc)
                return self.market_rates.copy()

            symbols = (
                "USDTRUB",
                "BTCRUB",
                "LTCRUB",
                "ETHRUB",
                "BTCUSDT",
                "LTCUSDT",
                "ETHUSDT",
                "XMRUSDT",
            )
            async with aiohttp.ClientSession(timeout=timeout) as session:
                tasks = {
                    symbol: asyncio.create_task(self._fetch_symbol_price(session, symbol))
                    for symbol in symbols
                }
                prices = {symbol: await task for symbol, task in tasks.items()}

            usdt_rub = prices.get("USDTRUB")
            if not usdt_rub:
                for base_currency in ("BTC", "ETH", "LTC"):
                    direct_rub = prices.get(f"{base_currency}RUB")
                    cross_usdt = prices.get(f"{base_currency}USDT")
                    if direct_rub and cross_usdt and cross_usdt > 0:
                        usdt_rub = direct_rub / cross_usdt
                        break
            resolved: Dict[str, float] = {}

            if usdt_rub:
                resolved["USDT"] = usdt_rub

            for currency in ("BTC", "LTC", "ETH"):
                direct_rub = prices.get(f"{currency}RUB")
                cross_usdt = prices.get(f"{currency}USDT")
                if direct_rub:
                    resolved[currency] = direct_rub
                elif cross_usdt and usdt_rub:
                    resolved[currency] = cross_usdt * usdt_rub

            xmr_usdt = prices.get("XMRUSDT")
            if xmr_usdt and usdt_rub:
                resolved["XMR"] = xmr_usdt * usdt_rub

            updated_any = False
            for currency, value in resolved.items():
                rounded = round(value, 2)
                if rounded > 0:
                    self.market_rates[currency] = rounded
                    updated_any = True

            if updated_any:
                self.last_update = datetime.now(timezone.utc)
            return self.market_rates.copy()

    async def ensure_fresh(self, max_age_seconds: int = 120) -> Dict[str, float]:
        if not self.last_update:
            return await self.update_rates()

        age_seconds = (datetime.now(timezone.utc) - self.last_update).total_seconds()
        if age_seconds >= max_age_seconds:
            return await self.update_rates()
        return self.market_rates.copy()

    def build_trade_rates(self, commission_percent: float) -> Dict[str, Dict[str, float]]:
        try:
            commission = max(0.0, float(commission_percent))
        except (TypeError, ValueError):
            commission = 0.0

        markup = commission / 100
        sell_multiplier = max(0.0, 1 - markup)

        rates: Dict[str, Dict[str, float]] = {}
        for currency, market_price in self.market_rates.items():
            rates[currency] = {
                "buy": round(market_price * (1 + markup), 2),
                "sell": round(market_price * sell_multiplier, 2),
            }
        return rates

    async def get_trade_rates(
        self,
        commission_percent: float,
        *,
        force_update: bool = False,
        max_age_seconds: int = 120,
    ) -> Dict[str, Dict[str, float]]:
        if force_update:
            await self.update_rates()
        else:
            await self.ensure_fresh(max_age_seconds=max_age_seconds)
        return self.build_trade_rates(commission_percent)

    def get_last_update_label(self) -> str:
        if not self.last_update:
            return "no data"
        return self.last_update.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")


exchange_rates = ExchangeRates()
