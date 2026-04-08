from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .constants import FALLBACK_RATES

logger = logging.getLogger(__name__)


class RateService:
    def __init__(self, ttl_seconds: int = 30, client: httpx.AsyncClient | None = None):
        self.ttl_seconds = ttl_seconds
        self._client = client
        self._cached_rates: dict[str, float] = dict(FALLBACK_RATES)
        self._last_fetch_ts = 0.0

    async def _fetch_coingecko(self) -> dict[str, float] | None:
        timeout = httpx.Timeout(8.0, connect=4.0)
        if self._client:
            return await self._do_fetch(self._client)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._do_fetch(client)

    async def _do_fetch(self, client: httpx.AsyncClient) -> dict[str, float] | None:
        try:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "bitcoin,litecoin,monero,tether",
                    "vs_currencies": "rub",
                },
                timeout=httpx.Timeout(8.0, connect=4.0)
            )
            if response.status_code != 200:
                return None
            payload: Any = response.json()
            if not isinstance(payload, dict):
                return None
            return {
                "btc": float(payload["bitcoin"]["rub"]),
                "ltc": float(payload["litecoin"]["rub"]),
                "xmr": float(payload["monero"]["rub"]),
                "usdt": float(payload["tether"]["rub"]),
            }
        except Exception as e:
            logger.warning("rates: _do_fetch failed: %s", e)
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
            fetched = await self._fetch_coingecko()
            if fetched is not None:
                self._cached_rates = fetched
                self._last_fetch_ts = now
            else:
                logger.warning("rates: CoinGecko returned no data, using cached/fallback rates")
                if not self._cached_rates:
                    self._cached_rates = dict(FALLBACK_RATES)
                self._last_fetch_ts = now
        except Exception as exc:
            logger.warning("rates: fetch failed (%s), using cached/fallback rates", exc)
            if not self._cached_rates:
                self._cached_rates = dict(FALLBACK_RATES)
        return dict(self._cached_rates)


COIN_ID_BY_SYMBOL: dict[str, str] = {
    "BTC": "bitcoin",
    "LTC": "litecoin",
    "USDT": "tether",
    "ETH": "ethereum",
    "TRX": "tron",
    "TON": "the-open-network",
    "XMR": "monero",
}


@dataclass
class CoinGeckoRateService:
    transport: httpx.AsyncBaseTransport | None = None
    timeout_sec: float = 10.0

    async def fetch_rub_rates(self, symbols: list[str]) -> dict[str, float]:
        normalized: list[str] = []
        ids: list[str] = []

        for raw_symbol in symbols:
            symbol = (raw_symbol or "").strip().upper()
            if not symbol:
                continue
            coin_id = COIN_ID_BY_SYMBOL.get(symbol)
            if coin_id is None:
                raise ValueError(f"Unknown symbol: {symbol}")
            normalized.append(symbol)
            ids.append(coin_id)

        if not normalized:
            return {}

        async with httpx.AsyncClient(
            base_url="https://api.coingecko.com/api/v3",
            timeout=self.timeout_sec,
            transport=self.transport,
        ) as client:
            response = await client.get(
                "/simple/price",
                params={
                    "ids": ",".join(ids),
                    "vs_currencies": "rub",
                },
            )
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected CoinGecko response payload")

        out: dict[str, float] = {}
        for symbol in normalized:
            coin_id = COIN_ID_BY_SYMBOL[symbol]
            row = payload.get(coin_id)
            if not isinstance(row, dict) or "rub" not in row:
                raise RuntimeError(f"Missing RUB rate for {symbol} in CoinGecko payload")
            out[symbol] = float(row["rub"])

        return out
