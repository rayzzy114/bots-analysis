"""Сверка типов клавиатур с clone_spec §2 (reply vs inline)."""

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from app import keyboards
from app.storage import SettingsStore

S = SettingsStore


def _s(tmp_path):
    return SettingsStore(path=tmp_path / "s.json")


def test_link_and_status_screens_are_inline(tmp_path):
    s = _s(tmp_path)
    for kb in (keyboards.kb_operator(s), keyboards.kb_site(s), keyboards.kb_help_links(s)):
        assert isinstance(kb, InlineKeyboardMarkup)


def test_calc_is_inline(tmp_path):
    assert isinstance(keyboards.kb_calc_default("btc", "795", False), InlineKeyboardMarkup)
    assert isinstance(keyboards.kb_calc_pad("btc"), InlineKeyboardMarkup)


def test_menu_coin_address_wallets_are_reply():
    for kb in (
        keyboards.kb_main_menu(),
        keyboards.kb_choose_coin(),
        keyboards.kb_back(),
        keyboards.kb_address_valid(),
        keyboards.kb_payment(),
        keyboards.kb_wallets_choose_coin(),
        keyboards.kb_wallets_list(),
        keyboards.kb_cancel_confirm(),
    ):
        assert isinstance(kb, ReplyKeyboardMarkup)


def test_operator_label_override(tmp_path):
    s = _s(tmp_path)
    kb = keyboards.kb_operator(s, label="👨‍💻 оператор")
    assert kb.inline_keyboard[0][0].text == "👨‍💻 оператор"
