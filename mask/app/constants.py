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
    "support_ticket": os.getenv("SUPPORT_TICKET_LINK", "https://t.me/mask24_bot"),
    "terms": os.getenv("TERMS_LINK", "https://t.me/mnIn_news"),
    "wallet_help": os.getenv("WALLET_HELP_LINK", "https://telegra.ph/CHto-takoe-koshelek-07-26"),
    "user_agreement": os.getenv("USER_AGREEMENT_LINK", "https://telegra.ph/Testvamvam-07-22"),
    "getting_started": os.getenv("GETTING_STARTED_LINK", "https://telegra.ph/Nachalo-raboty-09-12"),
    "withdrawal_help": os.getenv("WITHDRAWAL_HELP_LINK", "https://telegra.ph/Vyvod-sredstv-09-12"),
    "pax_code_help": os.getenv("PAX_CODE_HELP_LINK", "https://telegra.ph/PAX-CODE--CHto-ehto-09-12"),
    "exchange_btc_help": os.getenv("EXCHANGE_BTC_HELP_LINK", "https://telegra.ph/Kak-obmenyat-Bitcoin-BTC-09-12"),
    "exchange_ltc_help": os.getenv("EXCHANGE_LTC_HELP_LINK", "https://telegra.ph/Kak-obmenyat-Litecoin-LTC-09-12"),
    "exchange_usdt_help": os.getenv("EXCHANGE_USDT_HELP_LINK", "https://telegra.ph/Kak-obmenyat-Tether-USDT-11-10"),
    "exchange_xmr_help": os.getenv("EXCHANGE_XMR_HELP_LINK", "https://telegra.ph/Kak-obmenyat-Monero-XMR-11-10"),
    "promo_help": os.getenv("PROMO_HELP_LINK", "https://telegra.ph/Kak-aktivirovat-promokod-09-12"),
    "offer": os.getenv("OFFER_LINK", "https://telegra.ph/Offer-The-MASK-07-26"),
    "finance": os.getenv("FINANCE_LINK", "https://telegra.ph/Finansy-07-26"),
    "charity_details": os.getenv("CHARITY_DETAILS_LINK", "https://telegra.ph/MASK-prisoedinilsya-k-pomoshchi-detyam-s-DCP-v-lechenii-i-reabilitacii-01-18"),
    "reports": os.getenv("REPORTS_LINK", "https://t.me/smart_rf"),
    "support_wallet": os.getenv("SUPPORT_WALLET_LINK", "https://t.me/mask24_bot"),
}

LINK_LABELS = {
    "faq": "FAQ",
    "channel": "Канал",
    "chat": "Чат",
    "reviews": "Отзывы",
    "review_form": "Оставить отзыв",
    "manager": "Менеджер",
    "operator": "Оператор",
    "support_ticket": "Тикет",
    "terms": "Условия",
    "wallet_help": "Кошелек",
    "user_agreement": "Соглашение",
    "getting_started": "Начало",
    "withdrawal_help": "Вывод",
    "pax_code_help": "PAX-CODE",
    "exchange_btc_help": "Обмен BTC",
    "exchange_ltc_help": "Обмен LTC",
    "exchange_usdt_help": "Обмен USDT",
    "exchange_xmr_help": "Обмен XMR",
    "promo_help": "Промокод",
    "offer": "Оффер",
    "finance": "Финансы",
    "charity_details": "Подробнее",
    "reports": "Отчеты",
    "support_wallet": "Support Wallet",
}

FALLBACK_RATES = {
    "btc": 7_100_000.0,
    "eth": 180_000.0,
    "ltc": 11_000.0,
    "xmr": 20_000.0,
    "trx": 12.0,
    "ton": 520.0,
    "usdt": 105.0,
}

DEFAULT_PAYMENT_METHODS = [
    "Перевод на карту",
    "СБП",
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

PAYMENT_PROOF_PROMPT = "📸 <b>Прикрепите фото успешной оплаты. После отправки фото будет отправлено администратору.</b>"
PAYMENT_PROOF_NEED_PHOTO = "Прикрепите именно фото успешной оплаты (чек/скрин)."
PAYMENT_PROOF_SENT = "✅ <b>Фото получено. Заявка передана администратору.</b>"
PAYMENT_PROOF_STORED = "✅ Фото получено. Админы пока не настроены, заявка сохранена локально."
