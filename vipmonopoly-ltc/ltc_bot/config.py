import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PARSE_MODE = "HTML"

def _get_env(key, default=""):
    val = os.getenv(key)
    return val if val is not None else default

requisites = _get_env("requisites")
bank = _get_env("bank")
rates = _get_env("rates")
sell_btc = _get_env("sell_btc")
news_channel = _get_env("news_channel")

def get_operator():
    return _get_env("operator")

def get_work_operator():
    return _get_env("work_operator")

def get_operator2():
    return _get_env("operator2")

def get_operator3():
    return _get_env("operator3")

ADMIN_IDS = [int(id.strip()) for id in _get_env("ADMIN_IDS", "").split(",") if id.strip()]

LTC_RATE_USD = float(_get_env("LTC_RATE_USD", "70.09"))
LTC_RATE_RUB = float(_get_env("LTC_RATE_RUB", "6650.20"))
BTC_RATE_USD = float(_get_env("BTC_RATE_USD", "45000.0"))
BTC_RATE_RUB = float(_get_env("BTC_RATE_RUB", "4500000.0"))


def reload_env():
    from importlib import reload

    import config
    reload(config)


def is_admin(user_id: int) -> bool:
    from runtime_state import get_runtime_state
    return user_id in get_runtime_state().admin_ids
