"""RateService — курсы крипто→RUB с CoinGecko, кэш 30–60с.

Никаких захардкоженных курсов. coin_min = min_rub / rate считается в момент
выбора монеты (clone_spec.md §4).
"""

from __future__ import annotations

import asyncio
import math
import time

from . import constants as const

try:
    import aiohttp
except ImportError:  # тесты могут не требовать сети
    aiohttp = None  # type: ignore

_API = "https://api.coingecko.com/api/v3/simple/price"
_CACHE_TTL = 45.0  # секунд


class RateService:
    def __init__(self, ttl: float = _CACHE_TTL) -> None:
        self._ttl = ttl
        self._cache: dict[str, tuple[float, float]] = {}  # coin -> (rate_rub, ts)
        self._lock = asyncio.Lock()

    async def get(self, coin: str) -> float:
        """RUB-курс одной монеты. Кэшируется на _ttl секунд."""
        now = time.monotonic()
        cached = self._cache.get(coin)
        if cached and (now - cached[1]) < self._ttl:
            return cached[0]
        async with self._lock:
            cached = self._cache.get(coin)
            if cached and (time.monotonic() - cached[1]) < self._ttl:
                return cached[0]
            rate = await self._fetch(coin)
            self._cache[coin] = (rate, time.monotonic())
            return rate

    async def _fetch(self, coin: str) -> float:
        if aiohttp is None:
            raise RuntimeError("aiohttp is required for live rates")
        cg_id = const.COINS[coin]["coingecko_id"]
        params = {"ids": cg_id, "vs_currencies": "rub"}
        async with aiohttp.ClientSession() as session:
            async with session.get(_API, params=params, timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
        return float(data[cg_id]["rub"])


def calc_example(min_rub: float, rate: float) -> str:
    """Пример суммы в монете, гарантированно проходящий минимум (skill)."""
    if rate <= 0:
        return "0"
    min_coin = min_rub / rate
    if min_coin >= 1:
        return str(math.ceil(min_coin))
    exp = math.floor(math.log10(min_coin))
    factor = 10 ** exp
    rounded = math.ceil(min_coin / factor)
    result = rounded * factor
    decimals = max(0, -exp)
    s = f"{result:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".") or "0"
    return s
