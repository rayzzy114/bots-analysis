import asyncio
import logging
import time
from typing import Any

import httpx

from .constants import FALLBACK_RATES

logger = logging.getLogger(__name__)


class RateService:
    def __init__(self, ttl_seconds: int = 3600, retries: int = 3, retry_backoff_seconds: float = 2.0, client: httpx.AsyncClient | None = None):
        self.ttl_seconds = ttl_seconds
        self.retries = max(1, retries)
        self.retry_backoff_seconds = max(0.1, retry_backoff_seconds)
        self._client = client
        self._cached_rates: dict[str, float] = dict(FALLBACK_RATES)
        self._last_fetch_ts = 0.0
        self._update_task: asyncio.Task | None = None

    def start(self):
        if self._update_task is None:
            self._update_task = asyncio.create_task(self._background_update_loop())
            logger.info("RateService background update loop started")

    async def _background_update_loop(self):
        while True:
            try:
                await self.get_rates(force=True)
                logger.info("Rates updated successfully")
            except Exception as e:
                logger.error(f"Failed to update rates in background: {e}")
            await asyncio.sleep(self.ttl_seconds)

    async def _fetch_coingecko_once(self) -> dict[str, float] | None:
        timeout = httpx.Timeout(10.0, connect=5.0)
        if self._client:
            return await self._do_fetch(self._client)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._do_fetch(client)

    async def _do_fetch(self, client: httpx.AsyncClient) -> dict[str, float] | None:
        try:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "bitcoin,litecoin,monero,tether,tron,ethereum",
                    "vs_currencies": "rub",
                },
                timeout=httpx.Timeout(10.0, connect=5.0)
            )
            if response.status_code != 200:
                logger.warning(f"Coingecko API returned status {response.status_code}")
                return None
            payload: Any = response.json()
            if not isinstance(payload, dict):
                return None
            return {
                "btc": float(payload["bitcoin"]["rub"]),
                "ltc": float(payload["litecoin"]["rub"]),
                "xmr": float(payload["monero"]["rub"]),
                "usdt": float(payload["tether"]["rub"]),
                "trx": float(payload["tron"]["rub"]),
                "eth": float(payload["ethereum"]["rub"]),
            }
        except Exception as e:
            logger.error(f"Error fetching from Coingecko: {e}")
            return None

    async def fetch_rates(self) -> dict[str, float] | None:
        for attempt in range(self.retries):
            try:
                rates = await self._fetch_coingecko_once()
                if rates is not None:
                    return rates
            except (httpx.HTTPError, KeyError, TypeError) as e:
                logger.debug(f"Fetch attempt {attempt + 1} failed: {e}")
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
            elif not self._cached_rates:
                self._cached_rates = dict(FALLBACK_RATES)
                self._last_fetch_ts = now
        except Exception as e:
            logger.error(f"Critical error in get_rates: {e}")
            if not self._cached_rates:
                self._cached_rates = dict(FALLBACK_RATES)
            self._last_fetch_ts = now
        return dict(self._cached_rates)
