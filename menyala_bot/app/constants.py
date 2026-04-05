import os

COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "BTC", "binance": "BTCRUB"},
    "ltc": {"symbol": "LTC", "title": "LTC", "binance": "LTCUSDT"},
    "xmr": {"symbol": "XMR", "title": "XMR", "binance": "XMRUSDT"},
    "usdt": {"symbol": "USDT", "title": "USDT", "binance": "USDTRUB"},
}

DEFAULT_LINKS = {
    "faq": os.getenv("FAQ_LINK", "https://t.me/mnIn_news"),
    "channel": os.getenv("CHANNEL_LINK", "https://t.me/mnIn_news"),
    "chat": os.getenv("CHAT_LINK", "https://t.me/mnln_24"),
    "reviews": os.getenv("REVIEWS_LINK", "https://t.me/mnIn_news"),
    "review_form": os.getenv("REVIEW_FORM_LINK", "https://t.me/mnln_24"),
    "manager": os.getenv("MANAGER_LINK", "https://t.me/MNLN_24"),
    "operator": os.getenv("OPERATOR_LINK", "https://t.me/mnln_24"),
    "terms": os.getenv("TERMS_LINK", "https://t.me/mnIn_news"),
}

LINK_LABELS = {
    "faq": "FAQ",
    "channel": "Канал",
    "chat": "Чат",
    "reviews": "Отзывы",
    "review_form": "Оставить отзыв",
    "manager": "Менеджер",
    "operator": "Оператор",
    "terms": "Условия",
}

FALLBACK_RATES = {
    "btc": 7_100_000.0,
    "ltc": 11_000.0,
    "xmr": 20_000.0,
    "usdt": 105.0,
}

DEFAULT_PAYMENT_METHODS = [
    "Перевод на карту",
    "СБП",
]
