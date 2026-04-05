COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "BTC", "binance": "BTCRUB"},
    "ltc": {"symbol": "LTC", "title": "LTC", "binance": "LTCUSDT"},
    "xmr": {"symbol": "XMR", "title": "XMR", "binance": "XMRUSDT"},
    "usdt": {"symbol": "USDT", "title": "USDT", "binance": "USDTRUB"},
}

DEFAULT_LINKS = {
    "faq": "https://t.me/mnIn_news",
    "channel": "https://t.me/bitmafia_channel",
    "chat": "https://t.me/mnln_24",
    "reviews": "https://t.me/bmfeed",
    "review_form": "https://t.me/mnln_24",
    "manager": "https://t.me/MNLN_24",
    "operator": "https://t.me/mnln_24",
    "terms": "https://t.me/mnIn_news",
    "exchange": "https://t.me/MixMafiaBot",
}

LINK_LABELS = {
    "faq": "Все о крипте",
    "channel": "Канал",
    "reviews": "Отзывы",
    "operator": "Поддержка",
    "exchange": "Миксер BTC",
}

FALLBACK_RATES = {
    "btc": 7_100_000.0,
    "ltc": 11_000.0,
    "xmr": 20_000.0,
    "usdt": 105.0,
}

DEFAULT_PAYMENT_METHODS = [
    "Перевод на карту",
    "Тинькофф",
    "Сбербанк",
    "Карта",
    "СБП",
    "Сбербанк QR",
    "Тинькофф QR",
    "Наличные",
]

SELL_WALLET_LABELS = {
    "btc": "BTC",
    "ltc": "LTC",
    "usdt_trc20": "USDT (TRC20)",
    "usdt_bsc": "USDT (BSC)",
    "eth": "ETH / EVM",
    "trx": "TRX",
    "xmr": "XMR",
    "ton": "TON",
}

DEFAULT_SELL_WALLETS = {
    key: ""
    for key in SELL_WALLET_LABELS
}
