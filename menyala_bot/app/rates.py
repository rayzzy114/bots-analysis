import time
from typing import Any

import httpx

from .constants import FALLBACK_RATES


class RateService:
    def __init__(self, ttl_seconds: int = 45):
        self.ttl_seconds = ttl_seconds
        self._cached_rates: dict[str, float] = dict(FALLBACK_RATES)
        self._last_fetch_ts = 0.0

    async def _fetch_coingecko(self) -> dict[str, float] | None:
        timeout = httpx.Timeout(8.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "bitcoin,litecoin,monero,tether",
                    "vs_currencies": "rub",
                },
            )
            if response.status_code != 200:
                return None
            payload: Any = response.json()
            if not isinstance(payload, dict):
                return None
            try:
                return {
                    "btc": float(payload["bitcoin"]["rub"]),
                    "ltc": float(payload["litecoin"]["rub"]),
                    "xmr": float(payload["monero"]["rub"]),
                    "usdt": float(payload["tether"]["rub"]),
                }
            except Exception:
                return None

    async def fetch_rates(self) -> dict[str, float]:
        rates = await self._fetch_coingecko()
        if rates is None:
            return dict(FALLBACK_RATES)
        return rates

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        now = time.time()
        if not force and (now - self._last_fetch_ts) < self.ttl_seconds:
            return dict(self._cached_rates)
        try:
            fetched = await self.fetch_rates()
            self._cached_rates = fetched
            self._last_fetch_ts = now
        except Exception:
            if not self._cached_rates:
                self._cached_rates = dict(FALLBACK_RATES)
        return dict(self._cached_rates)
