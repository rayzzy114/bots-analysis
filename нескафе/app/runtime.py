"""AppContext — единый контейнер зависимостей, прокидывается в хендлеры."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .rates import RateService
from .storage import OrdersStore, SettingsStore, UsersStore, WalletsStore


def parse_admin_ids(raw: str | None) -> set[int]:
    out: set[int] = set()
    for tok in (raw or "").replace(";", ",").split(","):
        tok = tok.strip()
        if tok.isdigit():
            out.add(int(tok))
    return out


@dataclass
class AppContext:
    settings: SettingsStore
    rates: RateService
    users: UsersStore
    orders: OrdersStore
    wallets: WalletsStore
    admin_ids: set[int] = field(default_factory=set)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    @classmethod
    def from_env(cls) -> "AppContext":
        return cls(
            settings=SettingsStore(),
            rates=RateService(),
            users=UsersStore(_path("USERS")),
            orders=OrdersStore(_path("ORDERS")),
            wallets=WalletsStore(_path("WALLETS")),
            admin_ids=parse_admin_ids(os.environ.get("ADMIN_IDS")),
        )


def _path(name: str):
    from . import constants as const

    return getattr(const, f"{name}_PATH")
