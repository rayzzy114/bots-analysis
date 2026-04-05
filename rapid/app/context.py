from dataclasses import dataclass
from pathlib import Path

from .rates import RateService
from .storage import OrdersStore, SettingsStore, UsersStore


@dataclass
class AppContext:
    settings: SettingsStore
    users: UsersStore
    orders: OrdersStore
    rates: RateService
    admin_ids: set[int]
    env_path: Path

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids
