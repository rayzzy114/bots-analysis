import time
from typing import Any

import aiohttp

class RateService:
    BASE_URL = "https://api.coingecko.com/api/v3/simple/price"

    def __init__(
        self,
        coins: dict[str, dict[str, Any]],
        fallback_rates: dict[str, float],
        ttl_seconds: int = 60,
        vs_currency: str = "rub",
        session: aiohttp.ClientSession | None = None,
    ):
        self.coins = coins
        self.ttl_seconds = ttl_seconds
        self.vs_currency = vs_currency
        self.session = session
        self._last_ts = 0.0
        self._rates = {k: float(fallback_rates.get(k, 0.0)) for k in coins}

    def _url(self) -> str:
        ids = ",".join(sorted({meta["id"] for meta in self.coins.values()}))
        return f"{self.BASE_URL}?ids={ids}&vs_currencies={self.vs_currency}"

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        now = time.time()
        if not force and now - self._last_ts < self.ttl_seconds:
            return self._rates
        
        if self.session:
            await self._do_fetch(self.session, now)
        else:
            timeout = aiohttp.ClientTimeout(total=10)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    await self._do_fetch(session, now)
            except Exception as e:
                print(f'Exception caught: {e}')
        return self._rates

    async def _do_fetch(self, session: aiohttp.ClientSession, now: float) -> None:
        try:
            async with session.get(self._url(), timeout=10) as response:
                response.raise_for_status()
                payload = await response.json()
                updated: dict[str, float] = {}
                for key, meta in self.coins.items():
                    coin_id = meta["id"]
                    value = payload.get(coin_id, {}).get(self.vs_currency)
                    if value is None:
                        continue
                    updated[key] = float(str(value).replace(",", ".").replace(" ", ""))
                if updated:
                    self._rates.update(updated)
                    self._last_ts = now
        except Exception as e:
            print(f'Exception caught: {e}')
