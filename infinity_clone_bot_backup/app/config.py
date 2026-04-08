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
    base_dir: Path

    @classmethod
    def from_env(cls, base_dir: Path) -> "AppConfig":
        load_dotenv(base_dir / ".env")
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN не задан в .env")

        links = {
            key: os.getenv(f"{key.upper()}_LINK", DEFAULT_LINKS[key]).strip() for key in DEFAULT_LINKS
        }
        return cls(
            bot_token=token,
            admin_ids=parse_admin_ids(os.getenv("ADMIN_IDS", "")),
            default_commission_percent=float(os.getenv("DEFAULT_COMMISSION_PERCENT", "2.5")),
            links=links,
            base_dir=base_dir,
        )
