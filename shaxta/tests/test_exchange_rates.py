from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

from utils.exchange_rates import ExchangeRates


class TestExchangeRatesUnit(unittest.IsolatedAsyncioTestCase):
    async def test_build_trade_rates_uses_commission_formula(self) -> None:
        rates = ExchangeRates()
        rates.market_rates = {"BTC": 100.0}

        trade = rates.build_trade_rates(2.0)

        self.assertEqual(trade["BTC"]["buy"], 102.0)
        self.assertEqual(trade["BTC"]["sell"], 98.0)

    async def test_update_rates_uses_direct_and_cross_pairs(self) -> None:
        rates = ExchangeRates()
        prices = {
            "USDTRUB": 90.0,
            "BTCRUB": 0.0,
            "LTCRUB": 7000.0,
            "ETHRUB": 200000.0,
            "BTCUSDT": 100000.0,
            "LTCUSDT": 0.0,
            "ETHUSDT": 0.0,
            "XMRUSDT": 150.0,
        }

        async def fake_fetch(_session, symbol: str):
            return prices.get(symbol)

        with patch.object(rates, "_fetch_coingecko_prices", new=AsyncMock(return_value={})):
            with patch.object(rates, "_fetch_symbol_price", new=fake_fetch):
                updated = await rates.update_rates()

        self.assertEqual(updated["USDT"], 90.0)
        self.assertEqual(updated["BTC"], 9000000.0)
        self.assertEqual(updated["LTC"], 7000.0)
        self.assertEqual(updated["ETH"], 200000.0)
        self.assertEqual(updated["XMR"], 13500.0)
        self.assertIsInstance(rates.last_update, datetime)

    async def test_update_rates_can_infer_usdt_from_cross(self) -> None:
        rates = ExchangeRates()
        prices = {
            "USDTRUB": None,
            "BTCRUB": 8000000.0,
            "LTCRUB": None,
            "ETHRUB": None,
            "BTCUSDT": 100000.0,
            "LTCUSDT": 80.0,
            "ETHUSDT": None,
            "XMRUSDT": None,
        }

        async def fake_fetch(_session, symbol: str):
            return prices.get(symbol)

        with patch.object(rates, "_fetch_coingecko_prices", new=AsyncMock(return_value={})):
            with patch.object(rates, "_fetch_symbol_price", new=fake_fetch):
                updated = await rates.update_rates()

        self.assertEqual(updated["USDT"], 80.0)
        self.assertEqual(updated["LTC"], 6400.0)

    async def test_update_rates_prefers_direct_rub_pair_over_cross(self) -> None:
        rates = ExchangeRates()
        prices = {
            "USDTRUB": 90.0,
            "BTCRUB": 4000000.0,
            "LTCRUB": 6500.0,
            "ETHRUB": 150000.0,
            "BTCUSDT": 100000.0,
            "LTCUSDT": 50.0,
            "ETHUSDT": 2000.0,
            "XMRUSDT": None,
        }

        async def fake_fetch(_session, symbol: str):
            return prices.get(symbol)

        with patch.object(rates, "_fetch_coingecko_prices", new=AsyncMock(return_value={})):
            with patch.object(rates, "_fetch_symbol_price", new=fake_fetch):
                updated = await rates.update_rates()

        self.assertEqual(updated["USDT"], 90.0)
        self.assertEqual(updated["BTC"], 4000000.0)
        self.assertEqual(updated["LTC"], 6500.0)
        self.assertEqual(updated["ETH"], 150000.0)

    async def test_ensure_fresh_skips_update_for_recent_data(self) -> None:
        rates = ExchangeRates()
        rates.market_rates = {"BTC": 123.0}
        rates.last_update = datetime.now(timezone.utc)

        mocked_update = AsyncMock(return_value=rates.market_rates.copy())
        with patch.object(rates, "update_rates", new=mocked_update):
            result = await rates.ensure_fresh(max_age_seconds=120)

        self.assertEqual(result["BTC"], 123.0)
        mocked_update.assert_not_awaited()
