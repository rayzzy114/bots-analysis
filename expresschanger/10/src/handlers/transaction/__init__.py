import os

from dotenv import load_dotenv

load_dotenv()

BTC_RUB_BUY = float(os.getenv("BTC_RUB_BUY", "9159862.91"))
XMR_RUB_BUY = float(os.getenv("XMR_RUB_BUY", "26471.68"))
LTC_RUB_BUY = float(os.getenv("LTC_RUB_BUY", "6675.19"))

