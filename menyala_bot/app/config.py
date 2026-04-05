import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .constants import DEFAULT_LINKS
from .utils import parse_admin_ids


@dataclass
class AppConfig:
    bot_token: str
    admin_ids: set[int]
    default_commission_percent: float
    links: dict[str, str]
    env_path: Path


def _safe_float(raw: str, default: float) -> float:
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < 0:
        return default
    return value


def load_config(base_dir: Path) -> AppConfig:
    env_path = base_dir / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is empty. Fill .env first.")

    admin_ids = parse_admin_ids(os.getenv("ADMIN_IDS", ""))
    default_commission_percent = _safe_float(
        os.getenv("DEFAULT_COMMISSION_PERCENT", "7"),
        default=7.0,
    )

    links = dict(DEFAULT_LINKS)
    for link_key in links:
        env_key = f"{link_key.upper()}_LINK"
        value = (os.getenv(env_key) or "").strip()
        if value:
            links[link_key] = value

    return AppConfig(
        bot_token=token,
        admin_ids=admin_ids,
        default_commission_percent=default_commission_percent,
        links=links,
        env_path=env_path,
    )
