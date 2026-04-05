from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.constants import DEFAULT_LINKS
from app.handlers.admin import apply_runtime_from_env
from app.handlers.flow import build_button_url_resolver
from app.storage import SettingsStore


class _DummyContext:
    def __init__(self, settings: SettingsStore) -> None:
        self.settings = settings
        self.admin_ids: set[int] = set()


class AdminRuntimeUpdatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.temp_dir.name) / "settings.json"
        self.settings = SettingsStore(
            path=self.settings_path,
            default_commission=15.0,
            env_links=dict(DEFAULT_LINKS),
        )
        self.ctx = _DummyContext(self.settings)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_apply_runtime_from_env_updates_commission_and_links(self) -> None:
        apply_runtime_from_env(
            self.ctx,
            {
                "ADMIN_IDS": "101, 202",
                "DEFAULT_COMMISSION_PERCENT": "2.75",
                "OPERATOR_LINK": "https://t.me/new_operator",
                "TERMS_LINK": "https://telegra.ph/new-terms",
            },
        )

        self.assertEqual(self.ctx.admin_ids, {101, 202})
        self.assertEqual(self.settings.commission_percent, 2.75)
        self.assertEqual(self.settings.link("operator"), "https://t.me/new_operator")
        self.assertEqual(self.settings.link("terms"), "https://telegra.ph/new-terms")

    def test_link_resolver_uses_latest_settings_values_without_restart(self) -> None:
        resolver = build_button_url_resolver(self.settings.link)

        self.assertEqual(
            resolver("👨‍🚀 Оператор", "https://t.me/RAPID_EX_Operator"),
            "https://t.me/RAPID_EX_Operator",
        )

        self.settings.set_link("operator", "https://t.me/runtime_operator")

        self.assertEqual(
            resolver("👨‍🚀 Оператор", "https://t.me/RAPID_EX_Operator"),
            "https://t.me/runtime_operator",
        )


if __name__ == "__main__":
    unittest.main()
