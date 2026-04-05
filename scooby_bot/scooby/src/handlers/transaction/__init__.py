import os
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class Currency(Enum):
    btc = "btc"
    ltc = "ltc"
    xmr = "xmr"


# Exchange Rates - Buy (Покупка) (from .env)
BTC_RUB_BUY = float(os.getenv("BTC_RUB_BUY", "9159862.91"))
XMR_RUB_BUY = float(os.getenv("XMR_RUB_BUY", "26471.68"))
LTC_RUB_BUY = float(os.getenv("LTC_RUB_BUY", "6675.19"))
USDT_RUB_BUY = float(os.getenv("USDT_RUB_BUY", "80.44"))

# Exchange Rates - Sell (Продажа) (from .env)
BTC_RUB_SELL = float(os.getenv("BTC_RUB_SELL", "7125000.00"))
XMR_RUB_SELL = float(os.getenv("XMR_RUB_SELL", "35400.00"))
LTC_RUB_SELL = float(os.getenv("LTC_RUB_SELL", "6600.00"))
USDT_RUB_SELL = float(os.getenv("USDT_RUB_SELL", "73.15"))
# Backward compatibility (используются для покупки)
BTC_RUB = BTC_RUB_BUY
XMR_RUB = XMR_RUB_BUY
LTC_RUB = LTC_RUB_BUY
USDT_RUB = USDT_RUB_BUY
