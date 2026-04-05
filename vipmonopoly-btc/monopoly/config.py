import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PARSE_MODE = "HTML"

# Runtime values (can be updated from .env or admin panel)
def _get_env(key, default=""):
    val = os.getenv(key)
    return val if val is not None else default

requisites = _get_env("requisites")
bank = _get_env("bank")
operator = _get_env("operator")
rates = _get_env("rates")
sell_btc = _get_env("sell_btc")
news_channel = _get_env("news_channel")
work_operator = _get_env("work_operator")
operator2 = _get_env("operator2")
operator3 = _get_env("operator3")
BOT_USER_LTC = _get_env("BOT_USER_LTC")
BOT_USER_XMR = _get_env("BOT_USER_XMR")
XMR_RATE_USD = float(_get_env("XMR_RATE_USD", "70.09"))
XMR_RATE_RUB = float(_get_env("XMR_RATE_RUB", "6650.20"))
BTC_RATE_USD = float(_get_env("BTC_RATE_USD", "6921145.74"))
BTC_RATE_RUB = float(_get_env("BTC_RATE_RUB", "6921145.74"))

ADMIN_IDS = [int(id.strip()) for id in _get_env("ADMIN_IDS", "").split(",") if id.strip()]


def reload_env():
    """Reload all env vars into module namespace."""
    from importlib import reload
    import config
    reload(config)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
