from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram import Bot


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}


def action_token(action_text: str) -> str:
    digest = hashlib.sha1(action_text.encode("utf-8")).hexdigest()[:24]
    return f"a:{digest}"


def _button_rows(state: dict[str, Any]) -> list[list[dict[str, Any]]]:
    rows = state.get("button_rows")
    if isinstance(rows, list):
        parsed: list[list[dict[str, Any]]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            parsed_row = [btn for btn in row if isinstance(btn, dict)]
            if parsed_row:
                parsed.append(parsed_row)
        if parsed:
            return parsed

    fallback = state.get("buttons")
    if isinstance(fallback, list) and fallback:
        return [[btn for btn in fallback if isinstance(btn, dict)]]
    return []


def build_markup(
    state: dict[str, Any],
    token_by_action: Callable[[str], str],
) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | None:
    if state.get("remove_keyboard"):
        return ReplyKeyboardRemove()

    rows = _button_rows(state)
    if not rows:
        return None

    types = {
        str(btn.get("type") or "")
        for row in rows
        for btn in row
        if str(btn.get("text") or "").strip()
    }

    if types == {"KeyboardButton"}:
        keyboard: list[list[KeyboardButton]] = []
        for row in rows:
            k_row: list[KeyboardButton] = []
            for btn in row:
                text = str(btn.get("text") or "").strip()
                if text:
                    k_row.append(KeyboardButton(text=text))
            if k_row:
                keyboard.append(k_row)
        if keyboard:
            return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
        return None

    inline_rows: list[list[InlineKeyboardButton]] = []
    for row in rows:
        i_row: list[InlineKeyboardButton] = []
        for btn in row:
            text = str(btn.get("text") or "").strip()
            if not text:
                continue
            btn_type = str(btn.get("type") or "")
            callback_text = str(btn.get("callback_text") or text).strip()
            if btn_type == "KeyboardButtonUrl":
                url = str(btn.get("url") or "").strip()
                if url:
                    i_row.append(InlineKeyboardButton(text=text, url=url))
                    continue
            i_row.append(
                InlineKeyboardButton(
                    text=text,
                    callback_data=token_by_action(callback_text),
                )
            )
        if i_row:
            inline_rows.append(i_row)

    if inline_rows:
        return InlineKeyboardMarkup(inline_keyboard=inline_rows)
    return None


def _media_relpath(state: dict[str, Any]) -> str:
    media = state.get("media")
    if isinstance(media, str):
        return media.replace("\\", "/").strip()
    if isinstance(media, dict):
        relpath = str(media.get("relpath") or media.get("path") or "")
        return relpath.replace("\\", "/").strip()
    return ""


async def send_state(
    msg: Message,
    state: dict[str, Any],
    *,
    media_dir: Path,
    token_by_action: Callable[[str], str],
) -> Message | None:
    markup = build_markup(state, token_by_action)
    html_text = str(state.get("text_html") or "")
    plain_text = str(state.get("text") or "")

    relpath = _media_relpath(state)
    if not relpath:
        return await _send_text(msg, html_text, plain_text, markup)

    relpath_path = Path(relpath)
    media_path = relpath_path if relpath_path.is_absolute() else media_dir / relpath_path.name
    if not media_path.exists():
        return await _send_text(msg, html_text, plain_text, markup)

    ext = media_path.suffix.lower()
    caption_html = html_text if html_text else None
    caption_plain = plain_text if plain_text else None

    try:
        file = FSInputFile(str(media_path))
        if ext in IMAGE_EXTENSIONS:
            return await msg.answer_photo(file, caption=caption_html, reply_markup=markup)
        elif ext in VIDEO_EXTENSIONS:
            return await msg.answer_video(file, caption=caption_html, reply_markup=markup)
        else:
            return await msg.answer_document(file, caption=caption_html, reply_markup=markup)
    except Exception:
        file = FSInputFile(str(media_path))
        if ext in IMAGE_EXTENSIONS:
            return await msg.answer_photo(
                file,
                caption=caption_plain,
                reply_markup=markup,
                parse_mode=None,
            )
        elif ext in VIDEO_EXTENSIONS:
            return await msg.answer_video(
                file,
                caption=caption_plain,
                reply_markup=markup,
                parse_mode=None,
            )
        else:
            return await msg.answer_document(
                file,
                caption=caption_plain,
                reply_markup=markup,
                parse_mode=None,
            )


async def _send_text(
    msg: Message,
    html_text: str,
    plain_text: str,
    markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None,
) -> Message | None:
    payload_html = html_text or plain_text
    payload_plain = plain_text or html_text
    if not payload_html and not payload_plain:
        return None
    try:
        return await msg.answer(payload_html, reply_markup=markup)
    except Exception:
        return await msg.answer(payload_plain, reply_markup=markup, parse_mode=None)


async def edit_state(
    bot: Bot,
    chat_id: int,
    message_id: int,
    state: dict[str, Any],
    *,
    media_dir: Path,
    token_by_action: Callable[[str], str],
) -> bool:
    """Try to edit an existing message to show the new state.

    Returns True if edit succeeded, False if caller should fall back to delete+send.
    """
    markup = build_markup(state, token_by_action)
    inline_markup = markup if isinstance(markup, InlineKeyboardMarkup) else None
    html_text = str(state.get("text_html") or "")
    plain_text = str(state.get("text") or "")
    has_media = bool(_media_relpath(state))

    if has_media:
        return False

    payload = html_text or plain_text
    if not payload:
        return False

    try:
        await bot.edit_message_text(
            text=payload,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=inline_markup,
        )
        return True
    except Exception:
        try:
            await bot.edit_message_text(
                text=plain_text or html_text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=inline_markup,
                parse_mode=None,
            )
            return True
        except Exception:
            return False
