from typing import Any

import httpx


class RateService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client

    async def _fetch_coingecko(self) -> dict[str, float]:
        timeout = httpx.Timeout(6.0, connect=2.0)
        if self._client:
            return await self._do_fetch(self._client)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await self._do_fetch(client)

    async def _do_fetch(self, client: httpx.AsyncClient) -> dict[str, float]:
        response = await client.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,litecoin,monero,tether",
                "vs_currencies": "rub",
            },
            timeout=httpx.Timeout(6.0, connect=2.0)
        )
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid CoinGecko payload")
        try:
            return {
                "btc": float(payload["bitcoin"]["rub"]),
                "ltc": float(payload["litecoin"]["rub"]),
                "xmr": float(payload["monero"]["rub"]),
                "usdt": float(payload["tether"]["rub"]),
            }
        except Exception as exc:
            raise ValueError("Invalid CoinGecko rates format") from exc

    async def fetch_rates(self) -> dict[str, float]:
        return await self._fetch_coingecko()

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        _ = force
        return await self.fetch_rates()
