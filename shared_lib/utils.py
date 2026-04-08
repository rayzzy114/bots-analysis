import re
from typing import Iterable, NamedTuple


class ParsedAmount(NamedTuple):
    value: float
    currency: str | None


def parse_amount(raw: str) -> ParsedAmount | None:
    # Remove all whitespace
    text = raw.strip().lower().replace(" ", "")
    if not text:
        return None

    # Handle comma as decimal separator
    text = text.replace(",", ".")

    # Match number and optional currency suffix
    # Pattern: optional sign, digits, optional dot and digits, then optional characters (currency)
    match = re.match(r"^([+-]?\d*(?:\.\d+)?)(.*)$", text)
    if not match:
        return None

    num_str, suffix = match.groups()
    if not num_str or num_str == ".":
        # Check if suffix contains the number (e.g. "btc0.1")
        match = re.search(r"(\d+(?:\.\d+)?)", text)
        if match:
            num_str = match.group(1)
            # Remove the number from text to get suffix
            suffix = text.replace(num_str, "")
        else:
            return None

    try:
        value = float(num_str)
    except ValueError:
        return None

    if value <= 0:
        return None

    currency = suffix.strip().upper() if suffix else None
    # Normalize some common currency names
    if currency:
        if currency in ("Р", "РУБ", "RUBLE", "RUBLES", "РУБЛЕЙ", "РУБЛЯ"):
            currency = "RUB"
        elif currency in ("БТЦ", "BITCOIN"):
            currency = "BTC"
        elif currency in ("ЛТЦ", "LITECOIN"):
            currency = "LTC"
        elif currency in ("ЭФИР", "ETH"):
            currency = "ETH"
        elif currency in ("ЮСДТ", "TETHER"):
            currency = "USDT"
        elif currency in ("ТРОН", "TRX"):
            currency = "TRX"
        elif currency in ("МОНЕРО", "XMR"):
            currency = "XMR"

    return ParsedAmount(value=value, currency=currency)


def parse_admin_ids(raw: str) -> set[int]:


def fmt_money(value: float) -> str:
    return f"{round(value):,}".replace(",", " ")


def fmt_coin(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def safe_username(username: str | None) -> str:
    if username:
        return f"@{username}"
    return "@N/A"


def first_or_none(values: Iterable[str]) -> str | None:
    for item in values:
        return item
    return None
