from __future__ import annotations

COINS: dict[str, dict[str, str]] = {
    "rub_thb": {"symbol": "RUB/THB", "title": "Рубль → Бат"},
    "usdt_thb": {"symbol": "USDT/THB", "title": "Tether → Бат"},
    "usdt_cny": {"symbol": "USDT/CNY", "title": "Tether → Юань"},
    "rub_cny": {"symbol": "RUB/CNY", "title": "Рубль → Юань"},
    "usdt_aed": {"symbol": "USDT/AED", "title": "Tether → Дирхам"},
    "rub_aed": {"symbol": "RUB/AED", "title": "Рубль → Дирхам"},
    "usdt_idr": {"symbol": "USDT/IDR", "title": "Tether → Рупия"},
    "rub_idr": {"symbol": "RUB/IDR", "title": "Рубль → Рупия"},
}

FALLBACK_RATES: dict[str, float] = {
    "usdt_rub": 86.5,
    "usdt_thb": 33.2,
    "usdt_cny": 7.1,
    "usdt_aed": 3.67,
    "usdt_idr": 16300.0,
    "rub_thb": 2.60,
    "rub_cny": 12.18,
    "rub_aed": 23.57,
    "rub_idr": 188.0,
}
