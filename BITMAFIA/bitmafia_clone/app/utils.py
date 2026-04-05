import re
from typing import Iterable


def _parse_float(raw: str) -> float | None:
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    if not re.fullmatch(r"[0-9]+\.?[0-9]*", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


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
    value = _parse_float(raw)
    if value is None:
        return None
    if value <= 0:
        return None
    return value


def parse_non_negative_amount(raw: str) -> float | None:
    value = _parse_float(raw)
    if value is None:
        return None
    if value < 0:
        return None
    return value


def fmt_money(value: float) -> str:
    return f"{round(value):,}".replace(",", " ")


def fmt_coin(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def safe_username(username: str | None) -> str:
    if username:
        return f"@{username}"
    return "@N/A"


def first_or_none(values: Iterable[str]) -> str | None:
    for item in values:
        return item
    return None
