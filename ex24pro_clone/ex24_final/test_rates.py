from __future__ import annotations

import asyncio

from rates import ExchangeRateService


def test_rate_service_applies_spread_to_live_rates() -> None:
    service = ExchangeRateService(ttl_seconds=999, spread_percent=10.0)

    async def fake_fetch() -> dict[str, float]:
        return {
            "rub": 100.0,
            "thb": 20.0,
            "cny": 10.0,
            "aed": 5.0,
            "idr": 20000.0,
        }

    service._fetch_coingecko = fake_fetch  # type: ignore[method-assign]
    rates = asyncio.run(service.get_rates(force=True))

    assert rates["usdt_rub"] == 110.0
    assert rates["usdt_thb"] == 22.0
    assert rates["rub_thb"] == 5.5
    assert rates["rub_idr"] == 0.0055


def test_rate_service_recomputes_spread_after_settings_change() -> None:
    service = ExchangeRateService(ttl_seconds=999, spread_percent=10.0)

    async def fake_fetch() -> dict[str, float]:
        return {
            "rub": 100.0,
            "thb": 20.0,
            "cny": 10.0,
            "aed": 5.0,
            "idr": 20000.0,
        }

    service._fetch_coingecko = fake_fetch  # type: ignore[method-assign]
    first = asyncio.run(service.get_rates(force=True))
    service.spread_percent = 20.0
    second = asyncio.run(service.get_rates())

    assert first["usdt_rub"] == 110.0
    assert second["usdt_rub"] == 120.0
