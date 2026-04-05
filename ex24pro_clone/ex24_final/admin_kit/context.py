from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import LinkDefinition
from .rates import RateService
from .storage import OrdersStore, SettingsStore, UsersStore


@dataclass
class AppContext:
    settings: SettingsStore
    rates: RateService
    admin_ids: set[int]
    env_path: Path
    link_definitions: tuple[LinkDefinition, ...]
    sell_wallet_labels: dict[str, str]
    users: UsersStore | None = None
    orders: OrdersStore | None = None

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids
