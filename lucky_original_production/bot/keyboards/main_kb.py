from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def _normalize_tg_url(value: str, fallback: str) -> str:

    if not value:

        return fallback

    v = value.strip()

    if not v:

        return fallback

    if v.startswith("http://") or v.startswith("https://"):

        return v

    if v.startswith("@"):

        return f"https://t.me/{v[1:]}"

    if v.startswith("t.me/") or v.startswith("telegram.me/"):

        return f"https://{v}"

    if "://" not in v and "/" not in v:

        return f"https://t.me/{v}"

    return fallback


def get_main_reply_kb() -> ReplyKeyboardMarkup:

    builder = ReplyKeyboardBuilder()

    builder.row(KeyboardButton(text="☘️ Главное меню"))

    return builder.as_markup(resize_keyboard=True)


def get_main_inline_kb(links: dict = None) -> InlineKeyboardMarkup:

    if links is None:

        links = {}


    url_reviews = _normalize_tg_url(

        links.get("link_reviews"),

        "https://t.me/luckyExchange_feedbacks",

    )

    url_news = _normalize_tg_url(

        links.get("link_news"),

        "https://t.me/luckyexchangenews",

    )

    url_support = _normalize_tg_url(

        links.get("link_support"),

        "https://t.me/luckyexchangesupport",

    )


    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="💎 Купить 💎", callback_data="buy_main"))

    builder.row(InlineKeyboardButton(text="💸 Продать 💸", callback_data="sell_main"))

    builder.row(InlineKeyboardButton(text="♻️ Чистка криптовалют ♻️", callback_data="clean_main"))

    builder.row(InlineKeyboardButton(text="Профиль", callback_data="profile_main"), InlineKeyboardButton(text="Мои заказы", callback_data="orders_main"))

    builder.row(InlineKeyboardButton(text="О сервисе", callback_data="about_main"), InlineKeyboardButton(text="Правила", callback_data="rules_main"))

    builder.row(InlineKeyboardButton(text="Настройки", callback_data="settings_main"))

    builder.row(InlineKeyboardButton(text="Отзывы ↗️", url=url_reviews), InlineKeyboardButton(text="Новости ↗️", url=url_news))

    builder.row(InlineKeyboardButton(text="🛠 Поддержка 24/7 ↗️", url=url_support))

    return builder.as_markup()



get_main_kb = get_main_inline_kb


def get_buy_methods_kb() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    methods = [

        ("Карта", "method_CARD"), ("СБП", "method_SBP"),

        ("СБП Трансгран", "method_SBP_TG"), ("Сим-карта", "method_SIM"),

        ("Альфа-Альфа", "method_ALFA"), ("Газпром-Газпром", "method_GZP"),

        ("Втб-Втб", "method_VTB"), ("НСПК", "method_NSPK"),

        ("QR Альфа-Альфа", "method_QR_ALFA"), ("QR Газпром-Газпром", "method_QR_GZP"),

        ("Сбер-Сбер", "method_SBER")

    ]

    for i in range(0, len(methods), 2):

        row = [InlineKeyboardButton(text=methods[i][0], callback_data=methods[i][1])]

        if i + 1 < len(methods):
            row.append(InlineKeyboardButton(text=methods[i+1][0], callback_data=methods[i+1][1]))

        builder.row(*row)

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    return builder.as_markup()


def get_amount_type_kb() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="В рублях (к отправке)", callback_data="amt_rub"))

    builder.row(InlineKeyboardButton(text="В токенах (к получению)", callback_data="amt_token"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    return builder.as_markup()


def get_currencies_kb(action: str) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    currencies = ["BTC", "USDT", "LTC", "ETH", "TRX"]

    prefix = "Купить" if action == "buy" else "Продать"

    for i in range(0, len(currencies), 2):

        row = [InlineKeyboardButton(text=f"{prefix} {currencies[i]}", callback_data=f"{action}_{currencies[i]}")]

        if i + 1 < len(currencies):
            row.append(InlineKeyboardButton(text=f"{prefix} {currencies[i+1]}", callback_data=f"{action}_{currencies[i+1]}"))

        builder.row(*row)

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    return builder.as_markup()


def get_profile_kb() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    builder.row(

        InlineKeyboardButton(text="💰 Пополнить бал...", callback_data="deposit"),

        InlineKeyboardButton(text="Вывести баланс", callback_data="withdraw")

    )

    builder.row(InlineKeyboardButton(text="Включить Merchant Mode", callback_data="merchant_mode"))

    builder.row(InlineKeyboardButton(text="🎟 Мои промокоды", callback_data="promocodes"))

    builder.row(InlineKeyboardButton(text="О реферальной системе", callback_data="referral_info"))

    builder.row(

        InlineKeyboardButton(text="🇬🇧 Eng", callback_data="lang_en"),

        InlineKeyboardButton(text="🇷🇺 Ru", callback_data="lang_ru")

    )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    return builder.as_markup()


def get_error_retry_kb() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    builder.row(

        InlineKeyboardButton(text="♻️ Попробовать снова", callback_data="buy_main"),

        InlineKeyboardButton(text="📝 Изменить сумму", callback_data="amt_rub")

    )

    builder.row(InlineKeyboardButton(text="Главное меню", callback_data="back_to_main"))

    return builder.as_markup()

