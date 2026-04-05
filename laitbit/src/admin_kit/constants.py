import os

from dotenv import load_dotenv

load_dotenv()


def _get_link(key: str, default: str) -> str:
    return os.getenv(f"{key.upper()}_LINK", default)


COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "BTC", "binance": "BTCRUB"},
    "ltc": {"symbol": "LTC", "title": "LTC", "binance": "LTCUSDT"},
    "xmr": {"symbol": "XMR", "title": "XMR", "binance": "XMRUSDT"},
    "usdt": {"symbol": "USDT", "title": "USDT", "binance": "USDTRUB"},
}

DEFAULT_LINKS = {
    "faq": _get_link("faq", "https://t.me/LITEBITBIT_CHANNEL"),
    "channel": _get_link("channel", "https://t.me/LITEBITBIT_CHANNEL"),
    "chat": _get_link("chat", "https://t.me/LITEBITBIT_CHANNEL"),
    "reviews": _get_link("reviews", "https://t.me/lit_otxov"),
    "review_form": _get_link("review_form", "https://t.me/lit_otxov"),
    "manager": _get_link("manager", "https://t.me/Litebit_2"),
    "operator": _get_link("operator", "https://t.me/Litebit_2"),
    "terms": _get_link("terms", "https://t.me/LITEBITBIT_CHANNEL"),
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

DEFAULT_PAYMENT_METHODS = [
    "Перевод на карту",
    "СБП",
]
