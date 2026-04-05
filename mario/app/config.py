from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_dir: Path
    bot_token: str
    debug: bool
    hot_reload: bool
    hot_reload_interval_seconds: float
    session_history_limit: int
    order_ttl_seconds: int
    log_level: str
    admin_ids: set[int]
    default_commission_percent: float
    rate_cache_ttl_seconds: int
    delete_webhook_on_start: bool
    search_delay_seconds: int
    raw_dir: Path
    compiled_dir: Path
    media_dir: Path
    orders_store_path: Path
    sessions_store_path: Path
    admin_settings_path: Path
    media_file_id_cache_path: Path


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_admin_ids(raw: str) -> set[int]:
    result: set[int] = set()
    for chunk in (raw or "").split(","):
        item = chunk.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            continue
    return result


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings(project_dir: Path) -> Settings:
    env_path = project_dir / ".env"
    load_dotenv(env_path, override=True)

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty in .env")

    raw_dir = project_dir / "data" / "raw"
    compiled_dir = project_dir / "data" / "compiled"
    media_dir = project_dir / "assets" / "media"
    compiled_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        project_dir=project_dir,
        bot_token=bot_token,
        debug=_as_bool(os.getenv("DEBUG", "false")),
        hot_reload=_as_bool(os.getenv("HOT_RELOAD", "false")),
        hot_reload_interval_seconds=_env_float("HOT_RELOAD_INTERVAL_SECONDS", 1.0),
        session_history_limit=_env_int("SESSION_HISTORY_LIMIT", 30),
        order_ttl_seconds=_env_int("ORDER_TTL_SECONDS", 900),
        log_level=(os.getenv("LOG_LEVEL") or "INFO").strip(),
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS") or ""),
        default_commission_percent=_env_float("DEFAULT_COMMISSION_PERCENT", 2.5),
        rate_cache_ttl_seconds=_env_int("RATE_CACHE_TTL_SECONDS", 45),
        delete_webhook_on_start=_as_bool(os.getenv("DELETE_WEBHOOK_ON_START", "false")),
        search_delay_seconds=_env_int("SEARCH_DELAY_SECONDS", 15),
        raw_dir=raw_dir,
        compiled_dir=compiled_dir,
        media_dir=media_dir,
        orders_store_path=project_dir / "data" / "runtime_orders.json",
        sessions_store_path=project_dir / "data" / "runtime_sessions.json",
        admin_settings_path=project_dir / "data" / "admin_settings.json",
        media_file_id_cache_path=project_dir / "data" / "runtime_media_file_ids.json",
    )
