import asyncio
import time
from typing import Any

import httpx

from .constants import FALLBACK_RATES


class RateService:
    def __init__(self, ttl_seconds: int = 45, retries: int = 3, retry_backoff_seconds: float = 1.0):
        self.ttl_seconds = ttl_seconds
        self.retries = max(1, retries)
        self.retry_backoff_seconds = max(0.1, retry_backoff_seconds)
        self._cached_rates: dict[str, float] = dict(FALLBACK_RATES)
        self._last_fetch_ts = 0.0

    async def _fetch_coingecko_once(self) -> dict[str, float] | None:
        timeout = httpx.Timeout(8.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "bitcoin,litecoin,monero,tether,tron,ethereum",
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
                "trx": float(payload["tron"]["rub"]),
                "eth": float(payload["ethereum"]["rub"]),
            }
        except Exception:
            return None

    async def fetch_rates(self) -> dict[str, float] | None:
        for attempt in range(self.retries):
            try:
                rates = await self._fetch_coingecko_once()
                if rates is not None:
                    return rates
            except httpx.HTTPError:
                pass
            if attempt + 1 < self.retries:
                await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))
        return None

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        now = time.time()
        if not force and (now - self._last_fetch_ts) < self.ttl_seconds:
            return dict(self._cached_rates)
        try:
            fetched = await self.fetch_rates()
            if fetched is not None:
                self._cached_rates = fetched
            self._last_fetch_ts = now
        except Exception:
            if not self._cached_rates:
                self._cached_rates = dict(FALLBACK_RATES)
            self._last_fetch_ts = now
        return dict(self._cached_rates)
