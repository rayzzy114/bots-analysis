from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from main import CloneRuntime


def _settings(project_dir: Path, tmp_path: Path) -> Settings:
    return Settings(
        project_dir=project_dir,
        bot_token="test-token",
        debug=False,
        hot_reload=False,
        hot_reload_interval_seconds=1.0,
        session_history_limit=30,
        order_ttl_seconds=900,
        log_level="INFO",
        admin_ids=set(),
        default_commission_percent=2.5,
        rate_cache_ttl_seconds=45,
        delete_webhook_on_start=False,
        search_delay_seconds=1,
        raw_dir=project_dir / "data" / "raw",
        compiled_dir=tmp_path / "compiled",
        media_dir=project_dir / "assets" / "media",
        orders_store_path=tmp_path / "runtime_orders.json",
        sessions_store_path=tmp_path / "runtime_sessions.json",
        admin_settings_path=tmp_path / "admin_settings.json",
        media_file_id_cache_path=tmp_path / "runtime_media_file_ids.json",
    )


@pytest.mark.smoke
def test_smoke_runtime_bootstraps_from_compiled_data(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    runtime = CloneRuntime(_settings(project_dir, tmp_path))

    assert runtime.entry_state_id in runtime.states
    assert runtime.search_wait_state_id in runtime.states
    assert runtime.replay_calc.quotes
