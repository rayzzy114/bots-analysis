"""Сборка клавиатур.

Тип строго по таблице clone_spec §2:
- reply (нижняя панель): меню, валюта, адрес, кошельки, подтверждения, реквизиты.
- inline (под сообщением): сервис/ссылки и статус-сообщения обмена.
- inline-кейпад: калькулятор (редактируется на месте).
"""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from .storage import SettingsStore

# --- Тексты кнопок (дословно из записи) -------------------------------------
BTN_START = "⚡️ нaчaть пользоваться!"
BTN_NEW_EXCHANGE = "новый 💱 обмен"
BTN_ACCOUNT = "👤 мой аккаунт"
BTN_HELP = "справочник ❔"
BTN_BACK = "⬅️ назад"
BTN_BACK2 = "❌ нет, назад"
BTN_HOME = "🏠 на главную"
BTN_BONUS_HISTORY = "📖 история бонусов"
BTN_SAVED_WALLETS = "📁 сохраненные кошельки (адреса)"
BTN_ADD = "➕ добавить"
BTN_DELETE = "➖ удалить"
BTN_RENAME = "🖋 переименовать"
BTN_SKIP = "➡️ пропустить"
BTN_YES = "✔️ да"
BTN_NO = "❌ нет"
BTN_YES2 = "✅ да"
BTN_NO_OTHER = "💱 нет нужной"
BTN_START_EXCHANGE = "➡️ начать"
BTN_REMEMBER_ADDR = "✔️ запомнить этот адрес"
BTN_FORGET_ADDR = "➖ не запоминать этот адрес"
BTN_CHECK_PAYMENT = "✔️ проверить оплату"
BTN_CANCEL_EXCHANGE = "❌ отменить обмен"
BTN_NEW_EXCHANGE2 = "➕ новый обмен"
BTN_RECENT = "📁 недавние обмены"

# Кнопки выбора монеты (обмен / кошельки)
# Справочник / FAQ (дословно из flow.json)
BTN_FAQ_ABOUT = "👾 обо мне"
BTN_FAQ_SPEED = "❔скорость обмена"
BTN_FAQ_WALLET_ERR = "❔ошибка в кошельке"
BTN_FAQ_REF = "❔реферальная система"
BTN_FAQ_RELIABILITY = "❔надежность сервиса"
BTN_FAQ_PRIVACY = "❔приватность"
BTN_HOME_ARROW = "⬅️ на главную"
FAQ_QUESTION_BTNS = {
    BTN_FAQ_ABOUT, BTN_FAQ_SPEED, BTN_FAQ_WALLET_ERR,
    BTN_FAQ_REF, BTN_FAQ_RELIABILITY, BTN_FAQ_PRIVACY,
}

COIN_BTN = {"btc": "🔸 BTC", "ltc": "🔹 LTC", "xmr": "Ⓜ️ XMR", "usdt": "💲 USDT"}
COIN_WALLET_BTN = {
    "btc": "🔸 BTC адреса", "ltc": "🔹 LTC адреса",
    "xmr": "Ⓜ️ XMR адреса", "usdt": "💲 USDT адреса",
}

REMOVE = ReplyKeyboardRemove()


def _reply(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
    )


# === Reply-клавиатуры =======================================================
def kb_start() -> ReplyKeyboardMarkup:
    return _reply([[BTN_START]])


def kb_main_menu() -> ReplyKeyboardMarkup:
    return _reply([[BTN_NEW_EXCHANGE], [BTN_ACCOUNT, BTN_HELP]])


def kb_account() -> ReplyKeyboardMarkup:
    return _reply([[BTN_BONUS_HISTORY], [BTN_SAVED_WALLETS], [BTN_BACK]])


def kb_back_home() -> ReplyKeyboardMarkup:
    return _reply([[BTN_BACK], [BTN_HOME]])


def kb_wallets_choose_coin() -> ReplyKeyboardMarkup:
    return _reply([
        [COIN_WALLET_BTN["btc"], COIN_WALLET_BTN["ltc"]],
        [COIN_WALLET_BTN["xmr"], COIN_WALLET_BTN["usdt"]],
        [BTN_BACK],
        [BTN_HOME],
    ])


def kb_wallets_list() -> ReplyKeyboardMarkup:
    return _reply([[BTN_ADD, BTN_DELETE], [BTN_RENAME], [BTN_BACK], [BTN_HOME]])


def kb_back() -> ReplyKeyboardMarkup:
    return _reply([[BTN_BACK]])


def kb_skip() -> ReplyKeyboardMarkup:
    return _reply([[BTN_SKIP]])


def kb_wallet_delete(count: int) -> ReplyKeyboardMarkup:
    from .renderer import ID_EMOJI

    rows = [[ID_EMOJI[i]] for i in range(min(count, len(ID_EMOJI)))]
    rows.append([BTN_BACK])
    return _reply(rows)


def kb_yes_no() -> ReplyKeyboardMarkup:
    return _reply([[BTN_YES, BTN_NO]])


def kb_cancel_confirm() -> ReplyKeyboardMarkup:
    return _reply([[BTN_YES2, BTN_BACK2]])


def kb_choose_coin() -> ReplyKeyboardMarkup:
    return _reply([
        [COIN_BTN["btc"], COIN_BTN["ltc"]],
        [COIN_BTN["xmr"], COIN_BTN["usdt"]],
        [BTN_NO_OTHER],
        [BTN_BACK],
    ])


def kb_address_valid() -> ReplyKeyboardMarkup:
    return _reply([[BTN_START_EXCHANGE], [BTN_REMEMBER_ADDR], [BTN_BACK]])


def kb_address_remembered() -> ReplyKeyboardMarkup:
    return _reply([[BTN_START_EXCHANGE], [BTN_FORGET_ADDR], [BTN_BACK]])


def kb_payment() -> ReplyKeyboardMarkup:
    return _reply([[BTN_CHECK_PAYMENT], [BTN_CANCEL_EXCHANGE]])


def kb_payment_checking() -> ReplyKeyboardMarkup:
    return _reply([[BTN_CANCEL_EXCHANGE], [BTN_NEW_EXCHANGE2, BTN_RECENT]])


# === Inline-клавиатуры (ссылки/статусы) =====================================
def kb_operator(settings: SettingsStore, label: str = "👨‍💻 Оператор") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, url=settings.operator_url)]
    ])


def kb_site(settings: SettingsStore) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 САЙТ", url=settings.site_url)]
    ])


def kb_help_links(settings: SettingsStore) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Поддержка 24/7 🌐", url=settings.operator_url)],
        [
            InlineKeyboardButton(text="⭐️ отзывы", url=settings.reviews_url),
            InlineKeyboardButton(text="розыгрыши 🎁", url=settings.giveaways_url),
        ],
    ])


def kb_help_panel(settings: SettingsStore) -> InlineKeyboardMarkup:
    """Инлайн-панель справочника: Оператор / Чат | Новости."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💻 Оператор", url=settings.operator_url)],
        [
            InlineKeyboardButton(text="💬 Чат", url=settings.chat_url),
            InlineKeyboardButton(text="📢 Новости", url=settings.news_url),
        ],
    ])


def kb_faq() -> ReplyKeyboardMarkup:
    """Нижняя FAQ-клавиатура справочника."""
    return _reply([
        [BTN_FAQ_ABOUT],
        [BTN_FAQ_SPEED, BTN_FAQ_WALLET_ERR],
        [BTN_FAQ_REF, BTN_FAQ_RELIABILITY],
        [BTN_HOME_ARROW, BTN_FAQ_PRIVACY],
    ])


# === Калькулятор (inline-кейпад, edit на месте) =============================
# callback-data схема clone_spec §6.
def _ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def kb_calc_default(coin: str, min_label: str, burn_active: bool) -> InlineKeyboardMarkup:
    """Дефолтный (новый) калькулятор: сумма вводится сообщением."""
    burn = "😌 сохранить монеты 🪙" if burn_active else "🪙 списать монеты: 50"
    rows = [[_ib("🧮 старый калькулятор 📟", "calc:old")]]
    if coin == "usdt":
        rows.append([_ib("🇷🇺 Ввод суммы в RUB", "calc:unit")])
    rows.append([_ib(f"🤏🏽 МИН ОБМЕН : {min_label} RUB", "calc:min")])
    rows.append([_ib(burn, "calc:burn")])
    rows.append([_ib(BTN_BACK, "calc:nav_back"), _ib("готово ➡️", "calc:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_calc_pad(coin: str) -> InlineKeyboardMarkup:
    """Старый калькулятор: цифровой кейпад (fffb274e)."""
    from . import constants as const

    emoji = const.COINS[coin]["emoji"]
    ticker = const.COINS[coin]["ticker"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [_ib("7", "calc:digit:7"), _ib("8", "calc:digit:8"), _ib("9", "calc:digit:9")],
        [_ib("4", "calc:digit:4"), _ib("5", "calc:digit:5"), _ib("6", "calc:digit:6")],
        [_ib("1", "calc:digit:1"), _ib("2", "calc:digit:2"), _ib("3", "calc:digit:3")],
        [_ib("0", "calc:digit:0"), _ib(",", "calc:dot"), _ib("<x", "calc:back")],
        [_ib(f"{emoji} Ввод в {ticker}", "calc:unit"), _ib("🤏🏽 МИН ОБМЕН", "calc:min")],
        [_ib("🪙 списать монеты", "calc:burn")],
        [_ib(BTN_BACK, "calc:nav_back"), _ib("готово ➡️", "calc:done")],
    ])
