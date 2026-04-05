from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from admin_kit.storage import SettingsStore

logger = logging.getLogger(__name__)

FALLBACK_RATES: dict[str, float] = {
    "usdt_rub": 86.5,
    "usdt_thb": 33.2,
    "usdt_cny": 7.1,
    "usdt_aed": 3.67,
    "usdt_idr": 16300.0,
    "usdt_try": 38.5,
    "rub_thb": 2.60,
    "rub_cny": 12.18,
    "rub_aed": 23.57,
    "rub_idr": 188.0,
    "rub_try": 0.45,
}


def _load_overrides() -> dict[str, float]:
    overrides: dict[str, float] = {}
    for key, val in os.environ.items():
        if key.startswith("RATE_OVERRIDE_"):
            rate_key = key[len("RATE_OVERRIDE_"):].lower()
            try:
                overrides[rate_key] = float(val)
            except ValueError:
                pass
    return overrides


def _compute_cross_rates(
    raw: dict[str, float],
    spread_pct: float,
) -> dict[str, float]:
    factor = 1.0 + spread_pct / 100.0
    usdt_rub_base = raw.get("rub", 86.5)
    usdt_thb_base = raw.get("thb", 33.2)
    usdt_cny_base = raw.get("cny", 7.1)
    usdt_aed_base = raw.get("aed", 3.67)
    usdt_idr_base = raw.get("idr", 16300.0)
    usdt_try_base = raw.get("try", 38.5)

    usdt_rub = usdt_rub_base * factor
    usdt_thb = usdt_thb_base * factor
    usdt_cny = usdt_cny_base * factor
    usdt_aed = usdt_aed_base * factor
    usdt_idr = usdt_idr_base * factor
    usdt_try = usdt_try_base * factor

    rates: dict[str, float] = {
        "usdt_rub": round(usdt_rub, 2),
        "usdt_thb": round(usdt_thb, 2),
        "usdt_cny": round(usdt_cny, 2),
        "usdt_aed": round(usdt_aed, 2),
        "usdt_idr": round(usdt_idr, 0),
        "usdt_try": round(usdt_try, 2),
    }
    if usdt_thb_base:
        rates["rub_thb"] = round((usdt_rub_base / usdt_thb_base) * factor, 2)
    if usdt_cny_base:
        rates["rub_cny"] = round((usdt_rub_base / usdt_cny_base) * factor, 2)
    if usdt_aed_base:
        rates["rub_aed"] = round((usdt_rub_base / usdt_aed_base) * factor, 2)
    if usdt_idr_base:
        rates["rub_idr"] = round((usdt_rub_base / usdt_idr_base) * factor, 4)
    if usdt_try_base:
        rates["rub_try"] = round((usdt_rub_base / usdt_try_base) * factor, 2)
    return rates


class ExchangeRateService:
    def __init__(self, ttl_seconds: int = 30, spread_percent: float = 5.0):
        self.ttl_seconds = ttl_seconds
        self.spread_percent = spread_percent
        self._cached_raw: dict[str, float] = dict(FALLBACK_RATES)
        self._cached_rates: dict[str, float] = _compute_cross_rates(self._cached_raw, self.spread_percent)
        self._last_fetch_ts = 0.0
        self.settings: SettingsStore | None = None

    def set_settings(self, settings: SettingsStore) -> None:
        self.settings = settings

    @property
    def current_spread(self) -> float:
        if self.settings is not None:
            return self.settings.commission_percent
        return self.spread_percent

    async def _fetch_coingecko(self) -> dict[str, float] | None:
        timeout = httpx.Timeout(8.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "tether",
                    "vs_currencies": "rub,thb,cny,aed,idr,try",
                },
            )
            if response.status_code != 200:
                return None
            payload: Any = response.json()
            if not isinstance(payload, dict):
                return None
            tether = payload.get("tether")
            if not isinstance(tether, dict):
                return None
            try:
                return {
                    "rub": float(tether["rub"]),
                    "thb": float(tether["thb"]),
                    "cny": float(tether["cny"]),
                    "aed": float(tether["aed"]),
                    "idr": float(tether["idr"]),
                    "try": float(tether["try"]),
                }
            except (KeyError, ValueError, TypeError):
                return None

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        now = time.time()
        # If commission changed, we might want to force recompute even if cache is fresh
        # But for now, we'll just wait for TTL or manual refresh in admin panel
        if not force and (now - self._last_fetch_ts) < self.ttl_seconds:
            self._cached_rates = _compute_cross_rates(self._cached_raw, self.current_spread)
            return dict(self._cached_rates)
        try:
            raw = await self._fetch_coingecko()
            if raw is not None:
                self._cached_raw = raw
                rates = _compute_cross_rates(raw, self.current_spread)
                overrides = _load_overrides()
                rates.update(overrides)
                self._cached_rates = rates
                self._last_fetch_ts = now
        except Exception:
            logger.exception("Failed to fetch rates from CoinGecko")
            if not self._cached_rates:
                self._cached_raw = dict(FALLBACK_RATES)
                self._cached_rates = _compute_cross_rates(self._cached_raw, self.current_spread)
        return dict(self._cached_rates)
