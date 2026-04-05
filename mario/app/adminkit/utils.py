import re
from typing import Iterable

AMOUNT_RE = re.compile(r"[+-]?\d[\d\s.,]*")


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
    text = (raw or "").strip()
    if not text:
        return None

    normalized = (
        text.replace("\u00A0", " ")
        .replace("\u2212", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )
    if "-" in normalized:
        return None
    match = AMOUNT_RE.search(normalized)
    if not match:
        return None

    cleaned = match.group(0).replace(" ", "")
    if cleaned.startswith("-"):
        return None
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    if cleaned.count(".") > 1 or not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value < 0:
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
