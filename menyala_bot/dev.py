from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


WATCH_EXTENSIONS = {".py"}
CHECK_INTERVAL_SECONDS = 0.7


def iter_source_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in WATCH_EXTENSIONS]


def snapshot_mtimes(root: Path) -> dict[Path, int]:
    mtimes: dict[Path, int] = {}
    for path in iter_source_files(root):
        try:
            mtimes[path] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return mtimes


def has_changes(before: dict[Path, int], after: dict[Path, int]) -> bool:
    return before != after


def main() -> None:
    root = Path(__file__).resolve().parent
    cmd = [sys.executable, "main.py"]
    print("[dev] starting bot with hot reload")
    print(f"[dev] command: {' '.join(cmd)}")
    baseline = snapshot_mtimes(root)
    process = subprocess.Popen(cmd, cwd=root)
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            current = snapshot_mtimes(root)
            if has_changes(baseline, current):
                baseline = current
                print("[dev] file change detected, restarting bot...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                process = subprocess.Popen(cmd, cwd=root)
            if process.poll() is not None:
                print("[dev] bot stopped, starting again...")
                process = subprocess.Popen(cmd, cwd=root)
    except KeyboardInterrupt:
        print("\n[dev] stopping...")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
