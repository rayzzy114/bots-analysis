import asyncio
from pathlib import Path

from watchfiles import Change, run_process

from main import amain

PROJECT_DIR = Path(__file__).resolve().parent
IGNORED_DIRS = {".git", ".venv", "__pycache__", "data", "assets"}
RELOAD_FILES = {".env", "captured_flow.json"}


def watch_filter(change: Change, path: str) -> bool:
    _ = change
    file_path = Path(path)
    try:
        rel = file_path.resolve().relative_to(PROJECT_DIR)
    except Exception:
        return False
    if any(part in IGNORED_DIRS for part in rel.parts):
        return False
    if rel.suffix == ".py":
        return True
    return rel.as_posix() in RELOAD_FILES


def run_bot() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    run_process(str(PROJECT_DIR), target=run_bot, watch_filter=watch_filter)
