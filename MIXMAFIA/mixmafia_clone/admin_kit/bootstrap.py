from __future__ import annotations

from pathlib import Path

import httpx
from dotenv import dotenv_values, load_dotenv

from .config import AdminKitConfig
from .context import AppContext
from .handlers.admin import build_admin_router
from .rates import RateService
from .runtime import apply_runtime_from_env
from .storage import OrdersStore, SettingsStore, UsersStore


def build_admin_context(config: AdminKitConfig, *, rates: RateService | None = None, client: httpx.AsyncClient | None = None) -> AppContext:
    env_path = Path(config.env_path)
    load_dotenv(dotenv_path=env_path, override=False)
    env = dotenv_values(env_path)

    settings = SettingsStore(
        path=Path(config.data_dir) / "admin_settings.json",
        default_commission=config.default_commission,
        link_definitions=tuple(config.link_definitions),
        sell_wallet_labels=dict(config.sell_wallet_labels),
    )
    users = UsersStore(Path(config.data_dir) / "admin_users.json") if config.enable_users else None
    orders = OrdersStore(Path(config.data_dir) / "admin_orders.json") if config.enable_orders else None
    ctx = AppContext(
        settings=settings,
        users=users,
        orders=orders,
        rates=rates or RateService(client=client),
        admin_ids=set(config.admin_ids),
        env_path=env_path,
        link_definitions=tuple(config.link_definitions),
        sell_wallet_labels=dict(config.sell_wallet_labels),
    )
    apply_runtime_from_env(ctx, env)
    return ctx


def build_admin_components(config: AdminKitConfig, *, rates: RateService | None = None, client: httpx.AsyncClient | None = None):
    ctx = build_admin_context(config, rates=rates, client=client)
    return ctx, build_admin_router(ctx)
