import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.storage import SettingsStore  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return SettingsStore(path=tmp_path / "settings.json")
