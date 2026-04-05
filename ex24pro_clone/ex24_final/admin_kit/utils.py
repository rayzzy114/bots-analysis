from html import escape, unescape
import re
from typing import Iterable

_SAFE_SUPPORT_FRAGMENT_RE = re.compile(
    r'(?is)^(?:[^<]*(?:<br\s*/?>|<a\s+href="[^"]+">[^<]*</a>))*[^<]*$'
)


def _contains_markup(raw: str) -> bool:
    lowered = raw.lower()
    return "<a " in lowered or "<br" in lowered or "&lt;a " in lowered or "&lt;br" in lowered


def _parse_float(raw: str) -> float | None:
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if cleaned.count(".") > 1:
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


def parse_amount(raw: str, *, allow_zero: bool = False) -> float | None:
    value = _parse_float(raw)
    if value is None:
        return None
    if allow_zero:
        return value if value >= 0 else None
    return value if value > 0 else None


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


def is_safe_html_fragment(raw: str) -> bool:
    value = raw.strip()
    return bool(value) and bool(_SAFE_SUPPORT_FRAGMENT_RE.fullmatch(value))


def sanitize_html_fragment(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    unescaped = unescape(value)
    if _contains_markup(value) and is_safe_html_fragment(unescaped):
        return unescaped
    if is_safe_html_fragment(value):
        return value
    return escape(value)


def preferred_html_text(text: str | None, html_text: str | None) -> str:
    text_value = (text or "").strip()
    if _contains_markup(text_value) and is_safe_html_fragment(text_value):
        return text_value

    html_value = (html_text or "").strip()
    if _contains_markup(html_value) and is_safe_html_fragment(unescape(html_value)):
        return unescape(html_value)
    if is_safe_html_fragment(html_value) and not text_value:
        return html_value

    return html_value or text_value
