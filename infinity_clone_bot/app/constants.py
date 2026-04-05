from typing import Any

COINS: dict[str, dict[str, Any]] = {
    "btc": {"id": "bitcoin", "title": "Bitcoin (BTC)", "symbol": "BTC"},
    "ltc": {"id": "litecoin", "title": "Litecoin (LTC)", "symbol": "LTC"},
    "usdt": {"id": "tether", "title": "Tether (USDT)", "symbol": "USDT"},
}

ASSETS = {
    "main": "main.jpg",
    "buy_coin": "buy_coin.jpg",
    "buy_method": "buy_method.jpg",
    "buy_amount": "buy_amount.jpg",
    "wallet": "wallet.jpg",
    "buy_requisites": "photo_2025-06-29_14-52-57.jpg",
    "sell": "sell.jpg",
    "contacts": "contacts.jpg",
    "module": "module.jpg",
    "history": "history.jpg",
    "promo": "promo.jpg",
    "cashback": "cashback.jpg",
}

DEFAULT_LINKS = {
    "faq": "https://telegra.ph/Nachalo-raboty-06-18",
    "channel": "https://t.me/infinity_ex_channel",
    "chat": "https://t.me/+nzNlzzrwBUQ4YjRi",
    "reviews": "https://t.me/infinity_ex_comment",
    "review_form": "https://t.me/Infinity_exchange_bot?start=D9LmdsU0mc",
    "manager": "https://t.me/manager_Infinity",
    "operator": "https://t.me/operator_Infinity",
    "terms": "https://telegra.ph/Polzovatelskoe-soglashenie-The-Infinity-Exchange-12-25",
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

FALLBACK_RATES = {"btc": 5_400_000.0, "ltc": 9_000.0, "usdt": 100.0}
