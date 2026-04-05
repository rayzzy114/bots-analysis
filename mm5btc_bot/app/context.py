from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .storage import RuntimeStore, SettingsStore


@dataclass
class AppContext:
    root_dir: Path
    settings: SettingsStore
    runtime: RuntimeStore
    admin_ids: set[int]
