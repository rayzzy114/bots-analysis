from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values, load_dotenv, set_key

from .config import LinkDefinition
from .context import AppContext
from .utils import parse_admin_ids, parse_amount

VISIBLE_BASE_ENV_KEYS = frozenset({"ADMIN_IDS", "RATE_SPREAD_PERCENT"})
CLEAR_MARKERS = frozenset({"-", "clear", "delete", "очистить"})


def commission_from_env(env: Mapping[str, str | None], fallback: float) -> float:
    raw = (env.get("RATE_SPREAD_PERCENT") or "").strip()
    value = parse_amount(raw, allow_zero=True)
    if value is None or value > 50:
        return fallback
    return value


def visible_env_keys(
    link_definitions: tuple[LinkDefinition, ...],
    sell_wallet_labels: Mapping[str, str],
) -> frozenset[str]:
    keys = set(VISIBLE_BASE_ENV_KEYS)
    keys.update(item.resolved_env_key for item in link_definitions)
    return frozenset(keys)


def normalize_input_value(raw: str) -> str:
    value = raw.strip()
    if value.lower() in CLEAR_MARKERS:
        return ""
    return value


def apply_runtime_from_env(ctx: AppContext, env: Mapping[str, str | None]) -> None:
    ctx.admin_ids = parse_admin_ids((env.get("ADMIN_IDS") or "").strip()) or set(ctx.admin_ids)

    commission = parse_amount(str(env.get("RATE_SPREAD_PERCENT") or ""), allow_zero=True)
    if commission is not None and 0 <= commission <= 50:
        ctx.settings.set_commission(commission)

    for item in ctx.link_definitions:
        env_key = item.resolved_env_key
        if env_key not in env:
            continue
        ctx.settings.set_link(item.key, (env.get(env_key) or "").strip())


def persist_env_value(key: str, value: str, ctx: AppContext) -> None:
    env_path = Path(ctx.env_path)
    set_key(
        dotenv_path=str(env_path),
        key_to_set=key,
        value_to_set=value,
        quote_mode="auto",
    )
    load_dotenv(dotenv_path=env_path, override=True)
    apply_runtime_from_env(ctx, dotenv_values(env_path))
