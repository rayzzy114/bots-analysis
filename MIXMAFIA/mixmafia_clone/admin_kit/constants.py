from __future__ import annotations

COINS: dict[str, dict[str, str]] = {
    "btc": {"symbol": "BTC", "title": "BTC (чистый)", "coingecko": "bitcoin"},
    "eth": {"symbol": "ETH", "title": "Ethereum", "coingecko": "ethereum"},
    "ltc": {"symbol": "LTC", "title": "Litecoin", "coingecko": "litecoin"},
    "xmr": {"symbol": "XMR", "title": "Monero", "coingecko": "monero"},
    "usdt": {"symbol": "USDT", "title": "Tether", "coingecko": "tether"},
}

FALLBACK_RATES: dict[str, float] = {
    "btc": 97_000.0,
    "eth": 3_500.0,
    "ltc": 110.0,
    "xmr": 170.0,
    "usdt": 1.0,
}
