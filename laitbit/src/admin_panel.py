from pathlib import Path

from dotenv import dotenv_values, load_dotenv

from src.admin_kit.constants import DEFAULT_LINKS
from src.admin_kit.context import AppContext
from src.admin_kit.handlers.admin import build_admin_router
from src.admin_kit.rates import RateService
from src.admin_kit.storage import OrdersStore, SettingsStore, UsersStore
from src.admin_kit.utils import parse_admin_ids
from src.cfg import ADMIN_CHAT_IDS

_ADMIN_CONTEXT: AppContext | None = None


def _commission_from_env(env: dict[str, str | None]) -> float:
    raw = (env.get("DEFAULT_COMMISSION_PERCENT") or "").strip()
    if not raw:
        return 5.0
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return 5.0
    if value < 0 or value > 50:
        return 5.0
    return value


def build_admin_context(base_dir: Path) -> AppContext:
    env_path = base_dir / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    env = dotenv_values(env_path)

    admin_ids = parse_admin_ids((env.get("ADMIN_IDS") or "").strip()) or set(ADMIN_CHAT_IDS)

    env_links: dict[str, str] = {}
    for link_key, fallback in DEFAULT_LINKS.items():
        env_key = f"{link_key.upper()}_LINK"
        env_links[link_key] = (env.get(env_key) or "").strip() or fallback

    data_dir = base_dir / "data"
    settings = SettingsStore(
        path=data_dir / "admin_settings.json",
        default_commission=_commission_from_env(env),
        env_links=env_links,
    )
    users = UsersStore(path=data_dir / "admin_users.json")
    orders = OrdersStore(path=data_dir / "admin_orders.json")
    rates = RateService()
    return AppContext(
        settings=settings,
        users=users,
        orders=orders,
        rates=rates,
        admin_ids=admin_ids,
        env_path=env_path,
    )


def build_admin_components(base_dir: Path):
    global _ADMIN_CONTEXT
    ctx = build_admin_context(base_dir)
    _ADMIN_CONTEXT = ctx
    return ctx, build_admin_router(ctx)


def get_admin_context() -> AppContext | None:
    return _ADMIN_CONTEXT
