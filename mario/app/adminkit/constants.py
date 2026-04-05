COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "BTC", "binance": "BTCRUB"},
    "ltc": {"symbol": "LTC", "title": "LTC", "binance": "LTCUSDT"},
    "xmr": {"symbol": "XMR", "title": "XMR", "binance": "XMRUSDT"},
    "usdt": {"symbol": "USDT", "title": "USDT", "binance": "USDTRUB"},
}

CRYPTO_WALLET_COINS = ["BTC", "LTC", "XMR", "USDT", "TRX", "ETH", "SOL"]

DEFAULT_LINKS = {
    "faq": "https://t.me/mnIn_news",
    "channel": "https://t.me/mnIn_news",
    "chat": "https://t.me/mnln_24",
    "reviews": "https://t.me/mnIn_news",
    "review_form": "https://t.me/mnln_24",
    "manager": "https://t.me/MNLN_24",
    "operator": "https://t.me/mnln_24",
    "terms": "https://t.me/mnIn_news",
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
    "trx": 11.0,
    "eth": 310_000.0,
    "sol": 10_500.0,
}

DEFAULT_PAYMENT_METHODS = [
    "Перевод на карту",
    "СБП",
]
