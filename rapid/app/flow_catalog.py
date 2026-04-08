from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

logger = logging.getLogger(__name__)


class CapturedFlow:
    def __init__(
        self,
        path: Path,
        supports_inline_queries: bool = False,
        url_resolver: Callable[[str, str], str] | None = None,
    ):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid flow format: {path}")
        self._supports_inline_queries = supports_inline_queries
        self._url_resolver = url_resolver
        self._states: dict[str, dict[str, Any]] = {
            str(key): value for key, value in raw.items() if isinstance(value, dict)
        }
        self._action_to_id: dict[str, str] = {}
        self._id_to_action: dict[str, str] = {}
        self._bootstrap_actions()

    def _bootstrap_actions(self) -> None:
        for state in self._states.values():
            for row in self._rows_for_state(state):
                for btn in row:
                    text = str(btn.get("text") or "").strip()
                    if text:
                        self._register_action(text)

    def _register_action(self, text: str) -> str:
        existing = self._action_to_id.get(text)
        if existing is not None:
            return existing
        base = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
        key = base
        idx = 1
        while key in self._id_to_action and self._id_to_action[key] != text:
            idx += 1
            key = f"{base[:8]}{idx:02d}"
        self._action_to_id[text] = key
        self._id_to_action[key] = text
        return key

    def callback_data(self, text: str) -> str:
        return f"a:{self._register_action(text)}"

    def action_from_callback(self, callback_data: str | None) -> str | None:
        if not callback_data or not callback_data.startswith("a:"):
            return None
        return self._id_to_action.get(callback_data[2:])

    def state(self, state_id: str) -> dict[str, Any]:
        return self._states[state_id]

    def text(self, state_id: str) -> str:
        return str(self.state(state_id).get("text") or "")

    def text_links(self, state_id: str) -> list[str]:
        raw_links = self.state(state_id).get("text_links")
        if not isinstance(raw_links, list):
            return []
        links: list[str] = []
        for item in raw_links:
            if isinstance(item, str) and item.strip():
                links.append(item.strip())
        return links

    def media_name(self, state_id: str) -> str | None:
        media = self.state(state_id).get("media")
        if not isinstance(media, str) or not media.strip():
            return None
        # Captured paths may come from Windows clients (e.g. "media\\file.jpg").
        # Normalize separators so basename extraction works on POSIX too.
        return Path(media.replace("\\", "/")).name

    def media_file(self, state_id: str, assets_dir: Path) -> Path | None:
        name = self.media_name(state_id)
        if not name:
            return None
        path = assets_dir / name
        if path.exists():
            return path
        return None

    def reply_keyboard(self, state_id: str) -> ReplyKeyboardMarkup | None:
        state = self.state(state_id)
        rows = self._rows_for_state(state)
        if not rows:
            return None
        button_types = {str(btn.get("type") or "") for row in rows for btn in row}
        if button_types != {"KeyboardButton"}:
            return None
        keyboard = [
            [KeyboardButton(text=str(btn.get("text") or "")) for btn in row]
            for row in rows
        ]
        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )

    def inline_keyboard(self, state_id: str) -> InlineKeyboardMarkup | None:
        state = self.state(state_id)
        rows = self._rows_for_state(state)
        if not rows:
            return None
        inline_rows: list[list[InlineKeyboardButton]] = []
        for row in rows:
            inline_row: list[InlineKeyboardButton] = []
            for btn in row:
                text = str(btn.get("text") or "")
                if not text:
                    continue
                url = btn.get("url")
                if isinstance(url, str) and url.strip():
                    resolved_url = url
                    if self._url_resolver is not None:
                        try:
                            candidate = str(self._url_resolver(text, url) or "").strip()
                        except Exception:
                            logger.warning(
                                "Failed to resolve runtime URL for button %r with source URL %r",
                                text,
                                url,
                                exc_info=True,
                            )
                            candidate = ""
                        if candidate:
                            resolved_url = candidate
                    inline_row.append(InlineKeyboardButton(text=text, url=resolved_url))
                elif (
                    str(btn.get("type") or "") == "KeyboardButtonSwitchInline"
                    and "Рассчитать стоимость" in text
                    and self._supports_inline_queries
                ):
                    inline_row.append(
                        InlineKeyboardButton(
                            text=text,
                            switch_inline_query_current_chat=self._calc_query_for_state(state),
                        )
                    )
                else:
                    inline_row.append(
                        InlineKeyboardButton(text=text, callback_data=self.callback_data(text))
                    )
            if inline_row:
                inline_rows.append(inline_row)
        if not inline_rows:
            return None
        return InlineKeyboardMarkup(inline_keyboard=inline_rows)

    def _calc_query_for_state(self, state: dict[str, Any]) -> str:
        text = str(state.get("text") or "")
        match = re.search(r"Валюта:\s*([A-Z0-9]+)", text)
        if match:
            return match.group(1)
        return ""

    def _rows_for_state(self, state: dict[str, Any]) -> list[list[dict[str, Any]]]:
        rows = state.get("button_rows")
        if not isinstance(rows, list):
            return []
        parsed: list[list[dict[str, Any]]] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            parsed_row: list[dict[str, Any]] = [btn for btn in row if isinstance(btn, dict)]
            if parsed_row:
                parsed.append(parsed_row)
        return parsed
