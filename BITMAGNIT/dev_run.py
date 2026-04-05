import subprocess
import sys
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
WATCH_ROOTS = [PROJECT_DIR / "app", PROJECT_DIR / "main.py", PROJECT_DIR / ".env"]


def snapshot_mtimes() -> dict[str, float]:
    mtimes: dict[str, float] = {}
    for root in WATCH_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            mtimes[str(root)] = root.stat().st_mtime
            continue
        for path in root.rglob("*.py"):
            if path.is_file():
                mtimes[str(path)] = path.stat().st_mtime
    return mtimes


def start_bot() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        cwd=PROJECT_DIR,
        start_new_session=True,
    )


def stop_bot(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main() -> None:
    print("dev_run: starting bot with hot reload")
    process = start_bot()
    previous = snapshot_mtimes()
    try:
        while True:
            time.sleep(1.0)
            current = snapshot_mtimes()
            if current != previous:
                print("dev_run: changes detected, restarting bot...")
                stop_bot(process)
                process = start_bot()
                previous = current
            elif process.poll() is not None:
                print("dev_run: bot stopped, restarting...")
                process = start_bot()
                previous = snapshot_mtimes()
    except KeyboardInterrupt:
        print("\ndev_run: stopping (Ctrl+C)")
    finally:
        stop_bot(process)


if __name__ == "__main__":
    main()
