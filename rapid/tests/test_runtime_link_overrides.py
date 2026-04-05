from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.constants import DEFAULT_LINKS
from app.flow_catalog import CapturedFlow
from app.handlers.flow import (
    apply_runtime_text_links_to_text,
    build_button_url_resolver,
    build_link_key_resolver,
)


class RuntimeLinkOverridesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.flow_path = Path(self.temp_dir.name) / "flow.json"
        self.flow_path.write_text(
            json.dumps(
                {
                    "state_with_links": {
                        "button_rows": [
                            [
                                {
                                    "type": "KeyboardButtonUrl",
                                    "text": "Отзывы 📣",
                                    "url": DEFAULT_LINKS["reviews"],
                                },
                                {
                                    "type": "KeyboardButtonUrl",
                                    "text": "🎮 Чат-Админ",
                                    "url": "https://t.me/RAPID_EX_Admin",
                                },
                                {
                                    "type": "KeyboardButtonUrl",
                                    "text": "💬 Чат",
                                    "url": DEFAULT_LINKS["chat"],
                                },
                            ]
                        ]
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_resolver_uses_separate_keys_for_reviews_and_review_form(self) -> None:
        links = dict(DEFAULT_LINKS)
        links["reviews"] = "https://t.me/new_reviews"
        links["review_form"] = "https://t.me/new_review_form"
        links["chat"] = "https://t.me/new_chat"

        resolver = build_button_url_resolver(links)

        self.assertEqual(
            resolver("Отзывы 📣", DEFAULT_LINKS["reviews"]),
            "https://t.me/new_reviews",
        )
        self.assertEqual(
            resolver("🎮 Чат-Админ", "https://t.me/RAPID_EX_Admin"),
            "https://t.me/new_review_form",
        )
        self.assertEqual(
            resolver("Чат для админов", "https://t.me/RAPID_EX_Admin"),
            "https://t.me/new_review_form",
        )
        self.assertEqual(
            resolver("💬 Чат", DEFAULT_LINKS["chat"]),
            "https://t.me/new_chat",
        )

    def test_terms_text_link_becomes_clickable_anchor_with_runtime_url(self) -> None:
        links = dict(DEFAULT_LINKS)
        links["terms"] = "https://telegra.ph/new-terms"
        key_resolver = build_link_key_resolver()
        url_resolver = build_button_url_resolver(links, link_key_resolver=key_resolver)
        text = (
            "❗️ Нажав кнопку \"Подтвердить\", "
            "Вы автоматически соглашаетесь с условиями сделки!"
        )

        result = apply_runtime_text_links_to_text(
            text,
            text_links=[DEFAULT_LINKS["terms"]],
            link_key_resolver=key_resolver,
            url_resolver=url_resolver,
        )

        self.assertIn(
            '<a href="https://telegra.ph/new-terms">условиями сделки</a>',
            result,
        )

    def test_custom_alias_rules_can_resolve_review_form(self) -> None:
        links = dict(DEFAULT_LINKS)
        links["review_form"] = "https://t.me/custom_review_form"
        rules = {
            "review_form": {
                "text_contains": ("админский чат",),
                "source_urls": ("https://t.me/legacy_admin_chat",),
            }
        }

        key_resolver = build_link_key_resolver(rules)
        url_resolver = build_button_url_resolver(links, link_key_resolver=key_resolver)

        self.assertEqual(
            url_resolver("Админский чат", "https://t.me/legacy_admin_chat"),
            "https://t.me/custom_review_form",
        )

    def test_text_link_with_bold_digits_stays_clickable(self) -> None:
        key_resolver = build_link_key_resolver()
        url_resolver = build_button_url_resolver(dict(DEFAULT_LINKS), link_key_resolver=key_resolver)
        rich_text = "t.me/RAPID_EX_BOT?start=<b>6131246501</b>"

        result = apply_runtime_text_links_to_text(
            rich_text,
            text_links=["t.me/RAPID_EX_BOT?start=6131246501"],
            link_key_resolver=key_resolver,
            url_resolver=url_resolver,
        )

        self.assertIn(
            '<a href="https://t.me/RAPID_EX_BOT?start=6131246501">'
            "t.me/RAPID_EX_BOT?start=<b>6131246501</b></a>",
            result,
        )

    def test_inline_keyboard_applies_runtime_url_overrides(self) -> None:
        links = dict(DEFAULT_LINKS)
        links["reviews"] = "https://t.me/new_reviews"
        links["review_form"] = "https://t.me/new_review_form"
        links["chat"] = "https://t.me/new_chat"

        flow = CapturedFlow(
            self.flow_path,
            url_resolver=build_button_url_resolver(links),
        )

        markup = flow.inline_keyboard("state_with_links")
        self.assertIsNotNone(markup)
        buttons = markup.inline_keyboard[0]
        self.assertEqual(buttons[0].url, "https://t.me/new_reviews")
        self.assertEqual(buttons[1].url, "https://t.me/new_review_form")
        self.assertEqual(buttons[2].url, "https://t.me/new_chat")

    def test_default_review_form_keeps_admin_chat_url(self) -> None:
        resolver = build_button_url_resolver(dict(DEFAULT_LINKS))
        self.assertEqual(
            resolver("🎮 Чат-Админ", "https://t.me/RAPID_EX_Admin"),
            "https://t.me/RAPID_EX_Admin",
        )


if __name__ == "__main__":
    unittest.main()
