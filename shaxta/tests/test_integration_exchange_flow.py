import os
import tempfile
import unittest

from db.init_db import init_db
from db.settings import get_commission, update_commission
from utils.exchange_rates import exchange_rates


class TestExchangeFlowIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._original_cwd = os.getcwd()
        self._temp_dir = tempfile.TemporaryDirectory()
        os.chdir(self._temp_dir.name)

    async def asyncTearDown(self) -> None:
        os.chdir(self._original_cwd)
        self._temp_dir.cleanup()

    async def test_commission_from_db_changes_trade_rate_calculation(self) -> None:
        await init_db()
        await update_commission(4.0)
        commission = await get_commission()

        original_rates = exchange_rates.market_rates.copy()
        try:
            exchange_rates.market_rates = {"BTC": 100.0}
            trade_rates = exchange_rates.build_trade_rates(commission)
        finally:
            exchange_rates.market_rates = original_rates

        self.assertEqual(commission, 4.0)
        self.assertEqual(trade_rates["BTC"]["buy"], 104.0)
        self.assertEqual(trade_rates["BTC"]["sell"], 96.0)
