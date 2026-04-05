COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "BTC (Bitcoin)", "coingecko": "bitcoin"},
    "ltc": {"symbol": "LTC", "title": "LTC (Litecoin)", "coingecko": "litecoin"},
    "eth": {"symbol": "ETH", "title": "ETH (ERC 20)", "coingecko": "ethereum"},
    "sol": {"symbol": "SOL", "title": "SOL (Solana)", "coingecko": "solana"},
    "usdt": {"symbol": "USDT", "title": "USDT (TRC 20)", "coingecko": "tether"},
}

DEFAULT_LINKS = {
    "faq": "https://telegra.ph/Instrukciya-po-vzaimodejstviyu-s-avtomaticheskim-botom---obmennikom-servisa-RAPID-EXCHANGE-05-02",
    "channel": "https://t.me/RAPID_EX_CHANNEL",
    "chat": "https://t.me/RAPID_EX_CHAT",
    "reviews": "https://t.me/RAPID_EX_REVIEWS",
    "review_form": "https://t.me/RAPID_EX_Admin",
    "manager": "https://t.me/RAPID_EX_Manager",
    "operator": "https://t.me/RAPID_EX_Operator",
    "terms": "https://telegra.ph/Polzovatelskoe-soglashenie-servisa-Rapid-Exchange-08-21",
}

LINK_LABELS = {
    "faq": "FAQ",
    "channel": "Канал",
    "chat": "Чат",
    "reviews": "Отзывы",
    "review_form": "Отзыв-форма",
    "manager": "Менеджер",
    "operator": "Оператор",
    "terms": "Условия",
}

LINK_RESOLUTION_RULES: dict[str, dict[str, tuple[str, ...]]] = {
    "faq": {
        "text_contains": ("инструк",),
        "source_urls": (DEFAULT_LINKS["faq"],),
    },
    "channel": {
        "text_contains": ("канал",),
        "source_urls": (DEFAULT_LINKS["channel"],),
    },
    "chat": {
        "text_contains": ("чат",),
        "source_urls": (DEFAULT_LINKS["chat"],),
    },
    "reviews": {
        "text_contains": ("отзыв",),
        "source_urls": (DEFAULT_LINKS["reviews"],),
    },
    "review_form": {
        "text_contains": ("чат-админ", "админ чат", "админский чат", "чат для админ"),
        "source_urls": (DEFAULT_LINKS["review_form"],),
    },
    "manager": {
        "text_contains": ("менеджер",),
        "source_urls": (DEFAULT_LINKS["manager"],),
    },
    "operator": {
        "text_contains": ("оператор",),
        "source_urls": (DEFAULT_LINKS["operator"],),
    },
    "terms": {
        "text_contains": ("услов",),
        "source_urls": (DEFAULT_LINKS["terms"],),
    },
}

FALLBACK_RATES = {
    "btc": 5_150_000.0,
    "ltc": 4_100.0,
    "eth": 150_000.0,
    "sol": 6_450.0,
    "usdt": 104.0,
}

DEFAULT_PAYMENT_METHODS = [
    "💳 Карта",
    "СБП 📱",
    "❌ QR код",
    "❌ QR (Альфа-Альфа)",
    "🏦 Внутрибанк. перевод 🏦",
    "❌ Моб. связь (СИМ)",
    "💱 Трансграничный перевод 💱",
]
