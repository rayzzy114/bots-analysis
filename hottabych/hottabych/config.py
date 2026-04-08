import os

from dotenv import load_dotenv

load_dotenv()


def _get_env(key: str, default: str, cast=float) -> float:
    return cast(os.getenv(key, default))


# Fallback rates from env (used when API is unavailable)
BTC_RATE_USD = _get_env("BTC_RATE_USD", "45000.0")
BTC_RATE_RUB = _get_env("BTC_RATE_RUB", "4200000.0")
LTC_RATE_USD = _get_env("LTC_RATE_USD", "450.0")
LTC_RATE_RUB = _get_env("LTC_RATE_RUB", "42000.0")
