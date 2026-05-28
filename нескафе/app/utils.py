"""Безопасная отправка медиа/стикеров: ошибки сети/файла не роняют хендлер."""

from __future__ import annotations

import logging

from aiogram.types import FSInputFile, Message

from . import media

log = logging.getLogger(__name__)


async def send_sticker(message: Message, emoji: str) -> None:
    """Отправить стикер по эмодзи отдельным сообщением (молча игнорируя сбои)."""
    sticker = media.sticker(emoji)
    if sticker is None:
        return
    try:
        await message.answer_sticker(sticker)
    except Exception as exc:  # noqa: BLE001
        log.warning("send_sticker(%s) failed: %s", emoji, exc)


async def send_animation_or_text(
    message: Message, doc: FSInputFile | None, *, text: str, **kwargs
) -> None:
    """Послать анимацию (doc) с подписью/кнопками; при сбое — текст с теми же кнопками."""
    if doc is not None:
        try:
            await message.answer_animation(doc, caption=text or None, **kwargs)
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("send_animation failed, falling back to text: %s", exc)
    await message.answer(text or "⁣", **kwargs)


async def send_photo_or_text(
    message: Message, photo: FSInputFile | None, *, text: str, **kwargs
) -> None:
    if photo is not None:
        try:
            await message.answer_photo(photo, caption=text or None, **kwargs)
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("send_photo failed, falling back to text: %s", exc)
    await message.answer(text or "⁣", **kwargs)
