import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from .constants import FALLBACK_RATES


FALLBACK_RATES_RUB: dict[str, float] = {
    "btc": 8_500_000.0,
    "eth": 300_000.0,
    "ltc": 9_500.0,
    "xmr": 15_000.0,
    "usdt": 87.0,
}


class RateService:
    def __init__(self, ttl_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self._cached_rates: dict[str, float] = dict(FALLBACK_RATES)
        self._cached_rates_rub: dict[str, float] = dict(FALLBACK_RATES_RUB)
        self._last_fetch_ts = 0.0

    async def _fetch_coingecko(self) -> tuple[dict[str, float], dict[str, float]] | None:
        timeout = httpx.Timeout(8.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "bitcoin,ethereum,litecoin,monero,tether",
                    "vs_currencies": "usd,rub",
                },
            )
            if response.status_code != 200:
                return None
            payload: Any = response.json()
            if not isinstance(payload, dict):
                return None
            try:
                usd = {
                    "btc": float(payload["bitcoin"]["usd"]),
                    "eth": float(payload["ethereum"]["usd"]),
                    "ltc": float(payload["litecoin"]["usd"]),
                    "xmr": float(payload["monero"]["usd"]),
                    "usdt": float(payload["tether"]["usd"]),
                }
                rub = {
                    "btc": float(payload["bitcoin"]["rub"]),
                    "eth": float(payload["ethereum"]["rub"]),
                    "ltc": float(payload["litecoin"]["rub"]),
                    "xmr": float(payload["monero"]["rub"]),
                    "usdt": float(payload["tether"]["rub"]),
                }
                return usd, rub
            except Exception:
                return None

    async def fetch_rates(self) -> dict[str, float]:
        result = await self._fetch_coingecko()
        if result is None:
            return dict(FALLBACK_RATES)
        return result[0]

    async def _refresh(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_fetch_ts) < self.ttl_seconds:
            return
        try:
            result = await self._fetch_coingecko()
            if result is not None:
                self._cached_rates, self._cached_rates_rub = result
                self._last_fetch_ts = now
            else:
                logger.warning("rates: CoinGecko returned no data, using cached/fallback rates")
                if not self._cached_rates:
                    self._cached_rates = dict(FALLBACK_RATES)
                if not self._cached_rates_rub:
                    self._cached_rates_rub = dict(FALLBACK_RATES_RUB)
                self._last_fetch_ts = now
        except Exception as exc:
            logger.warning("rates: fetch failed (%s), using cached/fallback rates", exc)
            if not self._cached_rates:
                self._cached_rates = dict(FALLBACK_RATES)
            if not self._cached_rates_rub:
                self._cached_rates_rub = dict(FALLBACK_RATES_RUB)
            self._last_fetch_ts = now

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        await self._refresh(force=force)
        return dict(self._cached_rates)

    async def get_rates_rub(self, force: bool = False) -> dict[str, float]:
        await self._refresh(force=force)
        return dict(self._cached_rates_rub)
