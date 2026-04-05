from __future__ import annotations

from admin_kit import AdminKitConfig, LinkDefinition, build_admin_context
from admin_kit.runtime import persist_env_value
from admin_kit.utils import preferred_html_text, sanitize_html_fragment
from texts import get_text
from rates import _compute_cross_rates


def test_support_link_can_store_html_block(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    data_dir = tmp_path / "data"

    ctx = build_admin_context(
        AdminKitConfig(
            env_path=env_path,
            data_dir=data_dir,
            link_definitions=[
                LinkDefinition(key="support", label="Доп. способы связи", default="https://ex24qr.com"),
            ],
            admin_ids=[],
            default_commission=5.0,
        )
    )

    html_block = (
        '<a href="https://t.me/exchange24thalland">Ознакомиться</a><br>'
        '<a href="https://t.me/ex24pro_comments">Ознакомиться</a>'
    )
    persist_env_value("SUPPORT_LINK", html_block, ctx)

    assert ctx.settings.link("support") == html_block


def test_malformed_support_link_is_sanitized_in_start_caption() -> None:
    bad_value = '<EX24PRO="https://t.me/Exchange24Thalland"'
    caption = get_text("welcome_caption", "ru").format(
        ticket_id="1234567",
        manager_name="Анна",
        link_support=sanitize_html_fragment(bad_value),
    )

    assert bad_value not in caption
    assert "&lt;EX24PRO" in caption


def test_admin_rate_lines_show_commissioned_values() -> None:
    rates = _compute_cross_rates(
        {"rub": 100.0, "thb": 20.0, "cny": 10.0, "aed": 5.0, "idr": 20000.0},
        10.0,
    )
    spread = 0.10
    assert rates["usdt_thb"] == 22.0
    assert f"{rates['usdt_thb']:.2f} -> {rates['usdt_thb'] * (1 + spread):.2f}" == "22.00 -> 24.20"


def test_preferred_html_text_keeps_html_entities() -> None:
    assert preferred_html_text(
        "https://example.com",
        '<a href="https://t.me/exchange24thalland">Ознакомиться</a>',
    ) == '<a href="https://t.me/exchange24thalland">Ознакомиться</a>'


def test_preferred_html_text_keeps_literal_html_input() -> None:
    raw_html = '<a href="https://t.me/Exchange24Thalland">EX24PRO</a>'
    escaped_html = '&lt;a href="https://t.me/Exchange24Thalland"&gt;EX24PRO&lt;/a&gt;'
    assert preferred_html_text(raw_html, escaped_html) == raw_html


def test_sanitize_html_fragment_unescapes_safe_anchor() -> None:
    escaped_html = '&lt;a href="https://t.me/Exchange24Thalland"&gt;EX24PRO&lt;/a&gt;'
    assert sanitize_html_fragment(escaped_html) == '<a href="https://t.me/Exchange24Thalland">EX24PRO</a>'


def test_support_link_html_block_round_trips_from_html_text(tmp_path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("", encoding="utf-8")
    data_dir = tmp_path / "data"
    ctx = build_admin_context(
        AdminKitConfig(
            env_path=env_path,
            data_dir=data_dir,
            link_definitions=[
                LinkDefinition(key="support", label="Доп. способы связи", default="https://ex24qr.com"),
            ],
            admin_ids=[],
            default_commission=5.0,
        )
    )

    html_block = '<a href="https://t.me/exchange24thalland">Ознакомиться</a><br><a href="https://t.me/ex24pro_comments">Ознакомиться</a>'
    persist_env_value("SUPPORT_LINK", html_block, ctx)

    assert ctx.settings.link("support") == html_block
