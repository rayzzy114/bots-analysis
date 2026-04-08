import re
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


def fmt_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")
