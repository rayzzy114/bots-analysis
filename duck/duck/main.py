import asyncio
import random
import os
import sqlite3
from datetime import datetime
import aiohttp

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils.env_writer import update_env_var, read_env_var

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
DB_FILE = "duck_exchange.db"

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env!")

# ======================= КУРСЫ И МИНИМАЛКИ =======================
buy_rates = {
    "BTC": int(os.getenv("BUY_RATES_BTC", 8704698)),
    "ETH": int(os.getenv("BUY_RATES_ETH", 125000)),
    "LTC": int(os.getenv("BUY_RATES_LTC", 8100)),
    "USDT": int(os.getenv("BUY_RATES_USDT", 90)),
    "XMR": int(os.getenv("BUY_RATES_XMR", 31555)),
}

sell_rates = {
    "BTC": int(os.getenv("SELL_RATES_BTC", 6340569)),
    "ETH": int(os.getenv("SELL_RATES_ETH", 120000)),
    "LTC": int(os.getenv("SELL_RATES_LTC", 6736)),
    "USDT": int(os.getenv("SELL_RATES_USDT", 73)),
    "XMR": int(os.getenv("SELL_RATES_XMR", 28000)),
}

MIN_CRYPTO = {
    "BTC": 0.0001,
    "LTC": 0.1,
    "USDT": 10.0,
    "XMR": 0.04,
    "ETH": 0.0001,
}

MIN_RUB = 1500

# ======================= COINGECKO FALLBACK =======================
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

# Маппинг монет для CoinGecko API
COINGECKO_COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "LTC": "litecoin",
    "XMR": "monero",
    "USDT": "tether",
}

async def fetch_crypto_rates_coingecko() -> dict[str, dict[str, float]] | None:
    """Fetch crypto rates from CoinGecko API. Returns {coin: {"usd": x, "rub": y}} or None on failure."""
    try:
        async with aiohttp.ClientSession() as session:
            ids = ",".join(COINGECKO_COINS.values())
            url = f"{COINGECKO_URL}?ids={ids}&vs_currencies=usd,rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    result = {}
                    for coin, cg_id in COINGECKO_COINS.items():
                        if cg_id in data:
                            result[coin] = {
                                "usd": float(data[cg_id].get("usd", 0)),
                                "rub": float(data[cg_id].get("rub", 0)),
                            }
                    if result:
                        print(f"✅ CoinGecko rates fetched: {list(result.keys())}")
                        return result
    except Exception as e:
        print(f"❌ CoinGecko fetch error: {e}")
    return None

def update_rates_from_coingecko(rates: dict[str, dict[str, float]]):
    """Update global buy_rates and sell_rates from CoinGecko data."""
    for coin, price_data in rates.items():
        if price_data.get("rub") and price_data["rub"] > 0:
            # Используем RUB цену как базу
            rub_price = price_data["rub"]
            if coin in buy_rates:
                buy_rates[coin] = int(rub_price)
            if coin in sell_rates:
                sell_rates[coin] = int(rub_price)
            print(f"📈 {coin} rate updated from CoinGecko: {rub_price} RUB")

async def refresh_rates_task():
    """Background task to refresh rates from CoinGecko periodically."""
    while True:
        rates = await fetch_crypto_rates_coingecko()
        if rates:
            update_rates_from_coingecko(rates)
        await asyncio.sleep(300)  # обновляем каждые 5 минут


CHAT_URL = os.getenv("CHAT_URL", "https://t.me/+EE6hLhKEFhUwNjYx")
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@duckobmen")
COMPLAINT_BOOK = os.getenv("COMPLAINT_BOOK", "@duckobmen_complaints")
RESERVE_URL = os.getenv("RESERVE_URL", "https://t.me/duckobmen_reserv_bot?start=reserv")
OPERATOR_CONTACT = os.getenv("OPERATOR_CONTACT", "@duckobmen")
REVIEWS_URL = os.getenv("REVIEWS_URL", "https://t.me/duckobmen_reviews")
THANK_YOU_TEXT = os.getenv("THANK_YOU_TEXT", "✅ Спасибо, чек получен!")
GOOD_EXCHANGE_TEXT = os.getenv("GOOD_EXCHANGE_TEXT", "🚀 Желаем хороших обменов!")
DEFAULT_COMMISSION = int(os.getenv("COMMISSION_PERCENT", 0))


# ======================= БОТ И ДИСПАТЧЕР =======================
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ======================= БАЗА ДАННЫХ =======================

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()

    # Реквизиты для приёма RUB (ПОКУПКА — пользователь платит тебе)
    c.execute("""
    CREATE TABLE IF NOT EXISTS payment_requisites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card TEXT,
        bank TEXT,
        country TEXT
    )
""")

    # Таблица настроек (комиссия и т.д.)
    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            commission INTEGER DEFAULT 0
        )
    """)
    # Вставляем дефолтную строку если её нет
    c.execute("INSERT OR IGNORE INTO settings (id, commission) VALUES (1, ?)", (DEFAULT_COMMISSION,))


    # Адреса для приёма крипты (ПРОДАЖА — пользователь отправляет тебе крипту)
    c.execute("""
        CREATE TABLE IF NOT EXISTS crypto_addresses (
            coin TEXT PRIMARY KEY,
            address TEXT
        )
    """)

    # Текст поддержки
    c.execute("""
        CREATE TABLE IF NOT EXISTS support_text (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            text TEXT
        )
    """)

    # Заявки
    c.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            deal_type TEXT CHECK(deal_type IN ('buy', 'sell')),
            coin TEXT,
            crypto_amount REAL,
            rub_amount INTEGER,
            wallet TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Таблица для бонусов за удачу
    c.execute("""
        CREATE TABLE IF NOT EXISTS luck_bonus (
            user_id INTEGER PRIMARY KEY,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS reserve_bonus (
        user_id INTEGER PRIMARY KEY,
        received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ← ВСТАВЬ СЮДА НОВУЮ ТАБЛИЦУ
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            username TEXT,
            first_name TEXT
        )
    """)

    conn.commit()
    conn.close()

# ======================= РЕКВИЗИТЫ ДЛЯ ПОКУПКИ =======================
def add_payment_requisites(card: str, bank: str, country: str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute(
        "INSERT INTO payment_requisites (card, bank, country) VALUES (?, ?, ?)",
        (card, bank, country)
    )
    conn.commit()
    conn.close()

def update_payment_requisites(id: int, card: str, bank: str, country: str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute(
        "UPDATE payment_requisites SET card=?, bank=?, country=? WHERE id=?",
        (card, bank, country, id)
    )
    conn.commit()
    conn.close()

def delete_payment_requisites(id: int):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("DELETE FROM payment_requisites WHERE id=?", (id,))
    conn.commit()
    conn.close()

def get_payment_requisites() -> tuple[str, str, str]:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT card, bank, country FROM payment_requisites ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return row if row else ("не заданы", "не задан", "не задана")


# ======================= АДРЕСА КРИПТЫ ДЛЯ ПРОДАЖИ =======================
def get_crypto_address(coin: str) -> str:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT address FROM crypto_addresses WHERE coin=?", (coin.upper(),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "не задан в админке!"

def set_crypto_address(coin: str, address: str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO crypto_addresses (coin, address) VALUES (?, ?)", (coin.upper(), address))
    conn.commit()
    conn.close()

# ======================= КОМИССИЯ =======================
def get_commission() -> int:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT commission FROM settings WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else DEFAULT_COMMISSION

def set_commission(commission: int):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("UPDATE settings SET commission = ? WHERE id = 1", (commission,))
    conn.commit()
    conn.close()

# ======================= ТЕКСТ ПОДДЕРЖКИ =======================
def get_support_text() -> str:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT text FROM support_text WHERE id=1")
    row = c.fetchone()
    conn.close()
    # если в базе нет текста, берём из env
    return row[0] if row else SUPPORT_CONTACT


def set_support_text(text: str):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO support_text (id, text) VALUES (1, ?)", (text,))
    conn.commit()
    conn.close()

# ======================= ЗАЯВКИ =======================
def add_deal(user_id: int, deal_type: str, coin: str, crypto_amount: float, rub_amount: int, wallet: str) -> int:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals (user_id, deal_type, coin, crypto_amount, rub_amount, wallet)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, deal_type, coin.upper(), crypto_amount, rub_amount, wallet))
    deal_id = c.lastrowid
    conn.commit()
    conn.close()
    return deal_id
async def notify_admins(deal_id: int, user_id: int, coin: str, crypto_amount: float, rub_amount: int, wallet: str):
    text = (
        f"🦆 <b>НОВАЯ ЗАЯВКА НА ПОКУПКУ</b>\n\n"
        f"📄 <b>Номер:</b> <code>#{deal_id}</code>\n"
        f"👤 <b>Пользователь:</b> <code>{user_id}</code>\n"
        f"💰 <b>К оплате:</b> <code>{rub_amount}</code> ₽\n"
        f"🏦 <b>Получит:</b> <code>{crypto_amount:.8f}</code> {coin}\n"
        f"💳 <b>Кошелёк:</b> <code>{wallet}</code>\n\n"
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f'Exception caught: {e}')
# ======================= РАССЫЛКА =======================
def get_all_users() -> list[int]:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM deals")
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]


# =======================игра в кости=======================
def has_luck_bonus(user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT 1 FROM luck_bonus WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def grant_luck_bonus(user_id: int):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO luck_bonus (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
# ======================= СОСТОЯНИЯ =======================
class BuyStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()
    waiting_for_proof = State()

class AdminRequisitesStates(StatesGroup):
    waiting_for_card = State()
    waiting_for_bank = State()
    waiting_for_country = State()
    
class AdminStates(StatesGroup):
    requisites = State()

class ExchangeStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()     
    waiting_for_proof = State()

class SellStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()
    waiting_for_proof = State()



# ======================= КЛАВИАТУРЫ =======================
# Главное меню
start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [  # первая строка
        InlineKeyboardButton(text="🤑 Купить", callback_data="buy"),
        InlineKeyboardButton(text="📈 Продать", callback_data="sell_menu")
    ],
    
    [  # вторая строка — одна кнопка
        InlineKeyboardButton(text="🎲 Проверь удачу и получи скидку (150₽)", callback_data="luck_discount")
    ],
    [  # третья
        InlineKeyboardButton(text="🧠 Ответь на 1 вопрос и получи скидку (100₽)", callback_data="quiz_discount")
    ],
    [  # четвертая
        InlineKeyboardButton(text="🧊 Подпишись на резерв (скидка 150₽)", url=RESERVE_URL)
    ],
    [  # пятая строка — две кнопки
        InlineKeyboardButton(text="💛 Отзывы клиентов", url=REVIEWS_URL),
        InlineKeyboardButton(text="💬 Чат", url=CHAT_URL)
    ],
    [  # новая строка — кнопка "Бонусы и полезное" внизу
        InlineKeyboardButton(text="🎁 Бонусы и полезное", callback_data="bonuses_menu")
    ],
])
def get_bonus_keyboard(user_id: int) -> InlineKeyboardMarkup:
    "✅ Проверь удачу и получи скидку (150₽)" if has_luck_bonus(user_id) else "🎲 Проверь удачу и получи скидку (150₽)"
    "✅ Подпишись на резерв (скидка 150₽)" if has_reserve_bonus(user_id) else "🧊 Подпишись на резерв (скидка 150₽)"

main_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Главное меню")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)
# Выбор валюты
buy_currency_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🟠 BTC (Bitcoin)", callback_data="buy_btc")],
    [InlineKeyboardButton(text="💎 ETH (Ethereum)", callback_data="buy_eth")],
    [InlineKeyboardButton(text="🟡 LTC (Litecoin)", callback_data="buy_ltc")],
    [InlineKeyboardButton(text="🕶️ XMR (Monero)", callback_data="buy_xmr")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
])


# Назад
back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="◀ Назад", callback_data="buy_currency_menu"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]
])
# Под заявкой
order_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Создать заявку", callback_data="create_order")],
    [InlineKeyboardButton(text="◀ Назад", callback_data="buy_currency_menu")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
])

def admin_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Реквизиты оплаты", callback_data="admin_requisites")],
        [InlineKeyboardButton(text="📝 Текст поддержки", callback_data="admin_support")],
        [InlineKeyboardButton(text="📊 Последние заявки", callback_data="admin_deals")],
        [InlineKeyboardButton(text="🔙 Выйти из админки", callback_data="main_menu")],
    ])


# ======================= /start =======================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    sticker_path = "media/start.tgs"
    if os.path.exists(sticker_path):
        await message.answer_sticker(FSInputFile(sticker_path))

    await message.answer(
        "<b>Уточка Обмен — ваш <i>обменник 24/7!</i></b>\n\n"
        "Уточка обменивает крипту моментально и по честному курсу 📈\n"
        "<u>Никаких задержек — карты всегда в наличии.</u>\n\n"
        "💰 Минимальные комиссии, максимум удобства.\n"
        "<b>🎉 Скидка 300₽ на первый обмен!</b>\n\n"
        f"<b>👩‍💻 Поддержка 24/7: {SUPPORT_CONTACT}</b>",
        parse_mode=ParseMode.HTML
    )

    await message.answer(

    "<b>Добро пожаловать в Уточка Обмен —</b> <i>обменник криптовалют 24/7!</i>\n\n"
    "<b>Обменивайте RUB на BTC, LTC и XMR</b> — быстро, удобно и безопасно 📈\n"
    "<u>Всё работает автоматически</u> — никаких задержек, только моментальные операции.\n\n"
    "Просто выберите монету и укажите сумму, а уточка всё сделает сама.\n\n"
    "<b>🎉 Скидка 300₽ на первый обмен!</b>\n\n"
    f"<b>👩‍💻 Поддержка 24/7: {SUPPORT_CONTACT}</b>\n\n"
    "<u>❗️Сними видео об \"Уточка Обмен\" в TikTok, Shorts, Reels, Клипах "
    "и получи 500₽ за каждую 1000 просмотров. Подробности узнавать в поддержке❗️</u>\n\n",
    reply_markup=start_keyboard,
    parse_mode=ParseMode.HTML
)


#ГЕн сделки
def generate_deal_id(length: int = 6, prefix: str = "25") -> int:
    """
    Генерация ID сделки.
    Начинается с prefix (по умолчанию '25'), общая длина length (по умолчанию 6).
    """
    digits_needed = length - len(prefix)
    random_digits = "".join(str(random.randint(0, 9)) for _ in range(digits_needed))
    return int(prefix + random_digits)


def add_deal(user_id, deal_type, coin, crypto_amount, total_rub, wallet, deal_id=None):
    """
    Добавление сделки в базу данных.
    :param user_id: ID пользователя Telegram
    :param deal_type: 'buy' или 'sell'
    :param coin: криптовалюта (например, BTC)
    :param crypto_amount: количество крипты
    :param total_rub: сумма в рублях
    :param wallet: адрес кошелька
    :param deal_id: ID сделки (если None — генерируется автоматически)
    :return: deal_id
    """
    if deal_id is None:
        deal_id = generate_deal_id()

    conn = sqlite3.connect("deals.db", check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()

    # создаём таблицу, если её нет
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            deal_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            deal_type TEXT,
            coin TEXT,
            crypto_amount REAL,
            total_rub REAL,
            wallet TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # сохраняем сделку
    cursor.execute("""
        INSERT INTO deals (deal_id, user_id, deal_type, coin, crypto_amount, total_rub, wallet)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (deal_id, user_id, deal_type, coin, crypto_amount, total_rub, wallet))

    conn.commit()
    conn.close()

    return deal_id 
# ======================= МЕНЮ =======================
@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text("<b>🦆 Главное меню</b>\n\nВыберите действие:", reply_markup=start_keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def buy_menu(callback: CallbackQuery):
    await callback.message.edit_text("<b>🌐 Выберите валюту, которую вы хотите купить:</b>", reply_markup=buy_currency_keyboard, parse_mode=ParseMode.HTML)
    await callback.answer()

# Обработчик кнопки "Назад" из меню ввода суммы
@dp.callback_query(F.data == "buy_currency_menu")
async def back_to_currency_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🌐 Выберите валюту, которую вы хотите купить:</b>",
        reply_markup=buy_currency_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy_currency(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.split("_")[1].upper()

    rate = buy_rates.get(currency)

    await state.update_data(selected_currency=currency, direction="buy", rate=rate or 0)

    warning = ""
    if not rate or rate <= 0:
        warning = "\n\n⚠️ Курс временно недоступен. Обмен может быть невозможен."
    
    

    await callback.message.edit_text(
    f"<b>🦆 Уточка готова к обмену!</b>\n\n"
    f"Введите сумму в <b>{currency}</b> или <b>RUB</b>:\n"
    f"<b>Пример:</b> <code>0.001</code>, <code>0,001</code> или <code>1500</code> 💸{warning}",
    reply_markup=back_keyboard,
    parse_mode=ParseMode.HTML
)


    await state.set_state(ExchangeStates.waiting_for_amount)
    await callback.answer()
    await callback.answer()

# ======================= ВВОД СУММЫ =======================
@dp.message(ExchangeStates.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    user_input = message.text.replace(",", ".").strip()
    try:
        amount = float(user_input)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗️Не удалось распознать сумму.", parse_mode=ParseMode.HTML)
        return  # остаёмся в состоянии

    data = await state.get_data()
    direction = data.get("direction", "buy")
    coin = data.get("selected_currency", "BTC").upper()
    commission = get_commission()

    # Выбираем правильный курс
    rate = buy_rates.get(coin) if direction == "buy" else sell_rates.get(coin)
    if not rate or rate <= 0:
        await message.answer("❗️Не удалось распознать сумму", parse_mode=ParseMode.HTML)
        return

    # При покупке: сумма ВСЕГДА в рублях (пользователь платит RUB)
    # При продаже: сумма может быть в крипте (< 1000 считаем как крипту)
    if direction == "buy" or amount >= 1000:
        rub_amount = round(amount)
        # Комиссия добавляется к сумме
        total_to_pay = round(rub_amount * (1 + commission / 100))
        crypto_amount = round(total_to_pay / rate, 8)
    else:
        # Продажа: сумма в крипте
        crypto_amount = round(amount, 8)
        base_rub = round(crypto_amount * rate)
        total_to_pay = round(base_rub * (1 + commission / 100))

    # Проверка минималки в рублях
    if rub_amount < MIN_RUB:
        await message.answer(
            f"⚠️ Сумма слишком маленькая!\n"
            f"Минимальная сумма обмена — *{MIN_RUB}₽*\n\n"
            f"Попробуйте указать сумму побольше 🦆💰",
            parse_mode="Markdown"
        )
        return  # остаёмся в состоянии

    # Проверка минималки в крипте
    min_crypto = MIN_CRYPTO.get(coin, 0.001)
    if crypto_amount + 1e-8 < min_crypto:
        await message.answer(
            f"⚠️ Сумма слишком маленькая!\n"
            f"Минимально — *{min_crypto} {coin}*\n\n"
            f"Попробуйте указать сумму побольше 🦆💰",
            parse_mode="Markdown"
        )
        return  # остаёмся в состоянии

    # Правильное округление и форматирование
    if coin in ["BTC", "ETH"]:
      crypto_rounded = round(crypto_amount, 6)  # 6 знаков
      crypto_fmt = f"{crypto_rounded:.6f}".rstrip('0').rstrip('.')  # убираем лишние нули
    else:
      crypto_rounded = round(crypto_amount, 6)
      crypto_fmt = f"{crypto_rounded:.6f}".rstrip('0').rstrip('.')

    total_rub = total_to_pay  # с учётом комиссии

    await state.update_data(
    coin=coin,
    crypto_amount=crypto_rounded,
    crypto_fmt=crypto_fmt,
    rub_amount=rub_amount,
    total_rub=total_rub,
    rate=rate,
    commission=commission
)

    if direction == "buy":
    # форматируем рубли с разделителем тысяч
      rub_fmt = f"{total_rub:,}".replace(",", " ")
      commission_info = f"\n<i>💰 Комиссия бота: {commission}%</i>" if commission > 0 else ""

    text = (
    f"<b>💵 На ваш счёт поступит:</b> <code>{crypto_fmt} {coin}</code>\n"
    f"<b>📈 По текущему курсу:</b> <code>{rub_fmt} ₽</code>{commission_info}\n\n"
    f"<i>🎁 Активированные скидки:</i>\n\n"
    f"📗 Ваш первый обмен у нас!\n"
    f"📗 Скидка за удачный бросок!\n"
    f"📗 Праздничная скидка (всем)!\n\n"
    f"<b>💰 Итого к оплате: <u>{rub_fmt} ₽</u></b>\n\n"
    f"🏄🏼‍♀️ Для продолжения расчётов\n"
    f"<b>🪪 Введите адрес {coin} ниже ⬇️</b>"
)


    await message.answer(text, reply_markup=back_keyboard, parse_mode=ParseMode.HTML)
    await state.set_state(ExchangeStates.waiting_for_wallet)
 

# ======================= ВВОД АДРЕСА =======================
@dp.message(ExchangeStates.waiting_for_wallet)
async def process_wallet(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Пришлите <b>текстом</b> адрес кошелька.")
        return

    wallet = message.text.strip()

    if len(wallet) < 25:
        await message.answer("❌ Адрес слишком короткий. Проверьте и пришлите полный адрес.")
        return

    data = await state.get_data()
    direction = data.get("direction", "buy")

    if direction != "buy":
        await message.answer("Ошибка. Начните заново.", reply_markup=main_reply_keyboard)
        await state.clear()
        return

    coin = data.get("coin").upper()
    crypto_fmt = data.get("crypto_fmt")
    total_rub = data.get("total_rub")

    await state.update_data(wallet=wallet)

# форматируем число с разделителем тысяч
    formatted_rub = f"{int(total_rub):,}".replace(",", " ")

    text = (
    f"<b>🦆 Информация по вашему обмену ⬇️</b>\n\n"
    f"<b>💰 К оплате:</b> <b>{formatted_rub} ₽</b>\n\n"
    f"<b>💳 Кошелёк для зачисления:</b> <code>{wallet}</code>\n\n"
    f"<b>🏦 Вы получите: <b>{crypto_fmt}</b> {coin}</b>\n\n"
    f"<b>⏱️ Данные для оплаты поступят в течение 5 минут.</b>\n"
    f"<b>⏱️ Как только перевод будет подтверждён, криптовалюта отправится на ваш адрес — обычно это занимает не более 10 минут</b>"
)



    await message.answer(text, reply_markup=confirm_keyboard, parse_mode=ParseMode.HTML)
# ======================= СОЗДАНИЕ ЗАЯВКИ =======================
# Клавиатура после создания заявки

# Клавиатура после ввода адреса (для создания заявки)
confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Создать заявку", callback_data="create_order")],  # по центру
    [
        InlineKeyboardButton(text="◀ Назад", callback_data="back_to_amount"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]
])
# Клавиатура "Оплатил" / "Отменить заявку"
payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Оплатил", callback_data="paid")],
    [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_order")]
])


@dp.callback_query(F.data == "create_order")
async def create_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    coin = data.get("coin") or data.get("selected_currency", "BTC").upper()
    crypto_amount = data.get("crypto_amount")
    total_rub = data.get("total_rub") or data.get("rub_amount")
    wallet = data.get("wallet")
    crypto_fmt = data.get("crypto_fmt", f"{crypto_amount:.8f}")

    if not all([coin, crypto_amount is not None, total_rub is not None, wallet]):
        await callback.message.edit_text(
            "❌ Ошибка при создании заявки. Данные неполные.\nНачните заново.",
            reply_markup=main_reply_keyboard,
            parse_mode=ParseMode.HTML
        )
        await state.clear()
        await callback.answer()
        return

    direction = data.get("direction", "buy")
    deal_type = "buy" if direction == "buy" else "sell"

    # Создаём заявку
    deal_id = generate_deal_id()
    await state.update_data(deal_id=deal_id, requisites_sent=False)
    # Создаём заявку в базе
    add_deal(user_id, deal_type, coin, crypto_amount, total_rub, wallet, deal_id=deal_id)
# форматируем число с разделителем тысяч
    formatted_rub = f"{int(total_rub):,}".replace(",", " ")

    text = (
    f"<b>📝 Заявка №{deal_id} успешно создана</b>\n\n"
    f"💸 К оплате: <b>{formatted_rub} ₽</b>\n"
    f"💎 Вы получите: <b>{crypto_fmt} {coin}</b>\n"
    f"🏠 Адрес для получения: <code>{wallet}</code>\n\n"
    f"⌛️ Подготавливаем платежные данные — обычно это занимает несколько минут."
)


    # Стикер ожидания
    # Стикер ожидания
    sticker_msg = None
    waiting_sticker_path = "media/reki.tgs"
    if os.path.exists(waiting_sticker_path):
       sticker_msg = await callback.message.answer_sticker(FSInputFile(waiting_sticker_path))

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML)

    # Уведомляем админов
    await notify_admins(deal_id, user_id, coin, crypto_amount, total_rub, wallet)

    await callback.answer()

    # Задержка перед реквизитами
    delay = random.randint(10,20)
    await asyncio.sleep(delay)

    current_data = await state.get_data()
    if current_data.get("deal_id") != deal_id or current_data.get("requisites_sent"):
        return
   
    # удаляем стикер, если он был
    if sticker_msg:
     try:
         await sticker_msg.delete()
     except Exception as e:
        print(f"Не удалось удалить стикер: {e}")
    # Отправляем реквизиты
    get_payment_requisites()

    card, bank, country = get_payment_requisites()

    # форматируем число с разделителем тысяч
    # форматируем число с разделителем тысяч
    formatted_rub = f"{int(total_rub):,}".replace(",", " ")

    payment_text = (
    f"<b>🏦 Платёжные данные по заявке №{deal_id}</b>\n\n"
    f"<b>Вам необходимо произвести оплату в течение 15 минут!</b>\n\n"
    f"<b>⚠️ Обратите внимание:</b>\n"
    f"• Проверьте внимательно <u>номер карты</u>, что указан ниже!\n"
    f"• Проверьте внимательно <u>сумму</u>, что указана ниже!\n\n"
    f"💳 <b>Реквизиты:</b> <code>{card}</code>\n"
    f"🏛 <b>Банк:</b> {bank}\n"
    f"💸 <b>Сумма к оплате:</b> <code>{formatted_rub} ₽</code>\n"
    f"🌍 <b>Страна перевода:</b> {country}\n\n"
    f"👩‍💻 <b>Поддержка 24/7:</b> @duckobmen"
)


    try:
        await bot.send_message(user_id, payment_text, reply_markup=payment_keyboard, parse_mode=ParseMode.HTML)
        await state.update_data(requisites_sent=True)
    except Exception as e:
        print(f"Ошибка отправки реквизитов пользователю {user_id}: {e}")

    # Больше ничего не делаем — уведомление админам уже было
#Прием чека
@dp.callback_query(F.data == "paid")
async def request_proof(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "<b>📸 Пришлите чек об оплате</b>\n\n"
        "Поддерживаемые форматы:\n"
        "• Фото (PNG, JPG)\n"
        "• PDF документ\n"
        "• Любой другой файл с чеком\n\n"
        "<i>🧾 После отправки чека оператор проверит платёж в течение 15 минут.</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(BuyStates.waiting_for_proof)
    await callback.answer()

#Приём чека (фото или документ)
@dp.message(BuyStates.waiting_for_proof, F.photo | F.document)
async def receive_proof(message: Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("deal_id")
    user_id = message.from_user.id
    coin = data.get("coin")
    data.get("crypto_amount")
    total_rub = data.get("total_rub")
    wallet = data.get("wallet")
    crypto_fmt = data.get("crypto_fmt")

    # Определяем, что прислали — фото или документ
    if message.photo:
        file_id = message.photo[-1].file_id  # лучшее качество
        send_method = bot.send_photo
    elif message.document:
        file_id = message.document.file_id
        send_method = bot.send_document
    else:
        return

    # Отправляем чек админам с полной инфой по заявке
    caption = (
        f"🧾 <b>ЧЕК ПО ЗАЯВКЕ #{deal_id}</b>\n\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"💰 К оплате: <code>{total_rub}</code> ₽\n"
        f"🏦 Получит: <code>{crypto_fmt}</code> {coin}\n"
        f"💳 Кошелёк: <code>{wallet}</code>\n\n"
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"Ожидает подтверждения оплаты"
    )

    for admin_id in ADMIN_IDS:
        try:
            await send_method(admin_id, file_id, caption=caption, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f'Exception caught: {e}')

    ## 1. Отправляем стикер ok.tgs
    ok_sticker_path = "media/ok.tgs"
    if os.path.exists(ok_sticker_path):
        await message.answer_sticker(FSInputFile(ok_sticker_path))
    else:
        await message.answer("✅")  # fallback на эмодзи, если файла нет

    # 2. Отправляем текстовое сообщение с главным меню
    await message.answer(
    f"{THANK_YOU_TEXT}\n\n"
    f"🧑‍💻 <b>Контакт оператора:</b> {OPERATOR_CONTACT}\n\n"
    f"{GOOD_EXCHANGE_TEXT}",
    reply_markup=start_keyboard,
    parse_mode=ParseMode.HTML
)



    await state.clear()

#Отмена заявки
@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("deal_id")

    # Можно удалить из БД или просто пометить как отменённую
    # Пока просто уведомим админов
    if deal_id:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, f"❌ Заявка #{deal_id} отменена пользователем {callback.from_user.id}")
            except Exception as e:
                print(f'Exception caught: {e}')

    await callback.message.edit_text(
        "❌ Заявка отменена.\n\nВы вернулись в меню покупки.",
        reply_markup=buy_currency_keyboard,
        parse_mode=ParseMode.HTML
    )
    await state.clear()
    await callback.message.answer("Выберите действие:", reply_markup=main_reply_keyboard)


# ======================= ПРОДАЖА КРИПТЫ =======================

sell_currency_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🟠 BTC (Bitcoin)", callback_data="sell_btc")],
    [InlineKeyboardButton(text="💎 ETH (Ethereum)", callback_data="sell_eth")],
    [InlineKeyboardButton(text="🟡 LTC (Litecoin)", callback_data="sell_ltc")],
    [InlineKeyboardButton(text="🕶️ XMR (Monero)", callback_data="sell_xmr")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
])


# Клавиатура выбора банка
sell_bank_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🏦 Тинькофф", callback_data="bank_tinkoff")],
    [InlineKeyboardButton(text="🏦 Сбер", callback_data="bank_sber")],
    [InlineKeyboardButton(text="🚀 СБП", callback_data="bank_sbp")],
    [InlineKeyboardButton(text="◀ Назад", callback_data="sell_back_to_amount")]
])

# ======================= КНОПКА "ПРОДАТЬ" =======================
@dp.message(F.text == "📈 Продать")
async def sell_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "<b>🦆 Выберите криптовалюту, которую хотите продать:</b>",
        reply_markup=sell_currency_keyboard,
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(F.data == "sell_menu")
async def sell_menu_inline(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "<b>🦆 Выберите криптовалюту, которую хотите продать:</b>",
        reply_markup=sell_currency_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

# ======================= ВЫБОР МОНЕТЫ =======================
@dp.callback_query(F.data.in_(["sell_btc", "sell_eth", "sell_ltc", "sell_usdt", "sell_xmr"]))
async def process_sell_currency(callback: CallbackQuery, state: FSMContext):
    token = callback.data.split("_", 1)[1].upper()
    currency = token
    rate = sell_rates.get(currency, 0.0)

    await state.update_data(selected_currency=currency, direction="sell", rate=rate)

    warning = "" if rate > 0 else "\n\n❗️Не удалось распознать курс для этой валюты"

    await callback.message.edit_text(
        f"<b>🦆 Уточка готова к обмену!</b>\n\n"
        f"Введите сумму в <b>{currency}</b> или <b>RUB</b>:\n"
        f"<b>Пример:</b> <code>0.001</code>, <code>0,001</code> или <code>1500</code> 💸{warning}",
        reply_markup=sell_back_keyboard_currency,  # ← клавиатура «Назад к валютам»
        parse_mode=ParseMode.HTML
    )
    await state.set_state(SellStates.waiting_for_amount)
    await callback.answer()


# Клавиатура "Назад" для продажи — возврат к выбору валюты
sell_back_keyboard_currency = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="◀ Назад", callback_data="sell_back_to_currency"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]
])

# Клавиатура "Назад" для продажи — возврат к вводу суммы
sell_back_keyboard_amount = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="◀ Назад", callback_data="sell_back_to_amount"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]
])



@dp.callback_query(F.data == "sell_back_to_currency")
async def back_to_sell_currency_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🌐 Выберите валюту, которую вы хотите продать:</b>",
        reply_markup=sell_currency_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "sell_back_to_amount")
async def back_to_sell_amount(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    coin = data.get("selected_currency")
    await callback.message.edit_text(
        f"<b>🦆 Продажа {coin}</b>\n\n"
        f"Введите сумму заново:\n\n"
        f"<b>Примеры:</b> <code>0.001</code>, <code>0,005</code> или <code>1500</code> рублей\n\n",
        reply_markup=sell_back_keyboard_currency,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ======================= ВВОД СУММЫ (ПРОДАЖА) =======================
MIN_RUB = 1500  # новый минимум для рубля

@dp.message(SellStates.waiting_for_amount)
async def process_sell_amount(message: Message, state: FSMContext):
    user_input = message.text.replace(",", ".").strip()
    try:
        amount = float(user_input)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❗️Не удалось распознать сумму", parse_mode=ParseMode.HTML)
        return

    data = await state.get_data()
    coin = data["selected_currency"].upper()
    rate = data["rate"]
    commission = get_commission()

    # Автоопределение: если >= MIN_RUB → это рубли, иначе → крипта
    # При продаже: комиссия ВЫЧИТАЕТСЯ из суммы, которую получит пользователь
    # rub_amount — сумма ДО комиссии (сколько стоит крипта по курсу)
    # total_rub — сумма ПОСЛЕ комиссии (что пользователь реально получит)
    if amount >= MIN_RUB:
        rub_amount = int(round(amount))  # рубли, которые пользователь ХОЧЕТ получить
        # Комиссия уменьшает то, что он получит: total_rub = rub_amount * (1 - commission)
        total_rub = int(round(rub_amount * (1 - commission / 100)))
        # Крипта рассчитывается от НЕТТО-суммы (что реально получит)
        crypto_amount = total_rub / rate
    else:
        crypto_amount = amount
        base_rub = int(round(crypto_amount * rate))  # округляем до целого
        # При продаже комиссия вычитается из суммы
        total_rub = int(round(base_rub * (1 - commission / 100)))
        rub_amount = total_rub  # для консистентности: храним то, что реально получит

    # Минималки — проверяем ПОСЛЕ комиссии (сколько реально получит)
    if total_rub < MIN_RUB:
        await message.answer(f"⚠️ Сумма слишком маленькая!\n"
            f"Минимальная сумма обмена — *{MIN_RUB}₽*\n\n"
            f"Попробуйте указать сумму побольше 🦆💰",
            parse_mode="Markdown"
        )
        return  # остаёмся в состоянии
    min_crypto = MIN_CRYPTO.get(coin, 0.001)
    if crypto_amount < min_crypto:
        await message.answer(
            f"⚠️ Сумма слишком маленькая!\n"
            f"Минимально — *{min_crypto} {coin}*\n\n"
            f"Попробуйте указать сумму побольше 🦆💰",
            parse_mode="Markdown"
        )
        return  # остаёмся в состоянии


    # Форматирование крипты
    if coin in ["BTC", "ETH"]:
       crypto_rounded = round(crypto_amount, 8)
       crypto_fmt = f"{crypto_rounded:.8f}".rstrip("0").rstrip(".")
    else:
       crypto_rounded = round(crypto_amount, 2)
       crypto_fmt = (
        f"{crypto_rounded:.2f}".rstrip("0").rstrip(".")
        if "." in f"{crypto_rounded:.2f}"
        else f"{int(crypto_rounded)}"
    )


    await state.update_data(
    crypto_amount=crypto_rounded,
    crypto_fmt=crypto_fmt,
    rub_amount=rub_amount,
    total_rub=total_rub,
    commission=commission
)
    rub_fmt = f"{total_rub:,}".replace(",", " ")
    commission_info = f"\n<i>💰 Комиссия бота: {commission}%</i>" if commission > 0 else ""

    text = (
    f"<b>💵 Вы получите на карту:</b> <b><code>{rub_fmt} ₽</code></b>{commission_info}\n"
    f"<b>📈 По текущему курсу:</b> <b><code>{crypto_fmt} {coin}</code></b>\n\n"
    f"🏄🏼‍♀️ Для продолжения расчётов\n"
    f"🪪 Укажите номер карты или номер телефона СБП и банк ⬇️"
)



    await message.answer(text, reply_markup=sell_back_keyboard_amount, parse_mode=ParseMode.HTML)
    await state.set_state(SellStates.waiting_for_wallet)



# ======================= ВЫБОР БАНКА =======================
@dp.message(SellStates.waiting_for_wallet)
async def process_sell_wallet(message: Message, state: FSMContext):
    card_or_phone = message.text.strip()
    if len(card_or_phone) < 8:
        await message.answer("❌ Укажите корректный номер карты или телефона для СБП.")
        return

    data = await state.get_data()
    coin = data.get("selected_currency")
    crypto_fmt = data.get("crypto_fmt")
    total_rub = data.get("total_rub", data.get("rub_amount"))

    await state.update_data(wallet=card_or_phone)

    rub_fmt = f"{total_rub:,}".replace(",", " ")

    text = (
    f"🦆 <b>Информация по вашему обмену</b>\n\n"
    f"💰 Вы отправляете: <b>{crypto_fmt} {coin}</b>\n"
    f"💳 Карта для зачисления: <code>{card_or_phone}</code>\n"
    f"🏦 Вы получите: <u><b>{rub_fmt}</b></u> ₽\n\n"
    f"⬇️ Нажмите кнопку ниже, чтобы получить адрес для отправки криптовалюты"
)






    confirm_keyboard_sell = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Получить адрес для отправки", callback_data="create_sell_order")],
    [
        InlineKeyboardButton(text="◀ Назад", callback_data="sell_back_to_amount"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]
])

    await message.answer(text, reply_markup=confirm_keyboard_sell, parse_mode=ParseMode.HTML)


@dp.callback_query(F.data == "create_sell_order")
async def create_sell_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    coin = data.get("selected_currency").upper()
    crypto_amount = data.get("crypto_amount")
    rub_amount = data.get("rub_amount")
    wallet = data.get("wallet")  # карта/телефон клиента
    crypto_fmt = data.get("crypto_fmt", f"{crypto_amount:.8f}")

    if not all([coin, crypto_amount, rub_amount, wallet]):
        await callback.answer("Ошибка данных", show_alert=True)
        return

    # Создаём заявку
    deal_id = add_deal(user_id, "sell", coin, crypto_amount, rub_amount, wallet)
    await state.update_data(deal_id=deal_id, requisites_sent=False)

    text = (
    f"<b>📝 Заявка №{deal_id} успешно создана</b>\n\n"
    f"💰 Вы отправляете: <b>{crypto_fmt} {coin}</b>\n"
    f"💳 На карту: <code>{wallet}</code>\n"
    f"🏦 Получите: <b>{rub_amount} ₽</b>\n\n"
    f"⌛️ Подготавливаем адрес для отправки..."
)


    if os.path.exists("media/reki.tgs"):
        await callback.message.answer_sticker(FSInputFile("media/reki.tgs"))

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML)

    # Уведомление админам
    notify_text = (
        f"🦆 <b>НОВАЯ ЗАЯВКА НА ПРОДАЖУ</b>\n\n"
        f"📄 Номер: <code>#{deal_id}</code>\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"💰 Отправляет: <code>{crypto_fmt}</code> {coin}\n"
        f"🏦 Получит: <code>{rub_amount}</code> ₽\n"
        f"💳 Карта: <code>{wallet}</code>\n\n"
        f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, notify_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f'Exception caught: {e}')

    await callback.answer()

    # Задержка
    delay = random.randint(5,7)
    await asyncio.sleep(delay)

    current_data = await state.get_data()
    if current_data.get("deal_id") != deal_id or current_data.get("requisites_sent"):
        return

    # Отправляем АДРЕС КРИПТЫ, а не банковские реквизиты!
    crypto_address = get_crypto_address(coin)

    if not crypto_address or crypto_address == "не задан в админке!":
        await bot.send_message(user_id, "⚠️ Адрес для приёма временно недоступен. Обратитесь в поддержку.")
        return

    payment_text = (
    f"📝 <b>Адрес для отправки {coin}</b>\n"
    f"💎 Отправьте: <code>{crypto_fmt}</code> {coin}\n"
    f"📍 На адрес: <code>{crypto_address}</code>\n"
    f"💰 После подтверждения транзакции на карту поступит: <b><code>{rub_amount}</code>₽</b>\n"
    f"💳 Номер карты: <code>{wallet}</code>\n"
    f"⏱️ Обработка обычно занимает от 10 до 30 минут после подтверждения в сети.\n\n"
    f"👩‍💻 Поддержка 24/7: @duckobmen_support"
)

    await bot.send_message(user_id, payment_text, reply_markup=payment_keyboard, parse_mode=ParseMode.HTML)
    await state.update_data(requisites_sent=True)

# ======================= ДЛЯ ПРОДАЖИ: КНОПКА "ОПЛАТИЛ" (теперь значит "Отправил крипту") =======================
# Важно: используем ту же кнопку "paid", что и в покупке, но клавиатура payment_keyboard одинаковая для обоих направлений

@dp.callback_query(F.data == "paid")
async def request_proof_sell(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    direction = data.get("direction")

    # Если это продажа — показываем свой текст
    if direction == "sell":
        await callback.message.edit_text(
            "<b>📸 Подтвердите отправку криптовалюты</b>\n\n"
            "Пришлите, пожалуйста:\n"
            "• TXID (хэш транзакции) — просто текстом\n"
            "• Скриншот отправки из кошелька\n"
            "• Фото или PDF с подтверждением\n\n"
            "<i>После поступления средств на наш адрес — выплата на вашу карту будет произведена автоматически в течение 5–15 минут.</i>",
            parse_mode=ParseMode.HTML
        )
        await state.set_state(SellStates.waiting_for_proof)  # Используем отдельное состояние для продажи
        await callback.answer()
        return

    # Если это покупка — можно оставить старый обработчик или перенаправить, но здесь мы обрабатываем только sell
    # (старый обработчик для buy можно оставить отдельно выше)


# ======================= ДЛЯ ПРОДАЖИ: ПРИЁМ ПОДТВЕРЖДЕНИЯ ОТПРАВКИ КРИПТЫ =======================
@dp.message(SellStates.waiting_for_proof, F.photo | F.document | F.text)
async def receive_proof_sell(message: Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("deal_id")
    user_id = message.from_user.id
    coin = data.get("selected_currency").upper()
    crypto_amount = data.get("crypto_amount")
    crypto_fmt = data.get("crypto_fmt", f"{crypto_amount:.8f}" if crypto_amount else f"{crypto_amount:.8f}")
    rub_amount = data.get("rub_amount") or data.get("total_rub")
    wallet = data.get("wallet")  # здесь wallet — это карта/телефон клиента

    # Определяем тип контента
    if message.photo:
        file_id = message.photo[-1].file_id
        send_method = bot.send_photo
    elif message.document:
        file_id = message.document.file_id
        send_method = bot.send_document
    elif message.text:
        file_id = None
        send_method = None
        txid = message.text.strip()
    else:
        return

    ## форматируем рубли с разделителем тысяч
    formatted_rub = f"{int(rub_amount):,}".replace(",", " ")

    caption = (
    f"🧾 <b>ПОДТВЕРЖДЕНИЕ ОТПРАВКИ #{deal_id} (ПРОДАЖА)</b>\n\n"
    f"👤 Пользователь: <code>{user_id}</code>\n"
    f"💰 Отправляет: <b>{crypto_fmt}</b> {coin}\n"
    f"🏦 Получит: <u><b>{formatted_rub}</b></u> ₽\n"
    f"💳 На карту/СБП: <code>{wallet}</code>\n\n"
    f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    f"Ожидает подтверждения поступления {coin}"
)

    # Если прислан текст (TXID) — добавляем его в подпись
    if message.text:
        caption += f"\n\n📄 <b>TXID:</b>\n<code>{txid}</code>"

    # Отправляем админам
    for admin_id in ADMIN_IDS:
        try:
            if file_id:
                await send_method(admin_id, file_id, caption=caption, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(admin_id, caption, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")

    # Ответ пользователю
    ok_sticker_path = "media/ok.tgs"
    if os.path.exists(ok_sticker_path):
        await message.answer_sticker(FSInputFile(ok_sticker_path))
    else:
        await message.answer("✅")

    await message.answer(
        "<b>✅ Подтверждение отправки получено!</b>\n\n"
        "Как только средства поступят — выплата на вашу карту будет произведена автоматически.\n"
        "Обычно это занимает <b>5–15 минут</b>.\n\n"
        "🦆 Спасибо за обмен!",
        reply_markup=start_keyboard,
        parse_mode=ParseMode.HTML
    )

    await state.clear()


# ======================= ОТМЕНА ЗАЯВКИ (ОБЩАЯ, НО РАБОТАЕТ И ДЛЯ ПРОДАЖИ) =======================
@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    deal_id = data.get("deal_id")
    direction = data.get("direction", "buy")

    # Уведомление админам с указанием направления
    direction_text = "ПОКУПКА" if direction == "buy" else "ПРОДАЖА"
    if deal_id:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"❌ Заявка #{deal_id} ({direction_text}) отменена пользователем <code>{callback.from_user.id}</code>",
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                print(f'Exception caught: {e}')

    await callback.message.edit_text(
        "❌ Заявка успешно отменена.\n\nВы вернулись в главное меню.",
        reply_markup=start_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()
    await state.clear()
    
# ======================= АДМИНКА =======================

class AdminStates(StatesGroup):
    waiting_payment_requisites = State()     # реквизиты для покупки
    waiting_crypto_address = State()         # адрес крипты
    waiting_broadcast = State()              # рассылка
    waiting_link = State()                   # редактирование ссылок
    waiting_commission = State()             # редактирование комиссии
    main = State()

def _get_env(key: str, default: str = "") -> str:
    return read_env_var(key, default)
def admin_main_menu():
    get_commission()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Реквизиты оплаты (покупка)", callback_data="admin_requisites")],
        [InlineKeyboardButton(text="🪙 Адреса приёма крипты (продажа)", callback_data="admin_crypto_addresses")],
        [InlineKeyboardButton(text="💰 Комиссия", callback_data="admin_commission")],
        [InlineKeyboardButton(text="📊 Последние заявки", callback_data="admin_deals")],
        [InlineKeyboardButton(text="📢 Рассылка пользователям", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 Выйти", callback_data="main_menu")],
    ])


@dp.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    # очищаем любое текущее состояние, чтобы команда всегда срабатывала
    await state.clear()

    if message.from_user.id not in ADMIN_IDS:
        # Тихо игнорируем, если не админ (или можно отправить "Доступ запрещён")
        return

    # переводим в главное состояние админки
    await state.set_state(AdminStates.main)

    await message.answer(
        "🔑 <b>Вы вошли в админку</b>\n\nВыберите действие:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_main_menu()
    )


@dp.callback_query(F.data == "admin_enter")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("⛔ Доступ запрещён", show_alert=True)
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
        reply_markup=admin_main_menu(),
        parse_mode=ParseMode.HTML
    )

# ======================= РЕКВИЗИТЫ ОПЛАТЫ (ПОКУПКА) =======================
admin_back_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="◀ Назад", callback_data="admin_main_menu"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ]
])
# Возврат в админ-меню
@dp.callback_query(F.data == "admin_main_menu")
async def back_to_admin_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.main)   # возвращаем в главное состояние админки
    await callback.message.edit_text(
        "🔑 <b>Вы снова в админке</b>\n\nВыберите действие:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_main_menu()
    )
    await callback.answer()


# Возврат в главное меню (обычное)
@dp.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()   # очищаем состояние, чтобы выйти из админки
    await callback.message.edit_text(
        "🏠 Главное меню",
        parse_mode=ParseMode.HTML,
        reply_markup=start_keyboard   # твоя клавиатура для обычных пользователей
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_requisites")
async def admin_payment_requisites(callback: CallbackQuery, state: FSMContext):
    card, bank, country = get_payment_requisites()
    await callback.message.edit_text(
        f"💳 <b>Реквизиты для оплаты (покупка)</b>\n\n"
        f"Текущие:\n"
        f"💳 Карта/телефон: {card}\n"
        f"🏛 Банк: {bank}\n"
        f"🌍 Страна: {country}\n\n"
        f"Введите новый <b>номер карты/телефон</b>:",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_back_keyboard
    )
    await state.set_state(AdminRequisitesStates.waiting_for_card)
    await callback.answer()


@dp.message(AdminRequisitesStates.waiting_for_card)
async def admin_set_card(message: Message, state: FSMContext):
    await state.update_data(card=message.text.strip())
    await message.answer("🏛 Введите <b>банк</b>:", parse_mode=ParseMode.HTML,
                         reply_markup=admin_back_keyboard)
    await state.set_state(AdminRequisitesStates.waiting_for_bank)


@dp.message(AdminRequisitesStates.waiting_for_bank)
async def admin_set_bank(message: Message, state: FSMContext):
    await state.update_data(bank=message.text.strip())
    await message.answer("🌍 Введите <b>страну перевода</b>:", parse_mode=ParseMode.HTML,
                         reply_markup=admin_back_keyboard)
    await state.set_state(AdminRequisitesStates.waiting_for_country)


@dp.message(AdminRequisitesStates.waiting_for_country)
async def admin_set_country(message: Message, state: FSMContext):
    data = await state.get_data()
    card = data.get("card")
    bank = data.get("bank")
    country = message.text.strip()

    add_payment_requisites(card, bank, country)

    await message.answer(
        f"✅ Реквизиты сохранены!\n\n"
        f"💳 Карта/телефон: <code>{card}</code>\n"
        f"🏛 Банк: {bank}\n"
        f"🌍 Страна: {country}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_main_menu()
    )
    await state.clear()



# ======================= АДРЕСА КРИПТЫ (ПРОДАЖА) =======================
@dp.callback_query(F.data == "admin_crypto_addresses")
async def admin_crypto_addresses(callback: CallbackQuery):
    coins = ["BTC", "ETH", "LTC", "USDT", "XMR"]  # ← Добавили ETH
    text = "<b>🪙 Адреса приёма крипты (продажа):</b>\n\n"
    for coin in coins:
        addr = get_crypto_address(coin)
        text += f"<b>{coin}:</b> <code>{addr}</code>\n"

    # Кнопки изменения — теперь с ETH
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Изменить {coin}", callback_data=f"crypto_edit_{coin.lower()}") for coin in coins]
    ] + [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_enter")]])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@dp.callback_query(F.data.startswith("crypto_edit_"))
async def crypto_edit_start(callback: CallbackQuery, state: FSMContext):
    coin = callback.data.split("_")[2].upper()
    current = get_crypto_address(coin)
    await state.update_data(edit_coin=coin)
    await callback.message.edit_text(
        f"<b>Изменение адреса {coin}</b>\n\n"
        f"Текущий адрес:\n<code>{current}</code>\n\n"
        f"Введите новый адрес:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_crypto_addresses")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_crypto_address)

@dp.message(AdminStates.waiting_crypto_address)
async def save_crypto_address(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    coin = data.get("edit_coin")
    address = message.text.strip()
    set_crypto_address(coin, address)
    await message.answer(f"✅ Адрес для {coin} обновлён!", reply_markup=admin_main_menu(), parse_mode=ParseMode.HTML)
    await state.clear()

# ======================= КОМИССИЯ =======================
@dp.callback_query(F.data == "admin_commission")
async def admin_commission(callback: CallbackQuery, state: FSMContext):
    current = get_commission()
    await callback.message.edit_text(
        f"<b>💰 Настройка комиссии</b>\n\n"
        f"Текущая комиссия: <b>{current}%</b>\n\n"
        f"Введите новое значение комиссии (в процентах, от 0 до 100):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_enter")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_commission)

@dp.message(AdminStates.waiting_commission)
async def process_commission(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        commission = int(message.text.strip().replace(',', '.').replace('%', ''))
        if commission < 0 or commission > 100:
            await message.answer("❌ Комиссия должна быть от 0 до 100%")
            return
        set_commission(commission)
        await message.answer(
            f"<b>✅ Комиссия обновлена: {commission}%</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=admin_main_menu()
        )
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число от 0 до 100.")
    await state.clear()

# ======================= ПОСЛЕДНИЕ ЗАЯВКИ =======================
@dp.callback_query(F.data == "admin_deals")
async def admin_deals(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("""
        SELECT id, user_id, deal_type, coin, rub_amount, wallet, status, created_at 
        FROM deals 
        ORDER BY id DESC 
        LIMIT 15
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        text = "📭 Заявок пока нет."
    else:
        text = "<b>📊 Последние 15 заявок:</b>\n\n"
        for r in rows:
            direction = "Покупка" if r[2] == "buy" else "Продажа"
            text += (
                f"#{r[0]} | {r[1]} | {direction} {r[3]}\n"
                f"💰 {r[4]} ₽ | {r[6]}\n"
                f"💳 <code>{r[5]}</code>\n"
                f"{r[7][:16]}\n\n"
            )

    await callback.message.edit_text(text, reply_markup=admin_main_menu(), parse_mode=ParseMode.HTML)

# ======================= ССЫЛКИ =======================
LINK_FIELDS = {
    "rates": "RATES_URL",
    "sell_btc": "SELL_BTC_URL",
    "news_channel": "NEWS_CHANNEL",
    "operator": "OPERATOR_CONTACT",
    "operator2": "OPERATOR2_CONTACT",
    "operator3": "OPERATOR3_CONTACT",
    "work_operator": "WORK_OPERATOR",
}

@dp.callback_query(F.data == "admin_links")
async def admin_links(callback: CallbackQuery):
    rates_url = _get_env("RATES_URL", "https://t.me/duckobmen")
    sell_btc_url = _get_env("SELL_BTC_URL", "https://t.me/duckobmen")
    news_channel = _get_env("NEWS_CHANNEL", "@duckobmen")
    operator = _get_env("OPERATOR_CONTACT", "@duckobmen")
    operator2 = _get_env("OPERATOR2_CONTACT", "")
    operator3 = _get_env("OPERATOR3_CONTACT", "")
    work_operator = _get_env("WORK_OPERATOR", "@duckobmen")

    text = "<b>🔗 Редактирование ссылок</b>\n\n"
    text += f"📊 Курсы: <code>{rates_url}</code>\n"
    text += f"💰 Продать BTC: <code>{sell_btc_url}</code>\n"
    text += f"📢 Канал новостей: <code>{news_channel}</code>\n"
    text += f"👨‍💻 Оператор: <code>{operator}</code>\n"
    text += f"👨‍💻 Оператор 2: <code>{operator2 or 'не задано'}</code>\n"
    text += f"👨‍💻 Оператор 3: <code>{operator3 or 'не задано'}</code>\n"
    text += f"🛠 Рабочий оператор: <code>{work_operator}</code>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Курсы", callback_data="link_edit_rates")],
        [InlineKeyboardButton(text="💰 Продать BTC", callback_data="link_edit_sell_btc")],
        [InlineKeyboardButton(text="📢 Канал новостей", callback_data="link_edit_news_channel")],
        [InlineKeyboardButton(text="👨‍💻 Оператор", callback_data="link_edit_operator")],
        [InlineKeyboardButton(text="👨‍💻 Оператор 2", callback_data="link_edit_operator2")],
        [InlineKeyboardButton(text="👨‍💻 Оператор 3", callback_data="link_edit_operator3")],
        [InlineKeyboardButton(text="🛠 Рабочий оператор", callback_data="link_edit_work_operator")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main_menu")],
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data.startswith("link_edit_"))
async def link_edit_start(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split("_", 2)[2]  # link_edit_rates -> rates
    env_key = LINK_FIELDS.get(key, key.upper())
    current = _get_env(env_key, "")

    await state.update_data(edit_link_key=key, edit_link_env_key=env_key)
    await callback.message.edit_text(
        f"<b>Редактирование: {key}</b>\n\n"
        f"Текущее значение:\n<code>{current or 'не задано'}</code>\n\n"
        f"Введите новое значение:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_links")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_link)
    await callback.answer()

@dp.message(AdminStates.waiting_link)
async def save_link_value(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    env_key = data.get("edit_link_env_key")
    value = message.text.strip()

    if env_key:
        update_env_var(env_key, value)

    await message.answer(
        f"✅ Ссылка обновлена!\n\n"
        f"<code>{env_key}={value}</code>",
        reply_markup=admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()

# ======================= РАССЫЛКА =======================
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    users_count = len(get_all_users())
    await callback.message.edit_text(
        f"<b>📢 Рассылка пользователям</b>\n\n"
        f"Пользователей в базе: <b>{users_count}</b>\n\n"
        f"Введите текст рассылки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_enter")]
        ]),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(AdminStates.waiting_broadcast)

@dp.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    users = get_all_users()
    if not users:
        await message.answer("Нет пользователей для рассылки.")
        await state.clear()
        return

    sent = 0
    for user_id in users:
        try:
            await bot.copy_message(user_id, message.from_user.id, message.message_id)
            sent += 1
        except Exception as e:
            print(f'Exception caught: {e}')

    await message.answer(
        f"✅ Рассылка завершена!\nОтправлено: <b>{sent}</b> из {len(users)}",
        reply_markup=admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
# ======================= ВСПОМОГАТЕЛЬНАЯ КНОПКА "НАЗАД" =======================
def back_to_admin(section: str):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=section)]])

@dp.callback_query(F.data.in_(["admin_banks", "admin_crypto_addresses", "admin_enter"]))
async def back_from_admin(callback: CallbackQuery):
    if callback.data == "admin_enter":
        await admin_panel(callback)
    elif callback.data == "admin_banks":
        await admin_banks(callback)
    elif callback.data == "admin_crypto_addresses":
        await admin_crypto_addresses(callback)

# ======================= Подменю Бонусы =======================

@dp.callback_query(F.data == "bonuses_menu")
async def bonuses_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    welcome_text = (
        "<b>Добро пожаловать в Уточка Обмен — обменник криптовалют 24/7!</b>\n\n"
        "Обменивайте RUB на BTC, LTC и XMR — быстро, удобно и безопасно 📈\n"
        "Всё работает автоматически — никаких задержек, только моментальные операции.\n"
        "Просто выберите монету и укажите сумму, а уточка всё сделает сама.\n\n"
        "🎉 <b>Скидка 300₽</b> на первый обмен!\n"
        "👩‍💻 Поддержка 24/7: @duckobmen_support\n\n"
        "❗️<b>Проводится конкурс видео!</b> Сними видео об \"Уточка Обмен\" в TikTok, Shorts, Reels, Клипах "
        "и получи <b>500₽ за каждые 1000 просмотров</b>. Подробности в поддержке❗️"
    )

    # Используем answer вместо edit_text — чтобы показать ReplyKeyboard
    await callback.message.answer(
        welcome_text,
        reply_markup=bonuses_inline_keyboard,
        parse_mode=ParseMode.HTML
    )

    # Опционально: удаляем старое сообщение, чтобы не было дублирования
    await callback.message.delete()

    await callback.answer()

bonuses_inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🦆 Поддержка", url=SUPPORT_CONTACT),
     InlineKeyboardButton(text="🎁 Промокоды", callback_data="promocodes")],

    [InlineKeyboardButton(text="🤝 Реферальная система", callback_data="referral"),
     InlineKeyboardButton(text="📔 Книга жалоб и предложений", url=COMPLAINT_BOOK)],

    [InlineKeyboardButton(text="💱 Курсы", callback_data="rates"),
     InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],

    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
])



@dp.callback_query(F.data == "promocodes")
async def promocodes(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🎁 Промокоды</b>\n\n"
        "Промокоды временно недоступны.\n"
        "Следите за новостями в поддержке!",
        reply_markup=bonuses_inline_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@dp.callback_query(F.data == "referral")
async def referral(callback: CallbackQuery):
    referral_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "<b>🤝 Реферальная система</b>\n\n"
        "💛 Реферальная система Уточки 💛\n\n"
        "Приглашай друзей и получай <b>250₽</b> на баланс за каждого активного друга! 🦆\n\n"
        "Твоя персональная реферальная ссылка:\n"
        "<code>https://t.me/duckobmen_bot?start=54RN9DA2</code>\n\n"
        "📩 Просто поделись этой ссылкой — и когда приглашённый пользователь совершит обмен,\n"
        "ты получишь бонус автоматически 💰\n\n"
        "✨ Твой баланс: <b>0₽</b>",
        reply_markup=referral_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rates")
async def rates(callback: CallbackQuery):
    rates_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 BTC → RUB", callback_data="rate_btc_rub"),
         InlineKeyboardButton(text="🌕 LTC → RUB", callback_data="rate_ltc_rub")],

        [InlineKeyboardButton(text="🪙 RUB → BTC", callback_data="rate_rub_btc"),
         InlineKeyboardButton(text="🌕 RUB → LTC", callback_data="rate_rub_ltc")],

        [InlineKeyboardButton(text="💎 ETH → RUB", callback_data="rate_eth_rub"),
         InlineKeyboardButton(text="🕶️ XMR → RUB", callback_data="rate_xmr_rub")],

        [InlineKeyboardButton(text="💎 RUB → ETH", callback_data="rate_rub_eth"),
         InlineKeyboardButton(text="🕶️ RUB → XMR", callback_data="rate_rub_xmr")],

        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "<b>💱 Актуальные курсы Уточки 🦆</b>\n\n"
        "Хотите узнать, сколько крипты получите за рубли 💸\n"
        "или наоборот — сколько рублей получите за крипту?\n\n"
        "Выберите направление ниже 👇\n\n"
        "📊 Поддерживаемые пары:\n"
        "• BTC ⇄ RUB\n"
        "• ETH ⇄ RUB\n"
        "• LTC ⇄ RUB\n"
        "• XMR ⇄ RUB\n\n"
        "🪙 Также можно ввести вручную:\n"
        "rate_btc_rub 0.01\n"
        "rate_eth_rub 0.01\n"
        "rate_rub_btc 10000\n"
        "rate_rub_eth 10000\n\n"
        "⚡️ Моментальный расчёт с учётом комиссии Уточки!\n"
        "Быстро. Удобно. Прозрачно. 💛",
        reply_markup=rates_keyboard,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ===================== Хэндлеры расчёта =====================

@dp.callback_query(F.data == "rate_btc_rub")
async def inline_rate_btc_rub(callback: CallbackQuery):
    amount = 0.001
    rate = buy_rates.get("BTC", 0)
    total = round(amount * rate, 2)

    text = (
        f"<code>rate_btc_rub {amount}</code>\n\n"
        f"<b>{amount} BTC = {total:.2f} ₽</b>\n"
        f"Курс: <code>{rate:.2f} RUB/BTC</code>"
    )

    await bot.send_message(callback.from_user.id, text, parse_mode=ParseMode.HTML)
    await callback.answer()



@dp.callback_query(F.data == "rate_eth_rub")
async def inline_rate_eth_rub(callback: CallbackQuery):
    amount = 0.01
    rate = buy_rates.get("ETH", 0)
    total = round(amount * rate, 2)
    await callback.message.answer(
        f"<code>rate_eth_rub {amount}</code>\n\n"
        f"<b>{amount} ETH = {total:.2f} ₽</b>\nКурс: <code>{rate:.2f} RUB/ETH</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rate_ltc_rub")
async def inline_rate_ltc_rub(callback: CallbackQuery):
    amount = 0.5
    rate = buy_rates.get("LTC", 0)
    total = round(amount * rate, 2)
    await callback.message.answer(
        f"<code>rate_ltc_rub {amount}</code>\n\n"
        f"<b>{amount} LTC = {total:.2f} ₽</b>\nКурс: <code>{rate:.2f} RUB/LTC</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rate_xmr_rub")
async def inline_rate_xmr_rub(callback: CallbackQuery):
    amount = 0.1
    rate = buy_rates.get("XMR", 0)
    total = round(amount * rate, 2)
    await callback.message.answer(
        f"<code>rate_xmr_rub {amount}</code>\n\n"
        f"<b>{amount} XMR = {total:.2f} ₽</b>\nКурс: <code>{rate:.2f} RUB/XMR</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rate_rub_btc")
async def inline_rate_rub_btc(callback: CallbackQuery):
    amount = 10000
    rate = sell_rates.get("BTC", 0)
    total = round(amount / rate, 8)
    await callback.message.answer(
        f"<code>rate_rub_btc {amount}</code>\n\n"
        f"<b>{amount} ₽ = {total:.8f} BTC</b>\nКурс: <code>{rate:.2f} RUB/BTC</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rate_rub_eth")
async def inline_rate_rub_eth(callback: CallbackQuery):
    amount = 10000
    rate = sell_rates.get("ETH", 0)
    total = round(amount / rate, 8)
    await callback.message.answer(
        f"<code>rate_rub_eth {amount}</code>\n\n"
        f"<b>{amount} ₽ = {total:.8f} ETH</b>\nКурс: <code>{rate:.2f} RUB/ETH</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rate_rub_ltc")
async def inline_rate_rub_ltc(callback: CallbackQuery):
    amount = 10000
    rate = sell_rates.get("LTC", 0)
    total = round(amount / rate, 8)
    await callback.message.answer(
        f"<code>rate_rub_ltc {amount}</code>\n\n"
        f"<b>{amount} ₽ = {total:.8f} LTC</b>\nКурс: <code>{rate:.2f} RUB/LTC</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "rate_rub_xmr")
async def inline_rate_rub_xmr(callback: CallbackQuery):
    amount = 10000
    rate = sell_rates.get("XMR", 0)
    total = round(amount / rate, 8)
    await callback.message.answer(
        f"<code>rate_rub_xmr {amount}</code>\n\n"
        f"<b>{amount} ₽ = {total:.8f} XMR</b>\nКурс: <code>{rate:.2f} RUB/XMR</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Получаем дату регистрации и рассчитываем дни
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT first_seen FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    if row:
        reg_datetime = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        reg_date = reg_datetime.strftime("%d.%m.%Y")
        days_with_duck = (datetime.now() - reg_datetime).days

        # Правильное склонение дней
        if days_with_duck % 10 == 1 and days_with_duck % 100 != 11:
            days_text = f"{days_with_duck} день"
        elif 2 <= days_with_duck % 10 <= 4 and (days_with_duck % 100 < 10 or days_with_duck % 100 >= 20):
            days_text = f"{days_with_duck} дня"
        else:
            days_text = f"{days_with_duck} дней"
    else:
        reg_date = "Неизвестно"
        days_text = "0 дней"

    profile_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await callback.message.edit_text(
        "<b>💛 Профиль Уточки 🦆</b>\n\n"
        f"📅 Дата регистрации: <b>{reg_date}</b>\n"
        f"🕒 С Уточкой уже: <b>{days_text}</b>\n\n"
        "💰 Ваш уровень скидки: <b>0.00%</b>\n"
        "💳 Баланс кэшбека:\n"
        " • Текущий: <b>0 ₽</b>\n"
        " • Кэшбек: <b>0 ₽</b>\n"
        " • Реферальный бонус: <b>0 ₽</b>\n\n"
        "🎟 Билетиков: <b>0</b>\n"
        "🎯 Всего выиграно: <b>0 ₽</b>\n"
        "🤝 Реферальные начисления: <b>0 ₽</b>\n"
        "⏳ До следующего билета: <b>0 ₽</b>\n\n"
        "📊 Статистика обменов\n\n"
        "🔄 Всего обменов: <b>0</b>\n"
        "📈 До следующего уровня скидки: осталось <b>50 обменов</b>\n\n"
        "💰 Общий объём обменов: <b>0 ₽</b>\n"
        "📈 Следующий уровень через: <b>150000 ₽</b>\n\n"
        "🗓 За последний месяц:\n"
        " • Количество обменов: <b>0</b>\n"
        " • Объём: <b>0 ₽</b>\n"
        " • До нового уровня скидки осталось: <b>15 обменов или 15000 ₽</b>\n\n"
        "🎁 Активные промокоды\n"
        "<i>Отсутствуют</i>\n\n"
        "1️⃣ Скидка на первый обмен — <b>300₽</b>\n"
        "🎲 Скидка за удачу — <b>150₽</b>\n"
        "🧠 Скидка за внимательность — <b>100₽</b>\n"
        "🤖 Подпишись на резервного бота[](https://t.me/duckobmen_reserv_bot?start=reserv) и получи скидку\n\n"
        "✨ Продолжайте обмены — и Уточка подарит ещё больше бонусов! 💛",
        reply_markup=profile_keyboard,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    await callback.answer()



# =======================Бонус кости =======================
# Клавиатура для броска
dice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎲 Бросить кости", callback_data="throw_dice")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
])

# Клавиатура "Попробовать ещё раз"
retry_dice_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎲 Бросить кости ещё раз", callback_data="throw_dice")],
    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
])

@dp.callback_query(F.data == "luck_discount")
async def luck_discount_handler(callback: CallbackQuery):
    if has_luck_bonus(callback.from_user.id):
        await callback.answer("✅ Вы уже получили скидку за удачу (150₽)", show_alert=False)
        return
    await callback.message.edit_text(
        "🔥 <b>Испытай судьбу с Уточкой!</b>\n\n"
        "Бросай кости и проверь, насколько ты везучий 🦆\n\n"
        "Если выпадет <b>1️⃣ или 6️⃣</b> — получаешь скидку <b>150₽</b> на следующий обмен 💸\n\n"
        "Удача уже ждёт тебя — рискнёшь? 🎲",
        reply_markup=dice_keyboard,  # клавиатура с кнопкой "Бросить кости"
        parse_mode=ParseMode.HTML
    )
    await callback.answer()

@dp.callback_query(F.data == "throw_dice")
async def throw_dice(callback: CallbackQuery):
    user_id = callback.from_user.id

    if has_luck_bonus(user_id):
        await callback.answer("❌ Вы уже получили скидку за удачу (150₽)!", show_alert=True)
        return

    await callback.message.edit_text("🎲 Уточка бросает кости... 🦆")
    await asyncio.sleep(1.2)

    # Отправляем настоящий кубик
    dice_message = await callback.message.answer_dice(emoji="🎲")
    result = dice_message.dice.value  # от 1 до 6

    await asyncio.sleep(2.5)  # ждём завершения анимации

    if result in [1, 6]:
        grant_luck_bonus(user_id)
        await callback.message.answer(
            "🎉 <b>Поздравляем! Уточка принесла тебе удачу!</b>\n\n"
            f"Выпало <b>{result}️⃣</b> — а значит, ты получаешь скидку <b>150₽</b> на следующий обмен 💸\n\n"
            "Используй бонус и продолжай летать на волне удачи 🦆✨",
            reply_markup=start_keyboard,
            parse_mode=ParseMode.HTML
        )
        await callback.answer("✅ Вы получили скидку за удачу (150₽)", show_alert=False)
    else:
        await callback.message.answer(
            "😅 <b>Уточка чуть не долетела до цели!</b>\n\n"
            f"В этот раз выпало <b>{result}️⃣</b> — не повезло, но удача уже рядом 🦆\n\n"
            "Хочешь попробовать ещё раз? 🎲",
            reply_markup=retry_dice_keyboard,
            parse_mode=ParseMode.HTML
        )
        await callback.answer()



# ======================= Резерв  =======================
RESERVE_BOT_USERNAME = "duckobmen_reserv_bot"  # без @

async def is_subscribed_to_reserve(user_id: int) -> bool:
    try:
        chat = await bot.get_chat_member(f"@{RESERVE_BOT_USERNAME}", user_id)
        return chat.status in ["member", "administrator", "creator"]
    except Exception as e:
        # Если пользователь не запускал бота или заблокировал — считается не подписан
        print(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

def has_reserve_bonus(user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("SELECT 1 FROM reserve_bonus WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def grant_reserve_bonus(user_id: int):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO reserve_bonus (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# ======================= ЗАПУСК =======================
async def main():
    init_db()
    print("🦆 Уточка Обмен успешно запущена!")

    # Пытаемся получить курсы с CoinGecko при запуске
    try:
        rates = await fetch_crypto_rates_coingecko()
        if rates:
            update_rates_from_coingecko(rates)
    except Exception as e:
        print(f"⚠️ Не удалось получить курсы с CoinGecko: {e}")

    # Запускаем фоновую задачу обновления курсов
    asyncio.create_task(refresh_rates_task())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())