"""Доступ к стикерам/медиа из assets/.

Стикеры шлются отдельным сообщением в 4 точках (clone_spec §5). Сопоставление
эмодзи→файл берём из assets/stickers/index.json, нормализуя вариационные
селекторы (U+FE0F), т.к. в индексе они опущены.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from aiogram.types import FSInputFile

from . import constants as const

_VS16 = "️"
_ZWJ = "‍"


def _norm(emoji: str) -> str:
    return emoji.replace(_VS16, "")


@lru_cache(maxsize=1)
def _index() -> dict[str, Path]:
    idx_path = const.STICKERS_DIR / "index.json"
    data = json.loads(idx_path.read_text("utf-8"))
    out: dict[str, Path] = {}
    for s in data["stickers"]:
        file = const.STICKERS_DIR / Path(s["file"]).name
        for emoji in s["emoji"]:
            out[_norm(emoji)] = file
    return out


def sticker(emoji: str) -> FSInputFile | None:
    """FSInputFile стикера по эмодзи (или None, если не найден)."""
    path = _index().get(_norm(emoji))
    if path is None or not path.exists():
        return None
    return FSInputFile(path)


# Фото «Вы уже есть в системе» (MessageMediaPhoto экрана 8ddd73a61f).
SYSTEM_PHOTO = const.MEDIA_DIR / "photo_6107149655184445175.jpg"

# Онбординг-«документы» с кнопками (MessageMediaDocument). В записи это анимации;
# из media/ им соответствуют два video_*.mp4. Точное сопоставление — косметика.
SAVE_SITE_DOC = const.MEDIA_DIR / "video_5382101656957631959.mp4"
HELP_LINKS_DOC = const.MEDIA_DIR / "video_5357196511702712269.mp4"


def _file(path: Path) -> FSInputFile | None:
    return FSInputFile(path) if path.exists() else None


def system_photo() -> FSInputFile | None:
    return _file(SYSTEM_PHOTO)


def save_site_doc() -> FSInputFile | None:
    return _file(SAVE_SITE_DOC)


def help_links_doc() -> FSInputFile | None:
    return _file(HELP_LINKS_DOC)
