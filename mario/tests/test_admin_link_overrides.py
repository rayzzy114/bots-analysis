from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.adminkit.constants import LINK_LABELS
from app.config import Settings
from main import CloneRuntime, apply_admin_links_to_states

LEGACY_TERMS_URL = "https://telegra.ph/Pravila-ispolzovaniya-servisa-httpstmeMarioBTCbot-i-ego-politika-01-06"

pytestmark = pytest.mark.unit


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


def _all_test_links() -> dict[str, str]:
    return {key: f"https://example.com/{key}" for key in LINK_LABELS}


def _find_url_by_text(states: dict[str, dict[str, Any]], needle: str) -> str | None:
    wanted = needle.lower()
    for state in states.values():
        rows = state.get("button_rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list):
                continue
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                if str(btn.get("type") or "") != "KeyboardButtonUrl":
                    continue
                text = str(btn.get("text") or "")
                if wanted in text.lower():
                    return str(btn.get("url") or "")
    return None


def test_apply_admin_links_to_states_updates_all_link_keys() -> None:
    links = _all_test_links()
    states: dict[str, dict[str, Any]] = {
        "s1": {
            "button_rows": [
                [
                    {"type": "KeyboardButtonUrl", "text": "FAQ", "url": "https://old.local/faq"},
                    {"type": "KeyboardButtonUrl", "text": "Канал", "url": "https://old.local/channel"},
                    {"type": "KeyboardButtonUrl", "text": "Чат", "url": "https://old.local/chat"},
                    {"type": "KeyboardButtonUrl", "text": "Отзывы", "url": "https://old.local/reviews"},
                ],
                [
                    {
                        "type": "KeyboardButtonUrl",
                        "text": "Оставить отзыв",
                        "url": "https://old.local/review_form",
                    },
                    {"type": "KeyboardButtonUrl", "text": "Менеджер", "url": "https://old.local/manager"},
                    {"type": "KeyboardButtonUrl", "text": "Оператор", "url": "https://old.local/operator"},
                    {"type": "KeyboardButtonUrl", "text": "Условия", "url": LEGACY_TERMS_URL},
                ],
            ],
            "text": f"Текст с правилами: {LEGACY_TERMS_URL}",
            "text_html": f'<a href="{LEGACY_TERMS_URL}">Условия</a>',
            "text_markdown": LEGACY_TERMS_URL,
        }
    }

    result = apply_admin_links_to_states(states, links)

    flat_buttons = [btn for row in states["s1"]["button_rows"] for btn in row]
    expected_urls = [
        links["faq"],
        links["channel"],
        links["chat"],
        links["reviews"],
        links["review_form"],
        links["manager"],
        links["operator"],
        links["terms"],
    ]
    assert [btn["url"] for btn in flat_buttons] == expected_urls
    assert links["terms"] in states["s1"]["text"]
    assert links["terms"] in states["s1"]["text_html"]
    assert links["terms"] in states["s1"]["text_markdown"]
    assert result == {"button_urls_updated": 8, "text_urls_updated": 3}


def test_runtime_applies_admin_links_to_real_flow_states(tmp_path: Path) -> None:
    links = _all_test_links()
    admin_settings_path = tmp_path / "admin_settings.json"
    admin_settings_path.write_text(json.dumps({"links": links}, ensure_ascii=False), encoding="utf-8")
    project_dir = Path(__file__).resolve().parents[1]

    runtime = CloneRuntime(_settings(project_dir, tmp_path))

    assert _find_url_by_text(runtime.states, "оператор") == links["operator"]
    assert _find_url_by_text(runtime.states, "канал") == links["channel"]
    assert _find_url_by_text(runtime.states, "курилка") == links["chat"]
    assert _find_url_by_text(runtime.states, "отзывы") == links["reviews"]

    terms_texts = [
        str(state.get("text") or "")
        for state in runtime.states.values()
        if "Правила и условия использования сервиса" in str(state.get("text") or "")
    ]
    assert terms_texts
    assert all(links["terms"] in text for text in terms_texts)
    assert all(LEGACY_TERMS_URL not in text for text in terms_texts)


def test_apply_admin_links_to_states_skips_ambiguous_default_text_urls() -> None:
    links = _all_test_links()
    states: dict[str, dict[str, Any]] = {
        "s1": {
            "text": "Ссылка: https://t.me/mnIn_news",
            "text_html": "Ссылка: https://t.me/mnIn_news",
            "text_markdown": "Ссылка: https://t.me/mnIn_news",
            "button_rows": [],
        }
    }

    result = apply_admin_links_to_states(states, links)

    assert states["s1"]["text"] == "Ссылка: https://t.me/mnIn_news"
    assert states["s1"]["text_html"] == "Ссылка: https://t.me/mnIn_news"
    assert states["s1"]["text_markdown"] == "Ссылка: https://t.me/mnIn_news"
    assert result == {"button_urls_updated": 0, "text_urls_updated": 0}


def test_apply_admin_links_to_states_updates_operator_mentions() -> None:
    links = _all_test_links()
    links["operator"] = "https://t.me/new_operator_support"
    states: dict[str, dict[str, Any]] = {
        "s1": {
            "text": "Так же вы можете сделать обмен через оператора @BTC24MONEYnoch",
            "text_html": "Так же вы можете сделать обмен через оператора @BTC24MONEYnoch",
            "text_markdown": "Так же вы можете сделать обмен через оператора @BTC24MONEYnoch",
            "button_rows": [],
        }
    }

    result = apply_admin_links_to_states(states, links)

    assert "@new_operator_support" in states["s1"]["text"]
    assert "@new_operator_support" in states["s1"]["text_html"]
    assert "@new_operator_support" in states["s1"]["text_markdown"]
    assert "@BTC24MONEYnoch" not in states["s1"]["text"]
    assert "@BTC24MONEYnoch" not in states["s1"]["text_html"]
    assert "@BTC24MONEYnoch" not in states["s1"]["text_markdown"]
    assert result == {"button_urls_updated": 0, "text_urls_updated": 3}


def test_apply_admin_links_to_states_updates_operator_contact_with_non_mention_link() -> None:
    links = _all_test_links()
    links["operator"] = "https://example.com/new-operator"
    states: dict[str, dict[str, Any]] = {
        "s1": {
            "text": "Так же вы можете сделать обмен через оператора @BTC24MONEYnoch",
            "text_html": "Так же вы можете сделать обмен через оператора @BTC24MONEYnoch",
            "text_markdown": "Так же вы можете сделать обмен через оператора @BTC24MONEYnoch",
            "button_rows": [],
        }
    }

    first = apply_admin_links_to_states(states, links)
    assert links["operator"] in states["s1"]["text"]
    assert links["operator"] in states["s1"]["text_html"]
    assert links["operator"] in states["s1"]["text_markdown"]
    assert "@BTC24MONEYnoch" not in states["s1"]["text"]
    assert first == {"button_urls_updated": 0, "text_urls_updated": 3}

    links["operator"] = "https://example.com/operator-v2"
    second = apply_admin_links_to_states(states, links)
    assert links["operator"] in states["s1"]["text"]
    assert "https://example.com/new-operator" not in states["s1"]["text"]
    assert second == {"button_urls_updated": 0, "text_urls_updated": 3}
