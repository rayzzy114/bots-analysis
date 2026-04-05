from __future__ import annotations

import asyncio

import handlers.livechat as livechat
from texts import get_text


class _FakeSentMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class _FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[int, str, dict[str, object]]] = []
        self.sent_messages: list[_FakeSentMessage] = []

    async def send_message(self, user_id: int, text: str, **kwargs: object) -> _FakeSentMessage:
        self.calls.append((user_id, text, dict(kwargs)))
        message = _FakeSentMessage(text)
        self.sent_messages.append(message)
        return message


def test_source_aftercare_sends_temporary_status_then_final_block() -> None:
    fake_bot = _FakeBot()
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    original_sleep = livechat.asyncio.sleep
    livechat.asyncio.sleep = fake_sleep  # type: ignore[assignment]
    try:
        asyncio.run(livechat._send_source_aftercare_via_bot(fake_bot, 42, "ru"))
    finally:
        livechat.asyncio.sleep = original_sleep  # type: ignore[assignment]

    assert [call[1] for call in fake_bot.calls] == [
        "💛 Спасибо, менеджер уже подключается...",
        get_text("welcome_manager_connected", "ru"),
        "💛 Здравствуйте, чем могу Вам помочь?",
    ]
    assert sleep_calls == [7, 3]
    assert fake_bot.sent_messages[0].deleted is True
    assert "link_preview_options" in fake_bot.calls[1][2]
