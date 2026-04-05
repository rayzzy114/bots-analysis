import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
WATCH_SUFFIXES = {".py"}
WATCH_NAMES = {".env"}
IGNORE_PARTS = {".git", "__pycache__", ".ruff_cache", ".venv", "venv"}


def iter_watch_files() -> list[Path]:
    files: list[Path] = []
    for path in BASE_DIR.rglob("*"):
        if path.is_dir():
            continue
        if any(part in IGNORE_PARTS for part in path.parts):
            continue
        if path.suffix in WATCH_SUFFIXES or path.name in WATCH_NAMES:
            files.append(path)
    return files


def build_snapshot() -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    for path in iter_watch_files():
        try:
            snapshot[path] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def start_bot() -> subprocess.Popen[bytes]:
    print("[dev] starting bot process...")
    return subprocess.Popen([sys.executable, "main.py"], cwd=BASE_DIR)


def stop_bot(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    process = start_bot()
    snapshot = build_snapshot()
    try:
        while True:
            time.sleep(1)
            current_snapshot = build_snapshot()
            if current_snapshot != snapshot:
                print("[dev] change detected, restarting...")
                stop_bot(process)
                process = start_bot()
                snapshot = current_snapshot
                continue
            if process.poll() is not None:
                print(f"[dev] bot exited with code {process.returncode}, restarting...")
                process = start_bot()
                snapshot = build_snapshot()
    except KeyboardInterrupt:
        print("[dev] stopping...")
    finally:
        stop_bot(process)


if __name__ == "__main__":
    main()
