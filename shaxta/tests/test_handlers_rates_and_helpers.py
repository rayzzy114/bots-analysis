import unittest
from typing import Any, cast
from unittest.mock import patch

import handlers.buy as buy
import handlers.calculator as calculator
import handlers.rates as rates
import handlers.sell as sell


class TestHandlersRatesAndHelpersUnit(unittest.IsolatedAsyncioTestCase):
    async def test_get_buy_rate_uses_trade_rates(self) -> None:
        async def fake_get_commission() -> float:
            return 2.0

        async def fake_get_trade_rates(commission, **_kwargs):
            self.assertEqual(commission, 2.0)
            return {"BTC": {"buy": 101.0, "sell": 99.0}}

        with (
            patch.object(buy, "get_commission", new=fake_get_commission),
            patch.object(buy.exchange_rates, "get_trade_rates", new=fake_get_trade_rates),
        ):
            rate, commission = await buy.get_buy_rate("BTC")

        self.assertEqual(rate, 101.0)
        self.assertEqual(commission, 2.0)

    async def test_get_sell_rate_uses_trade_rates(self) -> None:
        async def fake_get_commission() -> float:
            return 1.5

        async def fake_get_trade_rates(commission, **_kwargs):
            self.assertEqual(commission, 1.5)
            return {"USDT": {"buy": 100.0, "sell": 98.5}}

        with (
            patch.object(sell, "get_commission", new=fake_get_commission),
            patch.object(sell.exchange_rates, "get_trade_rates", new=fake_get_trade_rates),
        ):
            rate, commission = await sell.get_sell_rate("USDT")

        self.assertEqual(rate, 98.5)
        self.assertEqual(commission, 1.5)

    async def test_get_calculator_rate_respects_direction(self) -> None:
        async def fake_get_commission() -> float:
            return 2.25

        async def fake_get_trade_rates(commission, **_kwargs):
            self.assertEqual(commission, 2.25)
            return {"ETH": {"buy": 220000.0, "sell": 210000.0}}

        with (
            patch.object(calculator, "get_commission", new=fake_get_commission),
            patch.object(calculator.exchange_rates, "get_trade_rates", new=fake_get_trade_rates),
        ):
            buy_rate, _ = await calculator.get_calculator_rate("ETH", "buy")
            sell_rate, _ = await calculator.get_calculator_rate("ETH", "sell")

        self.assertEqual(buy_rate, 220000.0)
        self.assertEqual(sell_rate, 210000.0)

    async def test_rates_render_contains_commission_and_update_time(self) -> None:
        async def fake_get_commission() -> float:
            return 3.0

        async def fake_get_trade_rates(_commission, **_kwargs):
            return {
                "BTC": {"buy": 10.0, "sell": 9.0},
                "LTC": {"buy": 8.0, "sell": 7.0},
                "ETH": {"buy": 6.0, "sell": 5.0},
                "USDT": {"buy": 4.0, "sell": 3.0},
            }

        with (
            patch.object(rates, "get_commission", new=fake_get_commission),
            patch.object(rates.exchange_rates, "get_trade_rates", new=fake_get_trade_rates),
            patch.object(rates.exchange_rates, "get_last_update_label", return_value="01.01.2026 00:00:00 UTC"),
        ):
            text = await rates._render_rates(cast(Any, None), force_refresh=False)

        self.assertIn("<b>3.00%</b>", text)
        self.assertIn("01.01.2026 00:00:00 UTC", text)
