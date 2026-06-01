"""JSON-хранилища с атомарной записью.

SettingsStore — единый источник правды админ-значений (ссылки, %, минимумы).
Геттеры читают live из self._data, set() пишет через атомарную запись, поэтому
правки админа применяются сразу, без рестарта бота.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from . import constants as const


# --- helpers ----------------------------------------------------------------
def _read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# --- SettingsStore ----------------------------------------------------------
class SettingsStore:
    """Админ-настройки поверх settings.json."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else const.SETTINGS_PATH
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        stored = _read_json(self.path, {})
        if not isinstance(stored, dict):
            stored = {}
        merged: dict[str, Any] = {}
        changed = False
        for key, default in const.DEFAULT_SETTINGS.items():
            if key in stored:
                merged[key] = stored[key]
            else:
                # копируем вложенные структуры, чтобы не делить ссылку с DEFAULT
                merged[key] = json.loads(json.dumps(default))
                changed = True
        self._data = merged
        if changed or not self.path.exists():
            _atomic_write(self.path, self._data)

    # generic access ---------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def all(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._data))

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = value
            _atomic_write(self.path, self._data)

    async def set_min_rub(self, coin: str, value: float) -> None:
        async with self._lock:
            mins = dict(self._data.get("min_rub_by_coin", {}))
            mins[coin] = value
            self._data["min_rub_by_coin"] = mins
            _atomic_write(self.path, self._data)

    # typed convenience properties ------------------------------------------
    @property
    def operator_url(self) -> str:
        return str(self._data["operator_url"])

    @property
    def chat_url(self) -> str:
        return str(self._data["chat_url"])

    @property
    def news_url(self) -> str:
        return str(self._data["news_url"])

    @property
    def reviews_url(self) -> str:
        return str(self._data["reviews_url"])

    @property
    def giveaways_url(self) -> str:
        return str(self._data["giveaways_url"])

    @property
    def site_url(self) -> str:
        return str(self._data["site_url"])

    @property
    def ref_link_base(self) -> str:
        return str(self._data["ref_link_base"])

    @property
    def commission_percent(self) -> float:
        return float(self._data["commission_percent"])

    @property
    def cashback_percent(self) -> float:
        return float(self._data["cashback_percent"])

    @property
    def start_bonus(self) -> int:
        return int(self._data["start_bonus"])

    @property
    def requisites(self) -> str:
        return str(self._data["requisites"])

    @property
    def bank(self) -> str:
        return str(self._data["bank"])

    def min_rub(self, coin: str) -> float:
        mins = self._data.get("min_rub_by_coin", {})
        return float(mins.get(coin, 1500))

    def ref_link(self, user_id: int | str) -> str:
        return self.ref_link_base.format(user_id=user_id)


# --- Простые key→value JSON-хранилища пользовательских данных ---------------
class _JsonDict:
    """База для users/orders: словарь, сохраняемый атомарно."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()
        loaded = _read_json(path, {})
        self._data: dict[str, Any] = loaded if isinstance(loaded, dict) else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    async def put(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = value
            _atomic_write(self.path, self._data)


class UsersStore(_JsonDict):
    """Зарегистрированные пользователи: {user_id: {registered, bonus, ...}}."""

    def is_registered(self, user_id: int) -> bool:
        return str(user_id) in self._data

    async def register(self, user_id: int, start_bonus: int) -> bool:
        """Возвращает True, если это первая регистрация (новый юзер)."""
        if self.is_registered(user_id):
            return False
        await self.put(str(user_id), {"bonus_available": start_bonus, "bonus_used": 0, "invited": 0})
        return True


class OrdersStore(_JsonDict):
    """Заявки на обмен: {order_id: {...}}."""


class WalletsStore(_JsonDict):
    """Сохранённые адреса: {user_id: {coin: [{"address","label"}, ...]}}."""

    def list_for(self, user_id: int, coin: str) -> list[dict[str, str]]:
        return self._data.get(str(user_id), {}).get(coin, [])

    async def add(self, user_id: int, coin: str, address: str, label: str = "") -> None:
        async with self._lock:
            user = dict(self._data.get(str(user_id), {}))
            coins = dict(user)
            lst = list(coins.get(coin, []))
            lst.append({"address": address, "label": label})
            coins[coin] = lst
            self._data[str(user_id)] = coins
            _atomic_write(self.path, self._data)

    async def delete(self, user_id: int, coin: str, index: int) -> bool:
        async with self._lock:
            user = dict(self._data.get(str(user_id), {}))
            lst = list(user.get(coin, []))
            if not (0 <= index < len(lst)):
                return False
            lst.pop(index)
            user[coin] = lst
            self._data[str(user_id)] = user
            _atomic_write(self.path, self._data)
            return True
