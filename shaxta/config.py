import os
from dotenv import load_dotenv

load_dotenv()

PARSE_MODE = "HTML"


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip().replace(",", "."))
    except ValueError:
        return default


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME")
OPERATOR = os.getenv("OPERATOR")
OTZIVY = os.getenv("OTZIVY")
NEWS = os.getenv("NEWS")
SUPPORT = os.getenv("SUPPORT")
REVIEWS = os.getenv("REVIEWS")

payment_details = os.getenv("payment_details")
PAYMENT_BANK = os.getenv("PAYMENT_BANK")
DEFAULT_COMMISSION = _get_float_env("DEFAULT_COMMISSION", 20.0)
RATE_UPDATE_INTERVAL = _get_int_env("RATE_UPDATE_INTERVAL", 300)

# Fallback rates (used when APIs are unavailable)
DEFAULT_BTC_RATE = _get_float_env("DEFAULT_BTC_RATE", 7500000.0)
DEFAULT_LTC_RATE = _get_float_env("DEFAULT_LTC_RATE", 7500.0)
DEFAULT_ETH_RATE = _get_float_env("DEFAULT_ETH_RATE", 200000.0)
DEFAULT_USDT_RATE = _get_float_env("DEFAULT_USDT_RATE", 85.0)
DEFAULT_XMR_RATE = _get_float_env("DEFAULT_XMR_RATE", 12000.0)

# Operational limits
MIN_BUY_AMOUNT = _get_int_env("MIN_BUY_AMOUNT", 1500)
MIN_SELL_AMOUNT = _get_int_env("MIN_SELL_AMOUNT", 1000)
MIN_WITHDRAW_AMOUNT = _get_int_env("MIN_WITHDRAW_AMOUNT", 1000)
REFERRAL_REWARD_PERCENT = _get_float_env("REFERRAL_REWARD_PERCENT", 1.5)

# Exchange wallet limits (per currency)
EXCHANGE_LIMIT_BTC = os.getenv("EXCHANGE_LIMIT_BTC", "0.05")
EXCHANGE_LIMIT_LTC = os.getenv("EXCHANGE_LIMIT_LTC", "50.0")
EXCHANGE_LIMIT_USDT = os.getenv("EXCHANGE_LIMIT_USDT", "5000.0")

ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
