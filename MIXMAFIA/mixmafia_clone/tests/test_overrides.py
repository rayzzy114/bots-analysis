"""Tests: commission and wallet substitution propagation."""
from __future__ import annotations

import pytest
from app.overrides import RuntimeOverrides, apply_state_overrides


_OVERRIDE_FIELDS = {"operator_url", "link_overrides", "sell_wallet_overrides", "commission_percent"}


def _apply(state: dict, **kwargs) -> dict:
    override_kwargs = {k: v for k, v in kwargs.items() if k in _OVERRIDE_FIELDS}
    extra_kwargs = {k: v for k, v in kwargs.items() if k not in _OVERRIDE_FIELDS}
    return apply_state_overrides(
        state=state,
        overrides=RuntimeOverrides(**override_kwargs),
        operator_url_aliases=(),
        operator_handle_aliases=(),
        **extra_kwargs,
    )


class TestCommissionReplacement:
    def test_commission_replaced_in_text(self):
        state = {"text": "Комиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=20.0)
        assert "20%" in result["text"]
        assert "1.5%" not in result["text"]

    def test_commission_replaced_in_text_html(self):
        state = {"text_html": "Комиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=5.0)
        assert "5%" in result["text_html"]
        assert "1.5%" not in result["text_html"]

    def test_commission_replaced_in_html_with_strong_tag(self):
        state = {"text_html": "Комиссия сервиса: <strong>1.5%</strong>"}
        result = _apply(state, commission_percent=25.0)
        assert "<strong>25%</strong>" in result["text_html"]
        assert "1.5%" not in result["text_html"]

    def test_commission_replaced_in_markdown_with_bold_tag(self):
        state = {"text_markdown": "Комиссия сервиса: **1.5%**"}
        result = _apply(state, commission_percent=25.0)
        assert "**25%**" in result["text_markdown"]
        assert "1.5%" not in result["text_markdown"]

    def test_plain_pattern_replaced(self):
        state = {"text": "только 2% и ничего более!"}
        result = _apply(state, commission_percent=3.5)
        assert "3.5%" in result["text"]
        assert "2%" not in result["text"]

    def test_zero_commission_leaves_text_unchanged(self):
        state = {"text": "Комиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=0.0)
        assert "1.5%" in result["text"]

    def test_commission_integer_formats_cleanly(self):
        state = {"text": "Комиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=10.0)
        assert "10%" in result["text"]
        assert "10.0%" not in result["text"]

    def test_all_commission_occurrences_replaced(self):
        state = {"text": "Комиссия сервиса: 1.5%\nКомиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=7.0)
        assert result["text"].count("7%") == 2
        assert "1.5%" not in result["text"]


class TestWalletReplacement:
    def test_wallet_replaced_in_text(self):
        state = {"text": "Адрес: bc1qold000000000000000000000000000000000"}
        result = _apply(
            state,
            sell_wallet_overrides={"btc_clean": "bc1qNEW111111111111111111111111111111111"},
            sell_wallet_aliases={"btc_clean": ("bc1qold000000000000000000000000000000000",)},
        )
        assert "bc1qNEW" in result["text"]
        assert "bc1qold" not in result["text"]

    def test_wallet_replaced_in_button_text(self):
        state = {
            "buttons": [{"text": "Отправить на bc1qold000000000000", "type": "KeyboardButton"}]
        }
        result = _apply(
            state,
            sell_wallet_overrides={"btc_clean": "bc1qNEW111111111111111"},
            sell_wallet_aliases={"btc_clean": ("bc1qold000000000000",)},
        )
        assert "bc1qNEW" in result["buttons"][0]["text"]

    def test_unknown_wallet_key_skipped(self):
        """No crash if wallet key has no alias."""
        state = {"text": "some text"}
        result = _apply(
            state,
            sell_wallet_overrides={"nonexistent_key": "bc1qNEW"},
            sell_wallet_aliases={},
        )
        assert result["text"] == "some text"


class TestLinkReplacement:
    def test_link_replaced_in_button_url(self):
        state = {
            "buttons": [
                {"text": "Канал", "type": "KeyboardButtonUrl", "url": "https://t.me/oldchannel"}
            ]
        }
        result = _apply(
            state,
            link_overrides={"channel": "https://t.me/newchannel"},
            link_url_aliases={"channel": ("https://t.me/oldchannel",)},
        )
        assert result["buttons"][0]["url"] == "https://t.me/newchannel"

    def test_link_replaced_in_text(self):
        state = {"text": "Перейди сюда: https://t.me/oldchannel"}
        result = _apply(
            state,
            link_overrides={"channel": "https://t.me/newchannel"},
            link_url_aliases={"channel": ("https://t.me/oldchannel",)},
        )
        assert "https://t.me/newchannel" in result["text"]
        assert "oldchannel" not in result["text"]
