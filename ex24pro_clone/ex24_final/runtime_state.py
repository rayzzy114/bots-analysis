from __future__ import annotations
import logging

from admin_kit import AdminKitConfig, LinkDefinition, build_admin_components

from config import ADMIN_IDS, ENV_PATH, PROJECT_DIR, RATE_SPREAD_PERCENT
from rates import ExchangeRateService

logger = logging.getLogger(__name__)

rate_service = ExchangeRateService(
    ttl_seconds=30,
    spread_percent=RATE_SPREAD_PERCENT,
)

config = AdminKitConfig(
    env_path=ENV_PATH,
    data_dir=PROJECT_DIR / "data" / "admin",
    link_definitions=[
        LinkDefinition(key="support", label="Доп. способы связи", default="https://ex24qr.com"),
        LinkDefinition(key="offices", label="Офисы", default="https://exchange24.pro/#offices"),
        LinkDefinition(key="reviews", label="Отзывы", default="https://ex24qr.com/reviews"),
        LinkDefinition(key="tickets", label="Мероприятия", default="https://ex24.tickets/"),
    ],
    admin_ids=ADMIN_IDS,
    sell_wallet_labels={},
    enable_orders=False,
    enable_users=True,
)

app_context, admin_router = build_admin_components(config, rates=rate_service)
rate_service.set_settings(app_context.settings)
