"""set() пишет в settings.json атомарно и переживает перезагрузку стора."""

import json

from app.storage import SettingsStore


async def test_set_persists_to_disk(settings):
    await settings.set("operator_url", "https://t.me/Persisted")
    on_disk = json.loads(settings.path.read_text("utf-8"))
    assert on_disk["operator_url"] == "https://t.me/Persisted"

    reloaded = SettingsStore(path=settings.path)
    assert reloaded.operator_url == "https://t.me/Persisted"


async def test_min_rub_per_coin_persists(settings):
    await settings.set_min_rub("xmr", 60000)
    reloaded = SettingsStore(path=settings.path)
    assert reloaded.min_rub("xmr") == 60000
    # остальные монеты не затронуты
    assert reloaded.min_rub("btc") == 795


def test_defaults_backfilled_on_first_load(tmp_path):
    s = SettingsStore(path=tmp_path / "s.json")
    assert s.path.exists()
    data = json.loads(s.path.read_text("utf-8"))
    assert "operator_url" in data and "min_rub_by_coin" in data
