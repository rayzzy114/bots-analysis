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
