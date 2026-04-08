import re
from collections.abc import Iterable
from typing import NamedTuple


class ParsedAmount(NamedTuple):
    value: float
    currency: str | None


def parse_amount(raw: str) -> float:
    clean = re.sub(r'[^0-9,.]', '', raw)
    if ',' in clean and '.' in clean:
        if clean.rfind(',') > clean.rfind('.'):
            clean = clean.replace('.', '').replace(',', '.')
        else:
            clean = clean.replace(',', '')
    elif ',' in clean:
        clean = clean.replace(',', '.')
    return float(clean)


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


def fmt_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


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


def parse_non_negative_amount(raw: str) -> float | None:
    try:
        clean = raw.replace(",", ".").replace(" ", "")
        value = float(clean)
        return value if value >= 0 else None
    except (ValueError, AttributeError):
        return None


import re

def is_valid_crypto_address(address: str, coin: str = "btc") -> bool:
    """Basic crypto address validation."""
    if not address or len(address) < 10:
        return False
    patterns = {
        "btc": r"^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,62}$",
        "ltc": r"^(ltc1|[LM3])[a-zA-HJ-NP-Z0-9]{25,62}$",
        "xmr": r"^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}$",
        "eth": r"^0x[a-fA-F0-9]{40}$",
        "trx": r"^T[a-zA-HJ-NP-Z0-9]{33}$",
    }
    pattern = patterns.get(coin.lower(), r"^[a-zA-Z0-9]{10,100}$")
    return bool(re.match(pattern, address))
