"""Константы и значения по умолчанию.

ВАЖНО: всё, что может меняться админом, живёт в settings.json и читается через
SettingsStore. Здесь только дефолты (значения оригинала @NeskafeEx_bot) и
неизменяемые структуры (список монет, точки отправки стикеров).
"""

from __future__ import annotations

from pathlib import Path

# --- Пути -------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
ADMIN_DIR = DATA_DIR / "admin"
ASSETS_DIR = ROOT_DIR / "assets"
STICKERS_DIR = ASSETS_DIR / "stickers"
MEDIA_DIR = ASSETS_DIR / "media"

SETTINGS_PATH = ADMIN_DIR / "settings.json"
USERS_PATH = ADMIN_DIR / "users.json"
ORDERS_PATH = ADMIN_DIR / "orders.json"
WALLETS_PATH = ADMIN_DIR / "wallets.json"

# --- Монеты -----------------------------------------------------------------
# Порядок и тикеры как в оригинале. coingecko_id — для RateService.
COINS: dict[str, dict[str, str]] = {
    "btc": {"ticker": "BTC", "emoji": "🔸", "coingecko_id": "bitcoin"},
    "ltc": {"ticker": "LTC", "emoji": "🔹", "coingecko_id": "litecoin"},
    "xmr": {"ticker": "XMR", "emoji": "Ⓜ", "coingecko_id": "monero"},
    "usdt": {"ticker": "USDT", "emoji": "💲", "coingecko_id": "tether"},
}
COIN_KEYS = tuple(COINS.keys())

# --- Значения по умолчанию (оригинал, заменяемы админом) --------------------
# Источник: clone_spec.md §3. Все подставляются в тексты динамически.
DEFAULT_SETTINGS: dict[str, object] = {
    "operator_url": "https://t.me/ExchangeNeskafeExmoLTC",
    "chat_url": "https://t.me/+4gnTdye4_jRkNmNi",
    "news_url": "https://t.me/Neskafe_Exchange",
    "reviews_url": "https://t.me/Neskafe_Exchange",
    "giveaways_url": "https://t.me/+4gnTdye4_jRkNmNi",
    "site_url": "https://nesk.bot/",
    "ref_link_base": "https://nesk.bot/go?ref={user_id}",
    "commission_percent": 5.0,   # комиссия сервиса: уменьшает сумму к получению
    "cashback_percent": 0.5,     # кэшбэк на бонусный счёт
    "start_bonus": 50,
    "min_rub_by_coin": {"btc": 795, "ltc": 728, "usdt": 48670, "xmr": 54000},
    # Реквизиты для экрана «К оплате» (правятся в /admin → 💳 Реквизиты)
    "requisites": "0000 0000 0000 0000",
    "bank": "Сбербанк",
}

# Человекочитаемые лейблы полей — ТОЛЬКО для админ-панели (не для юзер-текстов).
SETTING_LABELS: dict[str, str] = {
    "operator_url": "👨‍💻 Оператор / Поддержка",
    "chat_url": "💬 Чат",
    "news_url": "📢 Новости",
    "reviews_url": "⭐️ Отзывы",
    "giveaways_url": "🎁 Розыгрыши",
    "site_url": "🌐 Сайт",
    "ref_link_base": "🔗 Реф-ссылка (база)",
    "commission_percent": "🏦 Комиссия, %",
    "cashback_percent": "💸 Кэшбэк, %",
    "start_bonus": "🎉 Стартовый бонус, ₽",
    "requisites": "💳 Реквизиты (номер)",
    "bank": "🏦 Банк",
}

# Ссылочные поля (правятся в разделе «Ссылки / контакты»).
LINK_KEYS = (
    "operator_url", "chat_url", "news_url", "reviews_url",
    "giveaways_url", "site_url", "ref_link_base",
)
# Числовые поля (правятся в разделе «Настройки»).
NUMERIC_KEYS = ("commission_percent", "cashback_percent", "start_bonus")
# Текстовые реквизиты для экрана «К оплате» (правятся в разделе «Реквизиты»).
REQUISITE_KEYS = ("requisites", "bank")

# --- Стикеры: точки отправки (clone_spec.md §5), эмодзи → момент -------------
STICKER_START_NEW = "😌"      # первый /start (новый юзер, «Начислено 50₽»)
STICKER_START_KNOWN = "❔"     # /start уже зарегистрированного (перед help)
STICKER_WALLET_CHECK = "💻"    # после ввода адреса, с «Проверка кошелька...»
STICKER_PAYMENT_CHECK = "🏃‍♂️"  # после «проверить оплату», с «Проверка оплаты...»
