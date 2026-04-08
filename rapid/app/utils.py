import re
from collections.abc import Iterable
from typing import NamedTuple


class ParsedAmount(NamedTuple):
    value: float
    currency: str | None


class CurrencyParser:
    def __init__(self, supported_currencies: Iterable[str] | None = None):
        self.supported = supported_currencies or ["RUB", "BTC", "LTC", "ETH", "USDT", "TRX", "XMR"]

    def parse(self, raw: str) -> ParsedAmount | None:
        text = raw.strip().lower().replace(" ", "")
        if not text:
            return None
        text = text.replace(",", ".")
        match = re.match(r"^([+-]?\d*(?:\.\d+)?)(.*)$", text)
        if not match:
            return None

        num_str, suffix = match.groups()
        if not num_str or num_str == ".":
            match = re.search(r"(\d+(?:\.\d+)?)", text)
            if match:
                num_str = match.group(1)
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


def fmt_money(value: float) -> str:
    return f"{round(value):,}".replace(",", " ")


def fmt_coin(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def safe_username(username: str | None) -> str:
    if username:
        return f"@{username}"
    return "@N/A"


def parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            result.add(int(chunk))
        except ValueError:
            continue
    return result


def parse_amount(raw: str) -> float | None:
    try:
        clean = raw.replace(",", ".").replace(" ", "")
        return float(clean)
    except (ValueError, AttributeError):
        return None
