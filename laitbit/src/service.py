import asyncio
import json
import logging
import secrets
import string
from pathlib import Path

import httpx

USERS_FILE = "users.json"

API_URL = "https://api.coingecko.com/api/v3/simple/price"
_RATES_HTTP_TIMEOUT = httpx.Timeout(6.0, connect=2.0)
_RATES_FETCH_RETRIES = 3
_RATES_RETRY_DELAY_SEC = 0.8
logger = logging.getLogger(__name__)


def load_users():
    file_path = Path(USERS_FILE)
    if not file_path.exists() or file_path.stat().st_size == 0:
        return []
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def save_user(chat_id: int):
    users = load_users()
    if chat_id not in users:
        users.append(chat_id)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)


def generate_request_id(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits  # a-zA-Z0-9
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def fetch_crypto():
    params = {
        "ids": "bitcoin,litecoin,monero,tether",
        "vs_currencies": "rub",
    }
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=_RATES_HTTP_TIMEOUT) as client:
        for attempt in range(1, _RATES_FETCH_RETRIES + 1):
            try:
                resp = await client.get(API_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
                return {
                    "BTC": float(payload["bitcoin"]["rub"]),
                    "LTC": float(payload["litecoin"]["rub"]),
                    "XMR": float(payload["monero"]["rub"]),
                    "USDT": float(payload["tether"]["rub"]),
                }
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt >= _RATES_FETCH_RETRIES:
                    break
                await asyncio.sleep(_RATES_RETRY_DELAY_SEC * attempt)

    logger.warning(
        "Cannot fetch crypto rates from CoinGecko after %s attempts: %s",
        _RATES_FETCH_RETRIES,
        last_error,
    )
    return {}
