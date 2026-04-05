from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from watchfiles import run_process


def _run_bot() -> None:
    subprocess.run([sys.executable, "main.py"], check=False)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    run_process(
        str(root),
        target=_run_bot,
        watch_filter=None,
    )
