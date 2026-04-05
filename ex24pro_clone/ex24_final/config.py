from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env"

load_dotenv(ENV_PATH, override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: tuple[int, ...] = tuple(
    int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()
)

RATE_SPREAD_PERCENT = float(os.getenv("RATE_SPREAD_PERCENT", "5.0"))

MANAGER_NAMES = [
    "Анна", "Мария", "Елена", "Ольга", "Светлана",
    "Дарья", "Алиса", "Виктория", "Екатерина", "Наталья",
]

# --- Ban storage ---
import json

BANNED_FILE = PROJECT_DIR / "data" / "admin" / "banned_users.json"


def load_banned() -> set[int]:
    try:
        data = json.loads(BANNED_FILE.read_text())
        return set(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_banned(banned: set[int]) -> None:
    BANNED_FILE.write_text(json.dumps(sorted(banned), ensure_ascii=False))


banned_users: set[int] = load_banned()
