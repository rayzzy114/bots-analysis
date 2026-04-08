from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .rates import RateService
from .storage import SettingsStore


@dataclass
class AppContext:
    settings: SettingsStore
    rates: RateService
    admin_ids: set[int]
    env_path: Path
    on_links_updated: Callable[[], object] | None = None

    def is_admin(self, user_id: int) -> bool:
        if not self.admin_ids:
            # Private/self-host mode: if ADMIN_IDS is empty, allow access for setup.
            return True
        return user_id in self.admin_ids

    def notify_links_updated(self) -> None:
        if self.on_links_updated is not None:
            self.on_links_updated()
