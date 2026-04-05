import unittest


from unittest.mock import MagicMock, AsyncMock, patch



import sys

import os

sys.path.append(os.getcwd())


from bot.handlers.mixer import get_commission_percent, get_crypto_rate_usdt

from bot.handlers.exchange import get_crypto_rate_rub

from bot.handlers.admin import is_admin

from core.models import User, Rate


class TestMixerLogic(unittest.TestCase):

    def test_commission_tiers(self):


        self.assertEqual(get_commission_percent(100), 10)

        self.assertEqual(get_commission_percent(200), 10)

        self.assertEqual(get_commission_percent(300), 10)



        self.assertEqual(get_commission_percent(301), 8)

        self.assertEqual(get_commission_percent(500), 8)



        self.assertEqual(get_commission_percent(501), 5)

        self.assertEqual(get_commission_percent(1000), 5)

        self.assertEqual(get_commission_percent(1001), 5)



        self.assertEqual(get_commission_percent(50), 10)                          

        self.assertEqual(get_commission_percent(999999), 2)                                                                     







class TestAsyncLogic(unittest.IsolatedAsyncioTestCase):

    async def test_get_crypto_rate_usdt(self):


        session = AsyncMock()



        rate = await get_crypto_rate_usdt(session, "USDT")

        self.assertEqual(rate, 1.0)




        mock_result_btc = MagicMock()

        mock_rate_btc = Rate(currency="BTC", buy_rate=10000.0)      

        mock_result_btc.scalar_one_or_none.return_value = mock_rate_btc


        mock_result_usdt = MagicMock()

        mock_rate_usdt = Rate(currency="USDT", buy_rate=100.0)      

        mock_result_usdt.scalar_one_or_none.return_value = mock_rate_usdt






        session.execute.side_effect = [mock_result_btc, mock_result_usdt]


        rate = await get_crypto_rate_usdt(session, "BTC")


        self.assertEqual(rate, 100.0)



        session.execute.side_effect = [mock_result_btc, MagicMock(scalar_one_or_none=MagicMock(return_value=None))]

        mock_result_btc.scalar_one_or_none.return_value = mock_rate_btc        


        rate = await get_crypto_rate_usdt(session, "BTC")

        self.assertIsNone(rate)


    async def test_get_crypto_rate_rub(self):

        session = AsyncMock()

        mock_result = MagicMock()

        mock_rate = Rate(currency="ETH", buy_rate=200000.0, sell_rate=190000.0)

        mock_result.scalar_one_or_none.return_value = mock_rate

        session.execute.return_value = mock_result



        rate = await get_crypto_rate_rub(session, "ETH", "buy")

        self.assertEqual(rate, 200000.0)








        rate = await get_crypto_rate_rub(session, "ETH", "sell")

        self.assertEqual(rate, 190000.0)



        mock_result.scalar_one_or_none.return_value = None

        rate = await get_crypto_rate_rub(session, "ETH", "buy")

        self.assertIsNone(rate)


    async def test_is_admin(self):

        session = AsyncMock()




        with patch('bot.handlers.admin.Config') as MockConfig:

            MockConfig.ADMIN_ID = "12345"

            self.assertTrue(await is_admin(session, 12345))



            mock_result = MagicMock()

            mock_user = User(telegram_id=67890, is_admin=True)

            mock_result.scalar_one_or_none.return_value = mock_user

            session.execute.return_value = mock_result


            self.assertTrue(await is_admin(session, 67890))



            mock_user.is_admin = False

            self.assertFalse(await is_admin(session, 67890))



            mock_result.scalar_one_or_none.return_value = None

            self.assertFalse(await is_admin(session, 11111))


if __name__ == '__main__':

    unittest.main()

