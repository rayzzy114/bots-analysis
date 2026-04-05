from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aiogram.types import (
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)


class StateRenderer:
    def __init__(self, media_dir: Path, cache_path: Path | None = None):
        self.media_dir = media_dir
        self.cache_path = cache_path
        self._file_id_cache: dict[str, str] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if self.cache_path is None or not self.cache_path.exists():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return
        loaded: dict[str, str] = {}
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, str) and key and value:
                loaded[key] = value
        self._file_id_cache = loaded

    def _save_cache(self) -> None:
        if self.cache_path is None:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self._file_id_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            return

    def _build_markup(
        self,
        state: dict[str, Any],
        action_to_callback: Callable[[str], str],
    ) -> InlineKeyboardMarkup | ReplyKeyboardMarkup | None:
        rows = state.get("button_rows") or []
        if not isinstance(rows, list) or not rows:
            return None

        button_types = {
            str(btn.get("type") or "")
            for row in rows
            if isinstance(row, list)
            for btn in row
            if isinstance(btn, dict) and str(btn.get("text") or "").strip()
        }
        if button_types == {"KeyboardButton"}:
            keyboard_rows: list[list[KeyboardButton]] = []
            for row in rows:
                if not isinstance(row, list):
                    continue
                rendered_row: list[KeyboardButton] = []
                for btn in row:
                    if not isinstance(btn, dict):
                        continue
                    text = str(btn.get("text") or "").strip()
                    if text:
                        rendered_row.append(KeyboardButton(text=text))
                if rendered_row:
                    keyboard_rows.append(rendered_row)
            if keyboard_rows:
                return ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True)
            return None

        inline_rows: list[list[InlineKeyboardButton]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            rendered_row: list[InlineKeyboardButton] = []
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                text = str(btn.get("text") or "").strip()
                if not text:
                    continue
                btn_type = str(btn.get("type") or "")
                url = str(btn.get("url") or "").strip()
                if btn_type == "KeyboardButtonUrl" and url:
                    rendered_row.append(InlineKeyboardButton(text=text, url=url))
                    continue
                rendered_row.append(
                    InlineKeyboardButton(
                        text=text,
                        callback_data=action_to_callback(text),
                    )
                )
            if rendered_row:
                inline_rows.append(rendered_row)

        if inline_rows:
            return InlineKeyboardMarkup(inline_keyboard=inline_rows)
        return None

    async def send_state(
        self,
        msg: Message,
        state: dict[str, Any],
        *,
        action_to_callback: Callable[[str], str],
        text_override: str | None = None,
        text_override_plain: str | None = None,
        include_markup: bool = True,
    ) -> None:
        markup = self._build_markup(state, action_to_callback) if include_markup else None
        html_text = text_override if text_override is not None else str(state.get("text_html") or "")
        plain_text = (
            text_override_plain
            if text_override_plain is not None
            else (text_override if text_override is not None else str(state.get("text") or ""))
        )
        media_file = str(state.get("media_file") or "")
        media_exists = bool(state.get("media_exists"))

        if not media_exists or not media_file:
            await self._send_text(msg, html_text, plain_text, markup)
            return

        media_path = self.media_dir / media_file
        if not media_path.exists():
            await self._send_text(msg, html_text, plain_text, markup)
            return

        ext = media_path.suffix.lower()
        caption_html = html_text.strip() if html_text.strip() else None
        caption_plain = plain_text.strip() if plain_text.strip() else None
        caption_source = caption_html or caption_plain or ""
        caption_too_long = len(caption_source) > 1000

        # Telegram media captions have strict limits. If text is long, send media first,
        # then send text as a separate message with markup.
        send_text_after_media = caption_too_long and bool(caption_source)
        media_markup = None if send_text_after_media else markup

        cached_file_id = self._file_id_cache.get(media_file)
        if cached_file_id:
            try:
                if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                    await msg.answer_photo(
                        cached_file_id,
                        caption=None if send_text_after_media else caption_html,
                        reply_markup=media_markup,
                    )
                elif ext in {".mp4", ".mov", ".m4v"}:
                    await msg.answer_video(
                        cached_file_id,
                        caption=None if send_text_after_media else caption_html,
                        reply_markup=media_markup,
                    )
                else:
                    await msg.answer_document(
                        cached_file_id,
                        caption=None if send_text_after_media else caption_html,
                        reply_markup=media_markup,
                    )
                if send_text_after_media:
                    await self._send_text(msg, html_text, plain_text, markup)
                return
            except Exception:
                self._file_id_cache.pop(media_file, None)
                self._save_cache()

        try:
            file = FSInputFile(str(media_path))
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                sent = await msg.answer_photo(
                    file,
                    caption=None if send_text_after_media else caption_html,
                    reply_markup=media_markup,
                )
            elif ext in {".mp4", ".mov", ".m4v"}:
                sent = await msg.answer_video(
                    file,
                    caption=None if send_text_after_media else caption_html,
                    reply_markup=media_markup,
                )
            else:
                sent = await msg.answer_document(
                    file,
                    caption=None if send_text_after_media else caption_html,
                    reply_markup=media_markup,
                )
            self._cache_file_id(media_file, sent)
            if send_text_after_media:
                await self._send_text(msg, html_text, plain_text, markup)
            return
        except Exception:
            file = FSInputFile(str(media_path))
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                sent = await msg.answer_photo(
                    file,
                    caption=None if send_text_after_media else caption_plain,
                    reply_markup=media_markup,
                    parse_mode=None,
                )
            elif ext in {".mp4", ".mov", ".m4v"}:
                sent = await msg.answer_video(
                    file,
                    caption=None if send_text_after_media else caption_plain,
                    reply_markup=media_markup,
                    parse_mode=None,
                )
            else:
                sent = await msg.answer_document(
                    file,
                    caption=None if send_text_after_media else caption_plain,
                    reply_markup=media_markup,
                    parse_mode=None,
                )
            self._cache_file_id(media_file, sent)
            if send_text_after_media:
                await self._send_text(msg, html_text, plain_text, markup)

    async def _send_text(
        self,
        msg: Message,
        html_text: str,
        plain_text: str,
        markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | None,
    ) -> None:
        if not html_text and not plain_text:
            return
        try:
            await msg.answer(html_text or plain_text, reply_markup=markup)
        except Exception:
            await msg.answer(plain_text or html_text, reply_markup=markup, parse_mode=None)

    def _cache_file_id(self, media_file: str, sent_message: Message) -> None:
        if not media_file or not sent_message:
            return
        if sent_message.video and sent_message.video.file_id:
            file_id = sent_message.video.file_id
            if self._file_id_cache.get(media_file) != file_id:
                self._file_id_cache[media_file] = file_id
                self._save_cache()
            return
        if sent_message.photo:
            file_id = sent_message.photo[-1].file_id
            if self._file_id_cache.get(media_file) != file_id:
                self._file_id_cache[media_file] = file_id
                self._save_cache()
            return
        if sent_message.document and sent_message.document.file_id:
            file_id = sent_message.document.file_id
            if self._file_id_cache.get(media_file) != file_id:
                self._file_id_cache[media_file] = file_id
                self._save_cache()
