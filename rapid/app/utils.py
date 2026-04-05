import re
from typing import Iterable


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


def parse_amount(raw: str, *, allow_zero: bool = False) -> float | None:
    cleaned = raw.strip().replace(" ", "").replace(",", ".").replace("−", "-")
    if not cleaned:
        return None
    if cleaned.count("-") > 1 or cleaned.count("+") > 1:
        return None
    if "-" in cleaned[1:] or "+" in cleaned[1:]:
        return None
    sign = 1.0
    if cleaned[0] in {"+", "-"}:
        if cleaned[0] == "-":
            sign = -1.0
        cleaned = cleaned[1:]
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned or cleaned == ".":
        return None
    if cleaned.count(".") > 1:
        return None
    try:
        value = sign * float(cleaned)
    except ValueError:
        return None
    if allow_zero:
        if value < 0:
            return None
    elif value <= 0:
        return None
    return value


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
