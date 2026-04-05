COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "Bitcoin", "coingecko": "bitcoin"},
    "ltc": {"symbol": "LTC", "title": "Litecoin", "coingecko": "litecoin"},
    "xmr": {"symbol": "XMR", "title": "Monero", "coingecko": "monero"},
    "usdt": {"symbol": "USDT", "title": "Tether", "coingecko": "tether"},
    "trx": {"symbol": "TRX", "title": "Tron", "coingecko": "tron"},
    "eth": {"symbol": "ETH", "title": "Ethereum", "coingecko": "ethereum"},
}

BUY_BUTTON_TO_COIN = {
    "🔄 Купить BTC": "btc",
    "🔄 Купить LTC": "ltc",
    "🔄 Купить XMR": "xmr",
    "🔄 Купить USDT-TRC20": "usdt",
    "🔄 Купить TRX": "trx",
    "🔄 Купить ETH": "eth",
}

SELL_BUTTON_TO_COIN = {
    "Продать BTC": "btc",
    "Продать LTC": "ltc",
    "Продать XMR": "xmr",
    "Продать USDT": "usdt",
    "Продать TRX": "trx",
    "Продать ETH": "eth",
}

DEFAULT_LINKS = {
    "faq": "https://t.me/bit_magnit_channel/221",
    "channel": "https://t.me/bit_magnit_channel/221",
    "chat": "https://t.me/bit_magnit_channel/221",
    "reviews": "https://t.me/bit_magnit_channel/221",
    "review_form": "https://t.me/bit_magnit_channel/221",
    "manager": "https://t.me/bitmagnit_support",
    "operator": "https://t.me/bitmagnit_support",
    "terms": "https://t.me/bit_magnit_channel/221",
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
    "usdt": 100.0,
    "trx": 10.0,
    "eth": 250_000.0,
}

DEFAULT_PAYMENT_METHODS = [
    "Номер карты (2211 руб.)",
    "Номер телефона (2211 руб.)",
    "АЛЬФА - АЛЬФА (2211 руб.)",
    "Сим-карта (2211 руб.)",
    "СБП(оплата по ссылке) (2061 руб.)",
    "QR - code (2211 руб.)",
    "БТ (2211 руб.)",
]

SELL_BTC_ADDRESS_DEFAULT = "bc1q0s04allqymxq9p0zraa5wup0c24qjuckfvfxdx"
