from __future__ import annotations
import os

# Output currencies (what users receive after mixing dirty BTC)
COINS: dict[str, dict[str, str]] = {
    "btc_clean":  {"symbol": "BTC",  "title": "BTC (чистый)", "coingecko": "bitcoin"},
    "eth":        {"symbol": "ETH",  "title": "Ethereum",     "coingecko": "ethereum"},
    "usdt_erc20": {"symbol": "USDT", "title": "USDT ERC-20",  "coingecko": "tether"},
    "usdt_trc20": {"symbol": "USDT", "title": "USDT TRC-20",  "coingecko": "tether"},
    "usdt_bep20": {"symbol": "USDT", "title": "USDT BEP-20",  "coingecko": "tether"},
    "ltc":        {"symbol": "LTC",  "title": "Litecoin",     "coingecko": "litecoin"},
    "xmr":        {"symbol": "XMR",  "title": "Monero",       "coingecko": "monero"},
}

# Receive wallets: BTC deposit address per output currency shown in orders
# Key names are used as admin_kit sell_wallet_labels keys
SELL_WALLET_LABELS: dict[str, str] = {
    "btc_clean":  "BTC (чистый)",
    "eth":        "Ethereum",
    "usdt_erc20": "USDT ERC-20",
    "usdt_trc20": "USDT TRC-20",
    "usdt_bep20": "USDT BEP-20",
    "ltc":        "Litecoin",
    "xmr":        "Monero",
}

DEFAULT_RECEIVE_WALLETS: dict[str, str] = {key: "" for key in SELL_WALLET_LABELS}

# URL buttons shown in the bot (manageable from admin panel)
DEFAULT_LINKS: dict[str, str] = {
    "channel":  os.getenv("CHANNEL_LINK", "https://t.me/+WV8DeR3IFcswYjRi"),
    "support":  os.getenv("SUPPORT_LINK", "https://t.me/BitMafia_support"),
    "reviews":  os.getenv("REVIEWS_LINK", "https://t.me/+Nq1-DPuYxl00MzMy"),
    "faq":      os.getenv("FAQ_LINK", "https://t.me/+9-b_IupCYGlhNmYy"),
    "exchange": os.getenv("EXCHANGE_LINK", "https://t.me/bitmafia_bot"),
    "other":    os.getenv("OTHER_LINK", "https://t.me/BitMafia_support"),
    "operator": os.getenv("OPERATOR_LINK", "https://t.me/BitMafia_support"),
}

LINK_LABELS: dict[str, str] = {
    "channel":  "Канал",
    "support":  "Поддержка",
    "reviews":  "Канал с отзывами",
    "faq":      "Все о крипте",
    "exchange": "Перейти в обменник",
    "other":    "Нужно другое направление?",
}

FALLBACK_RATES: dict[str, float] = {
    "btc": 97_000.0,
    "eth": 3_500.0,
    "ltc": 110.0,
    "xmr": 170.0,
    "usdt": 1.0,
}

DEFAULT_COMMISSION: float = 2.0
PARTNER_MIN_WITHDRAW_BTC: str = "0.0001"
HISTORY_PAGE_SIZE: int = 5
