"""Безопасная отправка медиа/стикеров: ошибки сети/файла не роняют хендлер."""

from __future__ import annotations

import asyncio
import logging
import random

from aiogram.types import FSInputFile, Message

from . import media

log = logging.getLogger(__name__)

# Диапазон «человеческой» задержки на экранах проверки (сек).
HUMAN_DELAY_MIN = 2.0
HUMAN_DELAY_MAX = 4.0


async def human_delay(lo: float = HUMAN_DELAY_MIN, hi: float = HUMAN_DELAY_MAX) -> None:
    """Случайная пауза 2–4 с — чтобы «проверка» выглядела реалистично."""
    await asyncio.sleep(random.uniform(lo, hi))


# Транзиентные «песочные часы» бота: отдельное сообщение "⏳", которое
# появляется и удаляется через ~2 с (events.jsonl: msg «⏳» при проверках/калькуляторе).
HOURGLASS = "⏳"


async def safe_delete(message) -> None:
    """Удалить сообщение, молча игнорируя сбой (нет прав / уже удалено)."""
    try:
        await message.delete()
    except Exception as exc:  # noqa: BLE001
        log.debug("delete failed: %s", exc)


async def transient_message(message: Message, *, text: str | None = None,
                            sticker: FSInputFile | None = None,
                            reply_to: int | None = None, hold: float = 2.0) -> None:
    """Показать отдельное сообщение (текст ИЛИ стикер) и убрать через `hold` секунд.

    Используется для «мелькающих» медиа бота: ⏳ на проверках, 🧮 на «МИН ОБМЕН»,
    стикер-заяц на «списать монеты».
    """
    try:
        if sticker is not None:
            ghost = await message.answer_sticker(sticker, reply_to_message_id=reply_to)
        else:
            ghost = await message.answer(text or HOURGLASS, reply_to_message_id=reply_to)
    except Exception as exc:  # noqa: BLE001
        log.debug("transient send failed: %s", exc)
        return
    await asyncio.sleep(hold)
    await safe_delete(ghost)


async def transient_hourglass(message: Message, *, reply_to: int | None = None,
                              hold: float = 2.0) -> None:
    """Показать "⏳" отдельным сообщением и убрать через `hold` секунд."""
    await transient_message(message, text=HOURGLASS, reply_to=reply_to, hold=hold)


async def delete_after(message, delay: float = 2.0) -> None:
    """Удалить уже отправленное сообщение через `delay` секунд (фон).

    Для случая «эмодзи показываем СРАЗУ, удаляем позже» — само сообщение шлётся
    синхронно до основного действия, а тут только отложенное удаление.
    """
    await asyncio.sleep(delay)
    await safe_delete(message)


async def send_sticker(message: Message, emoji: str) -> None:
    """Отправить стикер по эмодзи отдельным сообщением (молча игнорируя сбои)."""
    sticker = media.sticker(emoji)
    if sticker is None:
        return
    try:
        await message.answer_sticker(sticker)
    except Exception as exc:  # noqa: BLE001
        log.warning("send_sticker(%s) failed: %s", emoji, exc)


async def send_transient_then(message: Message, transient_emoji: str, answer: str, **kwargs) -> None:
    """Послать эмодзи-сообщение, подержать 2–3 с, удалить и отправить ответ.

    В справочнике перед каждым ответом всплывает и через паузу исчезает эмодзи
    (❔ для вопросов, 🤖 для «обо мне»).
    """
    try:
        ghost = await message.answer(transient_emoji)
        await human_delay(2.0, 3.0)
        await ghost.delete()
    except Exception as exc:  # noqa: BLE001
        log.warning("transient emoji failed: %s", exc)
    await message.answer(answer, **kwargs)


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
