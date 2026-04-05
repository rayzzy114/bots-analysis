from __future__ import annotations

from keyboards import kb_source_choice


def test_source_keyboard_order_is_online_then_offline() -> None:
    keyboard = kb_source_choice()
    buttons = [button.text for row in keyboard.inline_keyboard for button in row]

    assert buttons == ["🌐 Онлайн", "🏠 Офлайн"]
