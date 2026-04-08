import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).parent / ".env"

def _get_env(key: str, default: str = "") -> str:
    """Read env var, checking .env file for updates."""
    load_dotenv(ENV_PATH)
    return os.getenv(key, default)

def reload_env():
    """Reload environment variables from .env file."""
    load_dotenv(ENV_PATH)

COMMISSION_PERCENT = int(os.environ.get('COMMISSION_PERCENT', 30))
