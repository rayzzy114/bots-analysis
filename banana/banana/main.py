import os
import sys
import asyncio
import logging
import random
from pathlib import Path

import aiohttp

# Fix: add parent directory to path so `utils` module can be found
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile , InlineKeyboardMarkup , InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime
from aiogram import F


from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH, override=True)

from utils.env_writer import update_env_var, read_env_var


def _get_env(key, default=""):
    val = os.getenv(key)
    return val if val is not None else default

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
DB = os.getenv("DB")
SUPPORT_TEXT = os.getenv("SUPPORT_TEXT")
logging.basicConfig(level=logging.INFO)

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_COINS = {
    "BTC": "bitcoin",
    "LTC": "litecoin",
    "USDT": "tether",
    "XMR": "monero",
}
RATE_REFRESH_SECONDS = 300

buy_rates = {coin: 0.0 for coin in COINGECKO_COINS}
sell_rates = {coin: 0.0 for coin in COINGECKO_COINS}


async def fetch_crypto_rates_coingecko() -> dict[str, float] | None:
    try:
        async with aiohttp.ClientSession() as session:
            ids = ",".join(COINGECKO_COINS.values())
            url = f"{COINGECKO_URL}?ids={ids}&vs_currencies=rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    logging.warning("CoinGecko returned HTTP %s", response.status)
                    return None
                data = await response.json()
    except Exception:
        logging.exception("CoinGecko fetch failed")
        return None

    result: dict[str, float] = {}
    for coin, cg_id in COINGECKO_COINS.items():
        coin_data = data.get(cg_id) or {}
        try:
            rub_price = float(coin_data.get("rub", 0))
        except (TypeError, ValueError):
            continue
        if rub_price > 0:
            result[coin] = rub_price

    return result or None


def update_rates_from_coingecko(rates: dict[str, float]) -> None:
    for coin, rub_price in rates.items():
        buy_rates[coin] = rub_price
        sell_rates[coin] = rub_price
        formatted = f"{rub_price:.2f}"
        os.environ[f"BUY_RATES_{coin}"] = formatted
        os.environ[f"SELL_RATES_{coin}"] = formatted
        update_env_var(f"BUY_RATES_{coin}", formatted)
        update_env_var(f"SELL_RATES_{coin}", formatted)
    logging.info("CoinGecko rates updated: %s", ", ".join(sorted(rates)))


async def refresh_rates_task() -> None:
    while True:
        rates = await fetch_crypto_rates_coingecko()
        if rates:
            update_rates_from_coingecko(rates)
        await asyncio.sleep(RATE_REFRESH_SECONDS)

CHANNEL_URL = os.getenv("CHANNEL_URL")
REVIEWS_URL = os.getenv("REVIEWS_URL")
SECOND_OPERATOR_URL = os.getenv("SECOND_OPERATOR_URL")
BONUS_CHAT_URL = os.getenv("BONUS_CHAT_URL")
CHAT_ADMIN_URL = os.getenv("CHAT_ADMIN_URL")
ROULETTE_URL = os.getenv("ROULETTE_URL")
REF_BOT_URL = os.getenv("REF_BOT_URL")
COMMISSION_PERCENT = float(os.getenv("COMMISSION_PERCENT", 30))

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_amounts = {}


class SellStatesRF(StatesGroup):
    waiting_for_amount = State()
    waiting_for_promo = State()
    waiting_for_method = State()
    waiting_for_receipt = State()

class OrderStates(StatesGroup):
    entering_amount = State()
    choosing_payment_method = State()
    waiting_payment_confirm = State()
    waiting_receipt = State()


    # Инлайн‑кнопка Назад для РБ
back_inline_rb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="◀ Назад", callback_data="back_to_crypto_rb")]
    ]
)


@dp.callback_query(lambda c: c.data == "back")
async def process_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev_level = data.get("prev_level")

    if prev_level == "menu":
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb)
    elif prev_level == "country":
        await callback.message.edit_text("Выберите страну:", reply_markup=buy_country_kb)
    elif prev_level == "crypto":
        await callback.message.edit_text("Выберите криптовалюту:", reply_markup=crypto_kb)
    # можно расширять дальше под твои уровни

    await callback.answer()



# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🟢 Купить"),
            KeyboardButton(text="🟡 Продать")
        ],
        [
            KeyboardButton(text="☎️ Контакты"),
            KeyboardButton(text="🎲 Призовая игра")
        ],
        [
            KeyboardButton(text="👤 Личный кабинет")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Тексты
first_text = """🤑🍌BANAN_BTC_BOT — обмен криптовалют с выгодой и удобством

💱 Быстрые и простые операции — никаких сложностей, только эффективные сделки.
🎯 Программа лояльности — получайте бонусы за рекомендации друзей.
♻️ Автоматические скидки — выгодные предложения подбираются индивидуально.
📝 Вознаграждение за отзывы — делитесь мнением и зарабатывайте.
🎟️ Специальная скидка для новых пользователей — выгодный старт уже при первом обмене.
🔒 Безопасность и конфиденциальность — быстрые и надежные транзакции.

⚠️ Криптовалюты — высокорисковые активы. Цены могут резко меняться. Не инвестируйте средства, которые не готовы потерять. Сервис не является финансовым советником.
"""

second_text = """Твой обмен — твой шанс на бонус! После каждой сделки получи возможность забрать от 200 до 1000 рублей на карту или баланс бота!
🚸 Возникли вопросы? Решим мгновенно! Обратись к оператору 24/7, приложив:
✔️ Чек оплаты.
✔️ Скрин заявки.
✔️ Скриншоты процесса создания заявки.

Честность превыше всего! Мы не работаем с мошенниками, не принимаем ворованные или «грязные» деньги и криптовалюту. 

Выбери нужный раздел в меню👇
"""

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    # Отправляем картинку JPEG
    photo = FSInputFile("images/start.jpg") # файл должен лежать рядом с кодом
    await message.answer_photo(photo)

    # Первое сообщение
    await message.answer(first_text)

    # Ждём секунду
    await asyncio.sleep(1)

    # Второе сообщение с меню
    await message.answer(second_text, reply_markup=main_menu)


import sqlite3

# ==================== Инициализация таблиц ====================

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Таблица ссылок (рулетка, контакты и т.д.)
    c.execute("""
        CREATE TABLE IF NOT EXISTS links (
            name TEXT PRIMARY KEY,
            url TEXT
        )
    """)


    # Таблица адресов для криптовалют
    c.execute("""
    CREATE TABLE IF NOT EXISTS addresses (
        coin TEXT PRIMARY KEY,
        address TEXT
    )
    """)


    # Таблица банков (РФ)
    c.execute("""
    CREATE TABLE IF NOT EXISTS banks (
        method TEXT PRIMARY KEY,   -- 'card' или 'spb'
        requisites TEXT
    )
    """)


    # Таблица текста поддержки
    c.execute("""
        CREATE TABLE IF NOT EXISTS support_text (
            id INTEGER PRIMARY KEY,
            text TEXT
        )
    """)

    # Таблица комиссии
    c.execute("""
        CREATE TABLE IF NOT EXISTS commission (
            id INTEGER PRIMARY KEY,
            percent REAL
        )
    """)

    # Таблица заявок (покупка/продажа)
    c.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            deal_type TEXT,
            coin TEXT,
            amount REAL,
            requisites TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# ==================== LINKS ====================

def get_links():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT name, url FROM links")
    rows = c.fetchall()
    conn.close()
    return rows

def set_link(name: str, url: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO links (name, url) VALUES (?, ?)", (name, url))
    conn.commit()
    conn.close()

# ==================== BANKS ====================

def get_banks():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT method, requisites FROM banks")
    rows = c.fetchall()
    conn.close()
    return rows

def get_bank(method: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT requisites FROM banks WHERE method=?", (method,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_bank(method: str, requisites: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO banks (method, requisites) VALUES (?, ?)", (method, requisites))
    conn.commit()
    conn.close()

def delete_bank(method: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM banks WHERE method=?", (method,))
    conn.commit()
    conn.close()



# ==================== ADDRESSES ====================

def get_addresses():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT coin, address FROM addresses")
    rows = c.fetchall()
    conn.close()
    return rows

def get_address(coin: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT address FROM addresses WHERE coin=?", (coin.upper(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def set_address(coin: str, address: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO addresses (coin, address) VALUES (?, ?)", (coin.upper(), address))
    conn.commit()
    conn.close()

def delete_address(coin: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM addresses WHERE coin=?", (coin.upper(),))
    conn.commit()
    conn.close()


# ==================== SUPPORT TEXT ====================

def get_support_text():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT text FROM support_text WHERE id=1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else SUPPORT_TEXT

def set_support_text(text: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO support_text (id, text) VALUES (1, ?)", (text,))
    conn.commit()
    conn.close()

# ==================== COMMISSION ====================

def get_commission():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT percent FROM commission WHERE id=1")
    row = c.fetchone()
    conn.close()
    return float(row[0]) if row else COMMISSION_PERCENT

def set_commission(percent: float):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO commission (id, percent) VALUES (1, ?)", (percent,))
    conn.commit()
    conn.close()

# ==================== DEALS ====================

def add_deal(user_id: int, deal_type: str, coin: str, amount: float, requisites: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals (user_id, deal_type, coin, amount, requisites)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, deal_type, coin, amount, requisites))
    conn.commit()
    conn.close()

def get_deals(limit: int = 20):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, user_id, deal_type, coin, amount, requisites, status, created_at FROM deals ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def update_deal_status(deal_id: int, status: str):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE deals SET status=? WHERE id=?", (status, deal_id))
    conn.commit()
    conn.close()



#=======================================АДМИНКА=============================

class AdminStates(StatesGroup):
    waiting_bank_input = State()      # добавление / редактирование банков
    waiting_address   = State()       # смена адреса продажи
    waiting_support   = State()       # смена текста поддержки
    waiting_commission = State()      # смена комиссии
    waiting_link_field = State()      # смена конкретного поля ссылок



@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("⛔ Доступ запрещён")

    # Показываем кнопку входа
    await message.answer(
        "🔐 Админ-панель BANAN_BTC",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Открыть админку", callback_data="admin_panel")]
        ])
    )


    

def admin_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Реквизиты банков", callback_data="admin_banks")],
        [InlineKeyboardButton(text="Адреса для продажи", callback_data="admin_addresses")],
        [InlineKeyboardButton(text="Текст поддержки", callback_data="admin_support")],
        [InlineKeyboardButton(text="🔗 Ссылки", callback_data="admin_env_links")],
        [InlineKeyboardButton(text="Комиссия", callback_data="admin_commission")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
    ])


@dp.callback_query(lambda c: c.data == "admin_panel")
async def open_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    await callback.message.edit_text(
        "⚙️ Админ-панель BANAN_BTC\n\nВыберите раздел:",
        reply_markup=admin_main_menu()
    )


@dp.callback_query(lambda c: c.data == "admin_banks")
async def admin_banks_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    card = get_bank("card")
    spb = get_bank("spb")

    text = "📑 Реквизиты банков (РФ):\n\n"
    text += f"🇷🇺💳ЛЮБАЯ КАРТА РФ—НОМЕР КАРТЫ : {card if card else '— не задан'}\n"
    text += f"🇷🇺💳ЛЮБАЯ КАРТА РФ—СПБ: {spb if spb else '— не задан'}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить 🇷🇺💳ЛЮБАЯ КАРТА РФ—НОМЕР КАРТЫ", callback_data="bank_change_card")],
        [InlineKeyboardButton(text="Удалить 🇷🇺💳ЛЮБАЯ КАРТА РФ—НОМЕР КАРТЫ", callback_data="bank_delete_card")],
        [InlineKeyboardButton(text="Изменить 🇷🇺💳ЛЮБАЯ КАРТА РФ—СПБ", callback_data="bank_change_spb")],
        [InlineKeyboardButton(text="🇷🇺💳ЛЮБАЯ КАРТА РФ—СПБ", callback_data="bank_delete_spb")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)
    




@dp.callback_query(lambda c: c.data.startswith("bank_change_"))
async def bank_change_start(callback: types.CallbackQuery, state: FSMContext):
    method = callback.data.split("_")[2]  # card или spb
    await state.update_data(edit_method=method)
    await state.set_state(AdminStates.waiting_bank_input)
    await callback.message.edit_text(f"Пришли новые реквизиты для {method.upper()}:")

@dp.callback_query(lambda c: c.data.startswith("bank_delete_"))
async def bank_delete(callback: types.CallbackQuery):
    method = callback.data.split("_")[2]
    delete_bank(method)
    await callback.answer(f"✅ {method.upper()} удалён!")
    await admin_banks_menu(callback)

@dp.message(AdminStates.waiting_bank_input)
async def admin_set_bank(message: types.Message, state: FSMContext):
    data = await state.get_data()
    method = data.get("edit_method")
    set_bank(method, message.text.strip())
    await message.answer(f"✅ Реквизиты для {method.upper()} обновлены", reply_markup=admin_main_menu())
    await state.clear()



#==================================АДРЕСАА КРИПТА=============================
# --- меню выбора монеты ---
@dp.callback_query(lambda c: c.data == "admin_addresses")
async def admin_addresses_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="BTC", callback_data="addr_coin_BTC")],
        [InlineKeyboardButton(text="LTC", callback_data="addr_coin_LTC")],
        [InlineKeyboardButton(text="USDT", callback_data="addr_coin_USDT")],
        [InlineKeyboardButton(text="XMR", callback_data="addr_coin_XMR")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_panel")]
    ])

    await callback.message.edit_text("📌 Выберите монету для управления адресом:", reply_markup=kb)


# --- просмотр/управление адресом конкретной монеты ---
@dp.callback_query(lambda c: c.data.startswith("addr_coin_"))
async def addr_coin_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    coin = callback.data.split("_")[2]
    addresses = get_addresses()
    addr_dict = {c: a for c, a in addresses}
    current = addr_dict.get(coin)

    text = f"📌 Адрес для {coin}:\n\n"
    if current:
        text += f"{current}\n\n"
    else:
        text += "Пока нет сохранённого адреса.\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить / Добавить", callback_data=f"addr_change_{coin}")],
        [InlineKeyboardButton(text="Удалить", callback_data=f"addr_delete_{coin}")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_addresses")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


# --- редактирование адреса ---
@dp.callback_query(lambda c: c.data.startswith("addr_change_"))
async def addr_change_start(callback: types.CallbackQuery, state: FSMContext):
    coin = callback.data.split("_")[2]
    await state.update_data(edit_coin=coin)
    await state.set_state(AdminStates.waiting_address)
    await callback.message.edit_text(f"Пришли новый адрес для {coin}:")


# --- удаление адреса ---
@dp.callback_query(lambda c: c.data.startswith("addr_delete_"))
async def addr_delete(callback: types.CallbackQuery):
    coin = callback.data.split("_")[2]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM addresses WHERE coin=?", (coin,))
    conn.commit()
    conn.close()
    await callback.answer(f"✅ Адрес {coin} удалён!")
    await addr_coin_menu(callback)


# --- приём нового адреса ---
@dp.message(AdminStates.waiting_address)
async def save_address(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    coin = data.get("edit_coin")

    set_address(coin, message.text.strip())
    await message.answer(f"✅ Адрес для {coin} обновлён", reply_markup=admin_main_menu())
    await state.clear()








@dp.callback_query(lambda c: c.data == "admin_support")
async def admin_support(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Доступ запрещён", show_alert=True)

    current = get_support_text()
    await callback.message.edit_text(
        f"🆘 Текущий текст поддержки:\n\n{current}\n\nВведите новый текст:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="admin_panel")]
        ])
    )
    await state.set_state(AdminStates.waiting_support)




@dp.message(AdminStates.waiting_support)
async def admin_set_support(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    set_support_text(message.text.strip())
    await message.answer("✅ Текст поддержки обновлён", reply_markup=admin_main_menu())
    await state.clear()



# ==================== ENV LINKS ADMIN ====================

LINK_FIELDS = {
    "link_rates": "BUY_RATES_BTC",
    "link_sell_btc": "SELL_RATES_BTC",
    "link_news_channel": "NEWS_CHANNEL",
    "link_operator": "OPERATOR",
    "link_operator2": "OPERATOR2",
    "link_operator3": "OPERATOR3",
    "link_work_operator": "WORK_OPERATOR",
    "link_contact_support": "CONTACT_SUPPORT",
    "link_contact_news": "CONTACT_NEWS",
}


@dp.callback_query(lambda c: c.data == "admin_env_links")
async def admin_env_links_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    text = "🔗 Редактирование ссылок:\n\n"
    text += f"📊 rates (BUY_RATES_BTC): {read_env_var('BUY_RATES_BTC', '— не задано')}\n"
    text += f"💰 sell_btc (SELL_RATES_BTC): {read_env_var('SELL_RATES_BTC', '— не задано')}\n"
    text += f"📢 news_channel: {read_env_var('NEWS_CHANNEL', '— не задано')}\n"
    text += f"👨‍💻 operator: {read_env_var('OPERATOR', '— не задано')}\n"
    text += f"👨‍💻 operator2: {read_env_var('OPERATOR2', '— не задано')}\n"
    text += f"👨‍💻 operator3: {read_env_var('OPERATOR3', '— не задано')}\n"
    text += f"⚙️ work_operator: {read_env_var('WORK_OPERATOR', '— не задано')}\n"
    text += f"📞 contact_support: {read_env_var('CONTACT_SUPPORT', '— не задано')}\n"
    text += f"📰 contact_news: {read_env_var('CONTACT_NEWS', '— не задано')}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 rates", callback_data="link_rates")],
        [InlineKeyboardButton(text="💰 sell_btc", callback_data="link_sell_btc")],
        [InlineKeyboardButton(text="📢 news_channel", callback_data="link_news_channel")],
        [InlineKeyboardButton(text="👨‍💻 operator", callback_data="link_operator")],
        [InlineKeyboardButton(text="👨‍💻 operator2", callback_data="link_operator2")],
        [InlineKeyboardButton(text="👨‍💻 operator3", callback_data="link_operator3")],
        [InlineKeyboardButton(text="⚙️ work_operator", callback_data="link_work_operator")],
        [InlineKeyboardButton(text="📞 contact_support", callback_data="link_contact_support")],
        [InlineKeyboardButton(text="📰 contact_news", callback_data="link_contact_news")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)


@dp.callback_query(lambda c: c.data in LINK_FIELDS)
async def admin_link_field_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    field_key = callback.data
    env_key = LINK_FIELDS[field_key]
    current_value = read_env_var(env_key, "")

    await state.update_data(link_field=field_key, env_key=env_key)
    await state.set_state(AdminStates.waiting_link_field)

    await callback.message.edit_text(
        f"🔗 Введите новое значение для <code>{env_key}</code>:\n\n"
        f"Текущее значение: {current_value if current_value else '— не задано'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="admin_env_links")]
        ]),
        parse_mode="HTML"
    )


@dp.message(AdminStates.waiting_link_field)
async def admin_set_link_field(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    env_key = data.get("env_key")
    new_value = message.text.strip()

    update_env_var(env_key, new_value)

    # Reload the env file for the current process
    load_dotenv(ENV_PATH, override=True)

    await message.answer(
        f"✅ <code>{env_key}</code> обновлено: {new_value}",
        reply_markup=admin_main_menu(),
        parse_mode="HTML"
    )
    await state.clear()


# ==================== COMMISSION ADMIN ====================

@dp.callback_query(lambda c: c.data == "admin_commission")
async def admin_commission(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)

    current = get_commission()
    await callback.message.edit_text(
        f"💰 Текущая комиссия: <b>{current}%</b>\n\n"
        f"Введите новое значение комиссии (число от 0 до 100):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="admin_panel")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_commission)


@dp.message(AdminStates.waiting_commission)
async def admin_set_commission(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        percent = float(message.text.strip().replace(",", "."))
        if percent < 0 or percent > 100:
            return await message.answer("⚠️ Введите число от 0 до 100")
    except ValueError:
        return await message.answer("⚠️ Введите корректное число")

    set_commission(percent)
    await message.answer(f"✅ Комиссия обновлена: {percent}%", reply_markup=admin_main_menu())
    await state.clear()

async def notify_admins(deal_type: str, user_id: int, crypto: str, amount: float, requisites: str):
    text = (
        f"📢 Новая заявка ({deal_type})\n"
        f"👤 Пользователь: {user_id}\n"
        f"💰 Сумма: {amount}\n"
        f"🔗 Криптовалюта: {crypto}\n"
        f"💳 Реквизиты: {requisites}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


# Главное меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🟢 Купить"),
            KeyboardButton(text="🟡 Продать")
        ],
        [
            KeyboardButton(text="☎️ Контакты"),
            KeyboardButton(text="🎲 Призовая игра")
        ],
        [
            KeyboardButton(text="👤 Личный кабинет")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)    

#КУПИТЬ

class BuyStatesRF(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()

class BuyStatesRB(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()
    



# Клавиатура выбора страны для покупки
buy_country_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 РФ", callback_data="buy_rf"),
         InlineKeyboardButton(text="🇧🇾 РБ", callback_data="buy_rb")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
    ]
)

sell_country_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 РФ", callback_data="sell_rf"),
         InlineKeyboardButton(text="🇧🇾 РБ", callback_data="sell_rb")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
    ]
)

#РБ ЛОГИКА ПОКА НЕ РАБОТАЕТ ЗАМЕНИТЬ 
@dp.callback_query(lambda c: c.data == "buy_rb")
async def process_buy_rb(callback: types.CallbackQuery):
    # показываем только кнопку "Назад"
    await callback.message.edit_reply_markup(
        InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="back_to_menu")]]
        )
    )
    await callback.answer()

    # ждём 10 секунд
    await asyncio.sleep(10)

    # перекидываем в главное меню
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu)

#РБ ЛОГИКА ПОКА НЕ РАБОТАЕТ ЗАМЕНИТЬ 
dp.callback_query(lambda c: c.data == "sell_rb")
async def process_sell_rb(callback: types.CallbackQuery):
    # показываем только кнопку "Назад"
    await callback.message.edit_reply_markup(
        InlineKeyboardMarkup(
            InlineKeyboardButton(text="◀ Назад", callback_data="back")

        )
    )
    await callback.answer()

    # ждём 10 секунд
    await asyncio.sleep(10)

    # перекидываем в главное меню
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu)



# Обработчик кнопки "🟢 Купить"

# buy_rates is maintained in memory and refreshed from CoinGecko.

@dp.message(lambda msg: msg.text == "🟢 Купить")
async def buy_handler(message: types.Message, state: FSMContext):
    await state.clear()
    photo = FSInputFile("images/strana.jpg")
    await message.answer_photo(
        photo,
        caption="Выберите страну для покупки 👇",
        reply_markup=buy_country_kb
    )
    

buy_crypto_kb_rf = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Bitcoin (BTC)", callback_data="buy_btc_rf")],
        [InlineKeyboardButton(text="Litecoin (LTC)", callback_data="buy_ltc_rf")],
        [InlineKeyboardButton(text="Tether (USDT)", callback_data="buy_usdt_rf")],
        [InlineKeyboardButton(text="Monero (XMR)", callback_data="buy_xmr_rf")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
    ]
)

buy_crypto_kb_rb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Bitcoin (BTC)", callback_data="buy_btc_rb")],
        [InlineKeyboardButton(text="Litecoin (LTC)", callback_data="buy_ltc_rb")],
        [InlineKeyboardButton(text="Tether (USDT)", callback_data="buy_usdt_rb")],
        [InlineKeyboardButton(text="Monero (XMR)", callback_data="buy_xmr_rb")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
    ]
)






@dp.callback_query(lambda c: c.data == "buy_rf")
async def choose_buy_crypto_rf(callback: types.CallbackQuery):
    photo = FSInputFile("images/coins.jpg")
    await callback.message.answer_photo(
        photo,
        caption="♻️ Выберите криптовалюту для покупки:",
        reply_markup=buy_crypto_kb_rf
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "buy_rb")
async def choose_buy_crypto_rb(callback: types.CallbackQuery):
    photo = FSInputFile("images/coins.jpg")
    await callback.message.answer_photo(
        photo,
        caption="♻️ Выберите криптовалюту для покупки:",
        reply_markup=buy_crypto_kb_rb
    )
    await callback.answer()
#Логика покупки ( РФ)


# Клавиатура отмены
cancel_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="buy_rf")]
    ]
)

@dp.callback_query(lambda c: c.data in {"buy_btc_rf", "buy_ltc_rf", "buy_usdt_rf", "buy_xmr_rf"})
async def buy_crypto_rf(callback: types.CallbackQuery, state: FSMContext):
    crypto = callback.data.split("_")[1].upper()
    base_rate = buy_rates.get(crypto)
    if not base_rate or base_rate <= 0:
        await callback.message.answer("⚠️ Курс этой валюты пока не загружен. Попробуйте позже.")
        return await callback.answer()

    rate = float(base_rate)

    # Примеры для каждой монеты
    examples = {
        "BTC": "0.001, 0.08 или 1250 (в рублях)",
        "LTC": "1, 5 или 1250 (в рублях)",
        "USDT": "10, 20 или 1250 (в рублях)",
        "XMR": "0.1, 1 или 1250 (в рублях)"
    }
    example_text = examples.get(crypto, "0.001, 0.08 или 1250 (в рублях)")

    await callback.message.answer(
        f"📱 УКАЖИТЕ СУММУ ДЛЯ ПОКУПКИ ({crypto}):\n"
        f"✅ Например: {example_text}",
         reply_markup=cancel_kb
    )

    await state.set_state(BuyStatesRF.waiting_for_amount)
    await state.update_data(crypto=crypto, rate=rate)
    await callback.answer()

@dp.message(BuyStatesRF.waiting_for_amount)
async def process_buy_amount_rf(message: types.Message, state: FSMContext):
    data = await state.get_data()
    crypto = data.get("crypto")
    rate = data.get("rate")

    if not crypto:
        await state.clear()
        return await message.answer("⚠️ Не удалось определить валюту. Начните заново.")

    try:
        rate = float(rate)
        if rate <= 0:
            raise ValueError
    except (TypeError, ValueError):
        await state.clear()
        return await message.answer("⚠️ Курс этой валюты пока не загружен. Попробуйте позже.")

    try:
        user_amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        return await message.answer("⚠️ Введите корректное число!")

    # Пороги для крипты
    crypto_thresholds = {
        "BTC": 1,     # всё что <1 трактуем как BTC
        "USDT": 500,  # всё что <500 трактуем как USDT
        "XMR": 500,   # всё что <500 трактуем как XMR
        "LTC": 200    # всё что <200 трактуем как LTC
    }
    threshold = crypto_thresholds.get(crypto.upper(), 0)

    # Логика: если сумма >= 1250 — трактуем как рубли
    if user_amount >= 1250:
        rub_amount = int(user_amount)
        crypto_amount = rub_amount / rate
    else:
        # если меньше порога — трактуем как крипту
        if user_amount < threshold:
            crypto_amount = user_amount
            rub_amount = crypto_amount * rate
        else:
            # если >= порога, но <1250 — трактуем как рубли
            rub_amount = int(user_amount)
            crypto_amount = rub_amount / rate

    # проверка минималки
    if rub_amount < 1250:
        return await message.answer("⚠️ Минимальная сумма 1250 рублей.")

    # округление крипты
    if crypto.upper() == "BTC":
        crypto_amount_val = round(crypto_amount, 8)
        crypto_amount_fmt = f"{crypto_amount_val:.8f}"
    else:
        crypto_amount_val = round(crypto_amount, 2)
        crypto_amount_fmt = f"{crypto_amount_val:.2f}"

    # применяем комиссию: user pays MORE
    commission = get_commission()
    rub_amount_with_commission = int(round(rub_amount * (1 + commission / 100)))

    # сохраняем в FSM числа
    await state.update_data(rub_amount=rub_amount_with_commission, crypto_amount=crypto_amount_val, base_rub=rub_amount)

    await message.answer(
        f"Вы покупаете: {crypto_amount_fmt} {crypto}\n"
        f"Сумма оплаты: {rub_amount_with_commission} ₽ (комиссия {commission}%)"
    )

    # Клавиатура выбора метода оплаты
    bank_kb_rf = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 ЛЮБАЯ КАРТА РФ — НОМЕР КАРТЫ", callback_data="bank_card_rf")],
            [InlineKeyboardButton(text="🇷🇺 ЛЮБАЯ КАРТА РФ — СБП", callback_data="bank_spb_rf")],
            [InlineKeyboardButton(text="🇷🇺 ЛЮБАЯ КАРТА РФ — СБП‑ТРАНСГРАН (СКИДКА 20%)", callback_data="bank_spb_transgran_rf")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
        ]
    )

    photo = FSInputFile("images/metod.jpg")
    await message.answer_photo(photo, caption="Выберите способ оплаты:", reply_markup=bank_kb_rf)


# Обработка выбора банка
@dp.callback_query(lambda c: c.data in ["bank_card_rf", "bank_spb_rf", "bank_spb_transgran_rf"])
async def bank_selected_rf(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_wallet = data.get("user_wallet")
    data.get("rub_amount", 0)       # сумма в рублях
    crypto_amount = data.get("crypto_amount", 0) # сумма в крипте
    crypto = data.get("crypto")

    # Если кошелёк ещё не введён — спрашиваем с картинкой по выбранной крипте
    # Если кошелёк ещё не введён — спрашиваем с картинкой по выбранной крипте


    if not user_wallet:
       await state.update_data(pending_bank=callback.data)  # запоминаем выбранный метод

    if crypto == "BTC":
        photo = FSInputFile("images/btc.jpg")
        caption = (
            f"Введите BITCOIN адрес кошелька,\n"
            f"куда вы хотите отправить: {crypto_amount} BTC"
        )
    elif crypto == "LTC":
        photo = FSInputFile("images/ltc.jpg")
        caption = (
            f"Введите LITECOIN адрес кошелька,\n"
            f"куда вы хотите отправить: {crypto_amount} LTC"
        )
    elif crypto.startswith("USDT"):
        photo = FSInputFile("images/trc20.jpg")
        caption = (
            f"Введите Tether адрес кошелька,\n"
            f"куда вы хотите отправить: {crypto_amount} USDT"
        )
    else:  # XMR
        photo = FSInputFile("images/xmr.jpg")
        caption = (
            f"Введите MONERO адрес кошелька,\n"
            f"куда вы хотите отправить: {crypto_amount} XMR"
        )

    back_inline = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="buy_rf")]]
    )

    await callback.message.answer_photo(photo, caption=caption, reply_markup=back_inline)
    await state.set_state(BuyStatesRF.waiting_for_wallet)
    await callback.answer()
    return




# Приём кошелька и сразу формирование заявки


@dp.message(BuyStatesRF.waiting_for_wallet)
async def save_wallet_and_form(message: types.Message, state: FSMContext):
    wallet = message.text.strip()
    if len(wallet) < 8:
        return await message.answer("⚠️ Похоже на некорректный адрес. Пришлите полный адрес кошелька.")

    data = await state.get_data()
    pending_bank = data.get("pending_bank")

    await message.answer(f"✅ Адрес кошелька принят:\n<code>{wallet}</code>", parse_mode="HTML")

    # сразу формируем заявку
    await form_order(message, state, pending_bank, wallet)


# Формируем текст заявки
async def form_order(message: types.Message, state: FSMContext, bank_code: str, wallet: str):
    data = await state.get_data()
    rub_amount = data.get("rub_amount", 0)       # сумма в рублях
    crypto_amount = data.get("crypto_amount", 0) # сумма в крипте
    crypto = data.get("crypto")

    deal_id = f"1764{int(datetime.now().timestamp())}{random.randint(100,999)}"

    if bank_code == "bank_card_rf":
        requisites = get_bank("card") or "— не заданы"
        method_name = "🇷🇺 Реквизиты:"
    elif bank_code == "bank_spb_rf":
        requisites = get_bank("spb") or "— не заданы"
        method_name = "🇷🇺 Реквизиты:"
    else:
        requisites = get_bank("spb_transgran") or "— не заданы"
        method_name = "🇷🇺 Реквизиты:"

    text = (
        f"✅ Заявка №<code>{deal_id}</code>\n\n"
        f"Будет зачислено: <code>{crypto_amount} {crypto}</code>\n"
        f"{crypto}-Кошелек:\n<code>{wallet}</code>\n\n"
        f"📱 Сумма к оплате: <code>{rub_amount} ₽</code>\n"
        f"{method_name}<code>{requisites}</code>\n\n"
        f"⚠️ Заявка действует: 15 минут\n\n"
        f"✅ После перевода необходимо нажать 'Оплатил'\n"
        f"📸 После этого отправить боту чек/скрин оплаты."
    )

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплатил", callback_data="confirm_payment")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_order")]
    ])

    photo = FSInputFile("images/metod.jpg")
    await message.answer_photo(photo, caption=text, reply_markup=confirm_kb, parse_mode="HTML")
    await state.set_state(OrderStates.waiting_payment_confirm)


@dp.callback_query(lambda c: c.data == "back")
async def process_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev_level = data.get("prev_level")

    if prev_level == "menu":
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb)
    elif prev_level == "country":
        await callback.message.edit_text("Выберите страну:", reply_markup=buy_country_kb)
    elif prev_level == "crypto":
        await callback.message.edit_text("Выберите криптовалюту:", reply_markup=crypto_kb)
    # можно расширять дальше под твои уровни

    await callback.answer()



@dp.callback_query(lambda c: c.data == "cancel_order")
async def process_cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
    await callback.message.answer("❌ Сделка отменена")

    # сразу перекидываем в меню покупки (buy_rf)
    await choose_buy_crypto_rf(callback)


@dp.callback_query(lambda c: c.data == "buy_rf")
async def choose_buy_crypto_rf(callback: types.CallbackQuery):
    photo = FSInputFile("images/coins.jpg")
    await callback.message.answer_photo(
        photo,
        caption="♻️ Выберите криптовалюту для покупки:",
        reply_markup=buy_crypto_kb_rf
    )
    await callback.answer()






# После нажатия "Оплатил" бот просит прислать чек
@dp.callback_query(lambda c: c.data == "confirm_payment")
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📸 Отправьте чек/скрин оплаты (PNG/JPG) или документ (PDF).")
    await state.set_state(OrderStates.waiting_payment_confirm)
    await callback.answer()


# Обработка фото (скриншот)
@dp.message(OrderStates.waiting_payment_confirm, F.photo)
async def process_payment_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id  # берём последнее фото (лучшее качество)
    data = await state.get_data()

    # Отправляем в админку
    for admin in ADMIN_IDS:
        await bot.send_photo(admin, photo_id, caption=f"📩 Чек по заявке №{data.get('deal_id')} от пользователя {message.from_user.id}")

    await message.answer("✅ Спасибо! Ожидайте сообщения оператора.")
    await state.clear()


# Обработка документа (PDF)
@dp.message(OrderStates.waiting_payment_confirm, F.document)
async def process_payment_document(message: types.Message, state: FSMContext):
    doc = message.document
    data = await state.get_data()

    # Проверяем формат
    if doc.mime_type not in ["application/pdf", "image/png", "image/jpeg"]:
        return await message.answer("⚠️ Пришлите файл в формате PNG, JPG или PDF.")

    # Отправляем в админку
    for admin in ADMIN_IDS:
        await bot.send_document(admin, doc.file_id, caption=f"📩 Чек по заявке №{data.get('deal_id')} от пользователя {message.from_user.id}")

    await message.answer("✅ Спасибо! Ожидайте сообщения оператора.")
    await state.clear()








# Продать 
# ==== SELL (RF) — mirrored to BUY, address from DB ====

# sell_rates is maintained in memory and refreshed from CoinGecko.




class SellStatesRF(StatesGroup):
    waiting_for_amount = State()
    waiting_for_promo = State()
    waiting_for_method = State()
    waiting_for_receipt = State()
    waiting_for_card = State()

# Клавиатуры
sell_country_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 РФ", callback_data="sell_rf"),
         InlineKeyboardButton(text="🇧🇾 РБ", callback_data="sell_rb")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")]
    ]
)

sell_crypto_kb_rf = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Bitcoin (BTC)", callback_data="sell_btc_rf")],
        [InlineKeyboardButton(text="Litecoin (LTC)", callback_data="sell_ltc_rf")],
        [InlineKeyboardButton(text="Tether (USDT)", callback_data="sell_usdt_rf")],
        [InlineKeyboardButton(text="Monero (XMR)", callback_data="sell_xmr_rf")],
        [InlineKeyboardButton(text="Назад", callback_data="sell_country")]
    ]
)

cancel_sell_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="buy_rf")]
    ]
)

@dp.message(lambda msg: msg.text == "🟡 Продать")
async def sell_handler(message: types.Message, state: FSMContext):
    await state.clear()  # сбрасываем FSM
    photo = FSInputFile("images/strana.jpg")
    await message.answer_photo(
        photo,
        caption="Выберите страну для продажи 👇",
        reply_markup=sell_country_kb
    )

@dp.callback_query(lambda c: c.data == "sell_rf")
async def choose_sell_crypto_rf(callback: types.CallbackQuery):
    photo = FSInputFile("images/coins.jpg")
    await callback.message.answer_photo(
        photo,
        caption="♻️ Выберите криптовалюту для продажи:",
        reply_markup=sell_crypto_kb_rf
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data in {"sell_btc_rf", "sell_ltc_rf", "sell_usdt_rf", "sell_xmr_rf"})
async def sell_crypto_rf(callback: types.CallbackQuery, state: FSMContext):
    crypto = callback.data.split("_")[1].upper()
    base_rate = sell_rates.get(crypto, 0)   # или buy_rates, если используешь один словарь
    if not base_rate or base_rate == 0:
        return await callback.message.answer("⚠️ Курс для этой валюты не найден.")

    # используем чистый курс
    rate = round(base_rate, 2)
    await state.update_data(crypto=crypto, rate=rate)

    # Примеры для каждой монеты
    examples = {
        "BTC": "0.001, 0.08 или 1250 (в рублях)",
        "LTC": "1, 5 или 1250 (в рублях)",
        "USDT": "10, 20 или 1250 (в рублях)",
        "XMR": "0.1, 1 или 1250 (в рублях)"
    }
    example_text = examples.get(crypto, "0.001, 0.08 или 1250 (в рублях)")

    await callback.message.answer(
        f"📱 УКАЖИТЕ СУММУ ДЛЯ ПРОДАЖИ ({crypto}):\n"
        f"✅ Например: {example_text}",
        reply_markup=cancel_sell_kb
    )

    # переводим в состояние ожидания суммы
    await state.set_state(SellStatesRF.waiting_for_amount)
    await callback.answer()


@dp.message(SellStatesRF.waiting_for_amount)
async def process_sell_amount_rf(message: types.Message, state: FSMContext):
    data = await state.get_data()
    crypto = data.get("crypto")
    rate = data.get("rate")

    if not rate or rate == 0:
        await state.clear()  # сброс FSM
        return await message.answer("⚠️ Курс не найден, попробуйте позже.")

    try:
        user_amount = float(message.text.replace(",", ".").strip())
    except ValueError:
        # Ошибка ввода числа
        await state.clear()  # сброс FSM, чтобы можно было нажать другие кнопки
        return await message.answer("⚠️ Введите корректное число!")

    # определяем тип ввода
    if user_amount < 1000:
        # трактуем как крипту
        crypto_amount = user_amount
        rub_amount = crypto_amount * rate
    elif user_amount >= 2500:
        # трактуем как рубли
        rub_amount = user_amount
        crypto_amount = rub_amount / rate
    else:
        return await message.answer("⚠️ Введите сумму меньше 1000 (в крипте) или больше 2500 (в рублях).")

    # округление крипты
    if crypto.upper() == "BTC":
        crypto_amount_fmt = round(crypto_amount, 8)
    else:
        crypto_amount_fmt = round(crypto_amount, 2)

    # рубли всегда целым числом
    rub_amount_fmt = int(round(rub_amount))

    # минимальные значения для каждой монеты
    min_limits = {
        "BTC": 0.001,
        "LTC": 1,
        "USDT": 10,
        "XMR": 0.1
    }
    min_crypto = min_limits.get(crypto.upper(), 0)

    # проверка минималки: ошибка только если оба условия не выполнены
    if rub_amount_fmt < 1250 and crypto_amount_fmt < min_crypto:
        return await message.answer(
            f"⚠️ Минимальная сумма для {crypto.upper()} — {min_crypto} {crypto.upper()} или 1250 ₽"
        )

    # применяем комиссию: user receives LESS
    commission = get_commission()
    rub_amount_with_commission = int(round(rub_amount * (1 - commission / 100)))

    # сохраняем
    await state.update_data(rub_amount=rub_amount_with_commission, crypto_amount=crypto_amount_fmt, base_rub=rub_amount)

    # вывод пользователю
    photo = FSInputFile("images/wallet.jpg")
    await message.answer_photo(
        photo,
        caption=(
            f"Вы продаёте: <code>{crypto_amount_fmt} {crypto.upper()}</code>\n"
            f"Сумма к получению: <code>{rub_amount_with_commission} ₽</code> (комиссия {commission}%)\n\n"
            f"Введите 💳 номер карты, куда вы хотите получить: <code>{rub_amount_with_commission} ₽</code>"
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data="sell_rf")]

        ]

        ),
        parse_mode="HTML"
    )

    await state.set_state(SellStatesRF.waiting_for_card)


# После ввода карты формируем заявку
@dp.message(SellStatesRF.waiting_for_card)
async def process_sell_card_rf(message: types.Message, state: FSMContext):
    data = await state.get_data()
    crypto = data.get("crypto")
    crypto_amount = data.get("crypto_amount")
    rub_amount = data.get("rub_amount")

    card_number = message.text.strip()

    # Генерация уникального ID заявки
    deal_id = f"1764{int(datetime.now().timestamp())}{random.randint(100,999)}"

    wallet_address = get_address(crypto)
    if not wallet_address:
        wallet_address = "(не задан)"

    text = (
        f"✅ Заявка №<code>{deal_id}</code>\n\n"
        f"💸 Вы продаёте: <code>{crypto_amount} {crypto}</code>\n"
        f"📱 Сумма к получению: <code>{rub_amount} ₽</code>\n\n"
        f"👛 {crypto}-Кошелек:\n<code>{wallet_address}</code>\n\n"
        f"💳 Номер карты для зачисления:\n<code>{card_number}</code>\n\n"
        f"⚠️ Заявка действует: 15 минут\n\n"
        f"✅ После отправки криптовалюты необходимо нажать 'Оплатил'\n"
        f"📸 После этого отправить боту чек/скрин перевода."
    )

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Оплата совершена", callback_data="confirm_payment_sell")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_order")]
    ])

    photo = FSInputFile("images/metod.jpg")
    await message.answer_photo(photo, caption=text, reply_markup=confirm_kb, parse_mode="HTML")

    # Сохраняем deal_id в FSM
    await state.update_data(deal_id=deal_id)
    await state.set_state(SellStatesRF.waiting_for_promo)  # или отдельное состояние ожидания подтверждения




@dp.callback_query(lambda c: c.data == "back")
async def process_back(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prev_level = data.get("prev_level")

    if prev_level == "menu":
        await callback.message.edit_text("Главное меню:", reply_markup=main_menu)
    elif prev_level == "country":
        await callback.message.edit_text("Выберите страну:", reply_markup=buy_country_kb)
    elif prev_level == "crypto":
        await callback.message.edit_text("Выберите криптовалюту:", reply_markup=crypto_kb)
    # можно расширять дальше под твои уровни

    await callback.answer()


    
@dp.callback_query(lambda c: c.data == "cancel_order")
async def process_cancel_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await state.clear()
    await callback.message.answer("❌ Сделка отменена")

    # сразу перекидываем в меню продажи (sell_rf)
    await choose_sell_crypto_rf(callback)


@dp.callback_query(lambda c: c.data == "sell_rf")
async def choose_sell_crypto_rf(callback: types.CallbackQuery):
    photo = FSInputFile("images/coins.jpg")
    await callback.message.answer_photo(
        photo,
        caption="♻️ Выберите криптовалюту для продажи:",
        reply_markup=sell_crypto_kb_rf
    )
    await callback.answer()




# После нажатия "Оплатил" бот просит прислать чек
@dp.callback_query(lambda c: c.data == "confirm_payment_sell")
async def confirm_payment_sell(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("📸 Отправьте чек/скрин перевода (PNG/JPG) или документ (PDF).")
    await state.set_state(SellStatesRF.waiting_for_receipt)
    await callback.answer()


# Обработка фото (скриншот)
@dp.message(SellStatesRF.waiting_for_receipt, F.photo)
async def process_payment_photo_sell(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    deal_id = data.get("deal_id")

    # Отправляем чек в админку
    for admin in ADMIN_IDS:
        await bot.send_photo(
            admin,
            photo_id,
            caption=f"📩 Чек по заявке №{deal_id} (продажа) от пользователя {message.from_user.id}"
        )

    await message.answer("✅ Спасибо! Ожидайте сообщения оператора.")
    await state.clear()



#===========================КОНтакты===================#
# Клавиатура для контактов
contacts_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📢 КАНАЛ", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="📝 ОТЗЫВЫ", url=REVIEWS_URL)],
        [InlineKeyboardButton(text="🧑‍💻 ВТОРОЙ ОПЕРАТОР", url=SECOND_OPERATOR_URL)],
        [InlineKeyboardButton(text="✅ ЧАТ С БОНУСАМИ 💳", url=BONUS_CHAT_URL)],
        [InlineKeyboardButton(text="🌞 АДМИНИСТРАТОР ЧАТА", url=CHAT_ADMIN_URL)],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
    ]
)


# Обработчик кнопки "☎️ Контакты"
@dp.message(lambda msg: msg.text == "☎️ Контакты")
async def contacts_handler(message: types.Message):
    photo = FSInputFile("images/contacts.jpg")  # картинка должна лежать рядом с кодом
    await message.answer_photo(
        photo,
        caption="Контакты и поддержка 24/7",
        reply_markup=contacts_kb
    )

# Обработчик кнопки "Назад" из контактов
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "Вы вернулись в главное меню 👇",
        reply_markup=main_menu
    )
    await callback.answer()

#=======================Бонусная игра===============#


# Клавиатура после "Призовая игра"
bonus_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🎰 Испытать удачу"),
            KeyboardButton(text="🤑 Большая рулетка")
        ],
        [
            KeyboardButton(text="◀ Назад", callback_data="back")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)


# Обработчик кнопки "🎲 Призовая игра"
@dp.message(lambda msg: msg.text == "🎲 Призовая игра")
async def bonus_game_handler(message: types.Message):
    photo = FSInputFile("images/bonus.jpg")  # картинка должна лежать рядом с кодом
    await message.answer_photo(photo)
    await message.answer("Розыгрыши от BANAN_BTC", reply_markup=bonus_menu)

# 🎰 Испытать удачу
@dp.message(lambda msg: msg.text == "🎰 Испытать удачу")
async def try_luck_handler(message: types.Message):
    await message.answer(
        "У тебя нету попыток на игру в лотерею.Чтобы получить попытку соверши сделку👇"
    )

# 🤑 Большая рулетка
@dp.message(lambda msg: msg.text == "🤑 Большая рулетка")
async def big_roulette_handler(message: types.Message):
    photo = FSInputFile("images/bigwin.jpg")  # картинка рядом с кодом
    await message.answer_photo(
        photo,
        caption=f"👉 [Смотреть рулетку]({ROULETTE_URL})",
        parse_mode="Markdown"
    )
# ◀ Назад
@dp.message(lambda msg: msg.text == "◀ Назад")
async def back_to_main_menu(message: types.Message):
    await message.answer("Вы вернулись в главное меню 👇", reply_markup=main_menu)


#==================ЛИЧНЫЙ КАБИНЕТ==========================№
# Клавиатура личного кабинета
profile_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="💳 Мои транзакции"),
            KeyboardButton(text="📈 Реф.Программа")
        ],
        [
            KeyboardButton(text="💸 Вывод"),
            KeyboardButton(text="◀ Назад")
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# Обработчик кнопки "👤 Личный кабинет"
@dp.message(lambda msg: msg.text == "👤 Личный кабинет")
async def profile_handler(message: types.Message):
    await message.answer("Ваш кабинет", reply_markup=profile_kb)

# 💳 Мои транзакции
@dp.message(lambda msg: msg.text == "💳 Мои транзакции")
async def transactions_handler(message: types.Message):
    await message.answer(
        "Вы не совершили ни одной сделки.\n"
    )

# 📈 Реф.Программа
ref_share_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📲 Поделиться ссылкой", switch_inline_query=REF_BOT_URL)],
        [InlineKeyboardButton(text="◀ Назад", callback_data="back_to_profile")]
    ]
)

async def send_ref_message(message: types.Message):
    await message.answer(
        (
            "Зарабатывайте с нашей реферальной программой! 🤑\n\n"
            "Приглашайте друзей и получайте процент с каждой их сделки – без ограничений и сложностей!\n\n"
            "🔹 Как это работает?\n"
            "1️⃣ Вы делитесь своей реферальной ссылкой.\n"
            "2️⃣ Ваши друзья совершают обмены.\n"
            "3️⃣ Вы автоматически получаете процент с каждой их сделки!\n\n"
            "🎁 Как использовать заработанные средства?\n"
            "✅ Обменивайте на скидку при сделках\n"
            "✅ Выводите удобным для вас способом\n\n"
            f"📲 Ваша реферальная ссылка:\n🔗 {REF_BOT_URL}\n\n"
            "📊 Ваши текущие показатели:\n"
            "💰 Ваши текущие накопления: 0₽ ~ 0 бел.рублей\n"
            "👥 Количество рефералов: 0, активных 0\n"
            "💰 Всего получено от рефералов: 0\n\n"
            "🎲 Проведенных сделок: 0\n"
            "🏆 Ваш ранг: 👶\n"
            "🎯 Ваша скидка: 0.0%\n\n"
            "🚀 Начните зарабатывать уже сейчас – делитесь ссылкой и увеличивайте свой доход!"
        ),
        reply_markup=ref_share_kb,
        parse_mode="HTML"
    )

# 💸 Вывод
@dp.message(lambda msg: msg.text == "💸 Вывод")
async def withdraw_handler(message: types.Message):
    await message.answer("Минимальная сумма для вывода средств равна 500₽")

# ◀ Назад (из личного кабинета)
@dp.message(lambda msg: msg.text == "◀ Назад")
async def back_to_main_menu(message: types.Message):
    await message.answer("Вы вернулись в главное меню 👇", reply_markup=main_menu)

# ◀ Назад (из инлайн-кнопки реф.программы)
@dp.callback_query(lambda c: c.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    await callback.message.answer("Ваш кабинет", reply_markup=profile_kb)
    await callback.answer()

async def main():
    # создаём таблицы, если их нет
    init_db()

    rates = await fetch_crypto_rates_coingecko()
    if rates:
        update_rates_from_coingecko(rates)
    else:
        logging.warning("CoinGecko rates were not loaded on startup")

    asyncio.create_task(refresh_rates_task())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
