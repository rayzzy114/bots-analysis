from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

COMMISSION_SERVICE_RE = re.compile(
    r"(?P<prefix>Комиссия сервиса:\s*)"
    r"(?P<open><strong>|\*\*)?"
    r"(?P<value>\d+(?:[\.,]\d+)?%)"
    r"(?P<close></strong>|\*\*)?",
)
COMMISSION_PLAIN_RE = re.compile(
    r"(?P<prefix>только\s+)"
    r"(?P<open><strong>|\*\*)?"
    r"(?P<value>\d+(?:[\.,]\d+)?%)"
    r"(?P<close></strong>|\*\*)?"
    r"(?P<suffix>\s+и\s+ничего\s+более)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuntimeOverrides:
    operator_url: str = ""
    link_overrides: dict[str, str] = field(default_factory=dict)
    sell_wallet_overrides: dict[str, str] = field(default_factory=dict)
    commission_percent: float = 0.0


def normalize_operator_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("@"):  # @username
        return f"https://t.me/{raw[1:]}"
    if raw.startswith("t.me/"):
        return f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return raw.rstrip("/")
    return raw.rstrip("/")


def extract_operator_handle(url: str) -> str:
    parsed = urlparse((url or "").strip())
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host not in {"t.me", "telegram.me"}:
        return ""
    path = (parsed.path or "").strip("/")
    if not path:
        return ""
    return path.split("/")[0]


def apply_state_overrides(
    *,
    state: dict[str, Any],
    overrides: RuntimeOverrides,
    operator_url_aliases: tuple[str, ...],
    operator_handle_aliases: tuple[str, ...],
    link_url_aliases: dict[str, tuple[str, ...]] | None = None,
    sell_wallet_aliases: dict[str, tuple[str, ...]] | None = None,
    live_rates_usd: dict[str, float] | None = None,
) -> dict[str, Any]:
    updated = copy.deepcopy(state)

    target_operator_url = normalize_operator_url(overrides.operator_url)
    target_operator_handle = extract_operator_handle(target_operator_url).lower()

    for text_field in ("text", "text_html", "text_markdown"):
        raw_value = updated.get(text_field)
        if not isinstance(raw_value, str) or not raw_value:
            continue
        value = raw_value

        if target_operator_url:
            value = _replace_operator_urls(value, operator_url_aliases, target_operator_url)
            if target_operator_handle:
                value = _replace_operator_handles(value, operator_handle_aliases, target_operator_handle)

        if overrides.link_overrides and link_url_aliases:
            value = _replace_link_urls(
                value,
                link_overrides=overrides.link_overrides,
                link_url_aliases=link_url_aliases,
                skip_keys={"operator"},
            )

        if overrides.sell_wallet_overrides and sell_wallet_aliases:
            value = _replace_sell_wallets(
                value,
                sell_wallet_overrides=overrides.sell_wallet_overrides,
                sell_wallet_aliases=sell_wallet_aliases,
            )

        if overrides.commission_percent > 0:
            value = _replace_commission(value, overrides.commission_percent)

        updated[text_field] = value

    text_links = updated.get("text_links")
    if isinstance(text_links, list):
        patched_links: list[Any] = []
        for link in text_links:
            if not isinstance(link, str):
                patched_links.append(link)
                continue

            patched = link
            if target_operator_url and _is_same_url(link, operator_url_aliases):
                patched = target_operator_url
            elif overrides.link_overrides and link_url_aliases:
                patched = _replace_single_link_url(
                    link,
                    link_overrides=overrides.link_overrides,
                    link_url_aliases=link_url_aliases,
                    skip_keys={"operator"},
                )
            patched_links.append(patched)
        updated["text_links"] = patched_links

    _patch_buttons(
        updated,
        target_operator_url=target_operator_url,
        target_operator_handle=target_operator_handle,
        operator_url_aliases=operator_url_aliases,
        operator_handle_aliases=operator_handle_aliases,
        link_overrides=overrides.link_overrides,
        link_url_aliases=link_url_aliases or {},
        sell_wallet_overrides=overrides.sell_wallet_overrides,
        sell_wallet_aliases=sell_wallet_aliases or {},
    )

    return updated


def _replace_operator_urls(text: str, aliases: tuple[str, ...], target_url: str) -> str:
    value = text
    for alias in aliases:
        if not alias:
            continue
        value = value.replace(alias, target_url)
        alt = alias.replace("https://", "http://")
        value = value.replace(alt, target_url)
    return value


def _replace_operator_handles(text: str, aliases: tuple[str, ...], target_handle: str) -> str:
    import re
    value = text
    for alias in aliases:
        if not alias:
            continue
        pattern = re.compile(rf"@{re.escape(alias)}\b", re.IGNORECASE)
        value = pattern.sub(f"@{target_handle}", value)
    return value


def _replace_link_urls(
    text: str,
    *,
    link_overrides: dict[str, str],
    link_url_aliases: dict[str, tuple[str, ...]],
    skip_keys: set[str],
) -> str:
    value = text
    for key, replacement in link_overrides.items():
        target = normalize_operator_url(replacement)
        if not target or key in skip_keys:
            continue
        target_handle = extract_operator_handle(target).lower()
        for alias in link_url_aliases.get(key, ()):
            if not alias:
                continue
            value = value.replace(alias, target)
            alt = alias.replace("https://", "http://")
            value = value.replace(alt, target)
            # Also replace @handle mentions derived from the alias URL
            alias_handle = extract_operator_handle(alias)
            if alias_handle and target_handle:
                pattern = re.compile(rf"@{re.escape(alias_handle)}\b", re.IGNORECASE)
                value = pattern.sub(f"@{target_handle}", value)
    return value


def _replace_single_link_url(
    url: str,
    *,
    link_overrides: dict[str, str],
    link_url_aliases: dict[str, tuple[str, ...]],
    skip_keys: set[str],
) -> str:
    for key, replacement in link_overrides.items():
        target = normalize_operator_url(replacement)
        if not target or key in skip_keys:
            continue
        aliases = link_url_aliases.get(key, ())
        if _is_same_url(url, aliases):
            return target
    return url


def _replace_sell_wallets(
    text: str,
    *,
    sell_wallet_overrides: dict[str, str],
    sell_wallet_aliases: dict[str, tuple[str, ...]],
) -> str:
    value = text
    for key, replacement in sell_wallet_overrides.items():
        wallet = (replacement or "").strip()
        if not wallet:
            continue
        for alias in sell_wallet_aliases.get(key, ()):
            if not alias:
                continue
            value = value.replace(alias, wallet)
    return value


def _patch_buttons(
    state: dict[str, Any],
    *,
    target_operator_url: str,
    target_operator_handle: str,
    operator_url_aliases: tuple[str, ...],
    operator_handle_aliases: tuple[str, ...],
    link_overrides: dict[str, str],
    link_url_aliases: dict[str, tuple[str, ...]],
    sell_wallet_overrides: dict[str, str],
    sell_wallet_aliases: dict[str, tuple[str, ...]],
) -> None:
    def patch_button(btn: dict[str, Any]) -> None:
        url = str(btn.get("url") or "")
        if target_operator_url:
            if url and _is_same_url(url, operator_url_aliases):
                btn["url"] = target_operator_url
                url = target_operator_url
        if url and link_overrides and link_url_aliases:
            btn["url"] = _replace_single_link_url(
                url,
                link_overrides=link_overrides,
                link_url_aliases=link_url_aliases,
                skip_keys={"operator"},
            )

        text = btn.get("text")
        if isinstance(text, str) and text:
            value = text
            if target_operator_handle:
                value = _replace_operator_handles(value, operator_handle_aliases, target_operator_handle)
            if sell_wallet_overrides and sell_wallet_aliases:
                value = _replace_sell_wallets(
                    value,
                    sell_wallet_overrides=sell_wallet_overrides,
                    sell_wallet_aliases=sell_wallet_aliases,
                )
            btn["text"] = value

    rows = state.get("button_rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, list):
                continue
            for btn in row:
                if isinstance(btn, dict):
                    patch_button(btn)

    buttons = state.get("buttons")
    if isinstance(buttons, list):
        for btn in buttons:
            if isinstance(btn, dict):
                patch_button(btn)


def _replace_commission(text: str, commission_percent: float) -> str:
    pct = f"{commission_percent:g}%"
    text = COMMISSION_SERVICE_RE.sub(
        lambda m: f"{m.group('prefix')}{m.group('open') or ''}{pct}{m.group('close') or ''}",
        text,
    )
    text = COMMISSION_PLAIN_RE.sub(
        lambda m: (
            f"{m.group('prefix')}{m.group('open') or ''}{pct}"
            f"{m.group('close') or ''}{m.group('suffix')}"
        ),
        text,
    )
    return text


def _normalize_url(value: str) -> str:
    raw = (value or "").strip().rstrip("/")
    if not raw:
        return ""
    return raw


def _is_same_url(url: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize_url(url)
    if not normalized:
        return False
    if normalized in {_normalize_url(alias) for alias in aliases if alias}:
        return True

    normalized_alt = normalized.replace("http://", "https://")
    alias_set_alt = {
        _normalize_url(alias).replace("http://", "https://")
        for alias in aliases
        if alias
    }
    return normalized_alt in alias_set_alt
