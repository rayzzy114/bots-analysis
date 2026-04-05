import asyncio
import aiohttp
import uuid
import json
import os
import time
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    Document,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
BOT_USERNAME = os.getenv("BOT_USERNAME")
SUPPORT_CHAT_URL = os.getenv("SUPPORT_CHAT_URL", "https://t.me/redbull_support")
REVIEW_URL = os.getenv("REVIEW_URL", "https://t.me/+your_channel_or_link")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/your_channel")
CONFIG_FILE = "config.json"
SETTINGS_FILE = "user_settings.json"
DATABASE_FILE = "orders.db"
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    default_config = {
        "payment_details": {
            "card": {
                "bank": "Сбербанк",
                "number": "1234567812345678",
                "holder": "Иван Иванов"
            },
            "sbp": {
                "phone": "79001234567",
                "bank": "Сбербанк"
            },
            "qr": {
                "description": "Отсканируйте QR-код для оплаты",
                "image_file_id": None
            },
            "transgran": {
                "bank": "Сбербанк",
                "number": "1234567812345678",
                "holder": "Никита К."
            }
        },
        "wallet_addresses": {
            "BTC": "bc1qexampleaddressforbtcwallet",
            "LTC": "ltc1qexampleaddressforltcwallet"
        },
        "admins": [ADMIN_ID],
        "commission_percent": 0.18,
        "support_chat_url": os.getenv("SUPPORT_CHAT_URL", "https://t.me/redbull_support")
    }
    save_config(default_config)
    return default_config
def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
config = load_config()

def get_support_chat_url() -> str:
    """Get support chat URL from config, fallback to env var."""
    return config.get("support_chat_url") or os.getenv("SUPPORT_CHAT_URL", "https://t.me/redbull_support")

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
def add_check_columns():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN check_file_id TEXT")
        cursor.execute("ALTER TABLE orders ADD COLUMN check_file_type TEXT")
        conn.commit()
        print("Колонки check_file_id и check_file_type успешно добавлены")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("Колонки уже существуют")
        else:
            raise
    finally:
        conn.close()
# Вызываем один раз при запуске
add_check_columns()
def init_database():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            order_type TEXT NOT NULL,
            currency TEXT NOT NULL,
            crypto_amount REAL NOT NULL,
            rub_amount REAL NOT NULL,
            rate REAL NOT NULL,
            commission REAL NOT NULL,
            payment_method TEXT NOT NULL,
            payment_details TEXT,
            wallet_address TEXT,
            promo_code TEXT,
            check_file_id TEXT,
            check_file_type TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
def add_user(user_id, first_name=None):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, first_name) VALUES (?, ?)", (user_id, first_name))
        conn.commit()
        conn.close()
    except:
        pass
def get_user_first_name(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT first_name FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Unknown"
def is_admin(user_id):
    global config
    return user_id in config["admins"]
def add_admin(user_id):
    global config
    if user_id not in config["admins"]:
        config["admins"].append(user_id)
        save_config(config)
def remove_admin(user_id):
    global config
    if user_id in config["admins"]:
        config["admins"].remove(user_id)
        save_config(config)
def create_order(user_id, order_type, currency, crypto_amount, rub_amount, rate,
                 commission, payment_method, payment_details, wallet_address, promo_code=None):
    order_id = uuid.uuid4().hex[:8]
    expires_at = datetime.now() + timedelta(minutes=30)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO orders (order_id, user_id, order_type, currency, crypto_amount,
                            rub_amount, rate, commission, payment_method, payment_details,
                            wallet_address, promo_code, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, user_id, order_type, currency, crypto_amount, rub_amount, rate,
          commission, payment_method, payment_details, wallet_address, promo_code, expires_at))
    conn.commit()
    conn.close()
    return order_id
def get_order_status(order_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None
def update_order_status(order_id, status):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE order_id = ?", (status, order_id))
    conn.commit()
    conn.close()
def update_order_check(order_id, file_id, file_type):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET check_file_id = ?, check_file_type = ? WHERE order_id = ?", (file_id, file_type, order_id))
    conn.commit()
    conn.close()
def get_order_user_id(order_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM orders WHERE order_id = ?", (order_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None
def get_user_active_orders(user_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_id, order_type, currency, crypto_amount, rub_amount,
               status, created_at, expires_at
        FROM orders
        WHERE user_id = ? AND status = 'pending' AND expires_at > datetime('now')
        ORDER BY created_at DESC
    """, (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders
def get_order_details(order_id):
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_type, currency, crypto_amount, rub_amount, rate, commission,
               payment_method, payment_details, wallet_address, promo_code
        FROM orders WHERE order_id = ?
    """, (order_id,))
    result = cursor.fetchone()
    conn.close()
    return result
def cancel_order(order_id):
    update_order_status(order_id, 'cancelled')
class OrderStates(StatesGroup):
    waiting_amount = State()
    waiting_wallet = State()
    waiting_promo = State()
    waiting_sell_payment_details = State()
    waiting_sell_bank = State()
    waiting_sell_amount = State()
    waiting_sell_promo = State()
    waiting_check = State()
class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_new_btc_address = State()
    waiting_new_ltc_address = State()
    waiting_new_card = State()
    waiting_new_sbp_phone = State()
    waiting_new_sbp_bank = State()
    waiting_new_operator_id = State()
    waiting_new_transgran_number = State()
    waiting_new_transgran_bank = State()
    waiting_new_transgran_holder = State()
    waiting_new_qr_image = State()
    waiting_new_qr_description = State()
    waiting_new_commission = State()
    waiting_new_all_bank = State()
    waiting_new_all_number = State()
    waiting_new_all_holder = State()
    waiting_new_all_phone = State()
    waiting_new_card_bank = State()
    waiting_new_card_holder = State()
    waiting_new_support_url = State()
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
def validate_card_number(card: str) -> bool:
    return True
def validate_phone_number(phone: str) -> bool:
    return True
def validate_btc_address(address: str) -> bool:
    if len(address) < 26 or len(address) > 62:
        return False
    if not (address.startswith("1") or address.startswith("3") or address.startswith("bc1")):
        return False
    return True
def validate_ltc_address(address: str) -> bool:
    if len(address) < 26 or len(address) > 43:
        return False
    if not (address.startswith("L") or address.startswith("M") or address.startswith("ltc1")):
        return False
    return True
BANKS_LIST = [
    ["АБ-Россия", "BMW Банк"],
    ["CIS (Трансграничный)", "HandyBank"],
    ["Qplus", "UniCredit"],
    ["Абсолют Банк", "Авангард"],
    ["Авито кошелек", "Азиатско-тихоокеанский б..."],
    ["Ак Барс Банк", "Алмазэргиэнбанк банк"],
    ["Альфа-Банк", "БФГ Банк"],
    ["БКС Банк", "Банк Агророс"],
    ["Банк Акцепт", "Банк Казани"],
    ["Банк Оренбург", "Белгородсоцбанк"],
    ["БыстроБанк", "ВБРР"],
    ["ВТБ", "Вайлдберис банк"],
    ["Возрождение", "Вологжанин"],
    ["Восточный банк", "Газпромбанк"],
    ["Газтрансбанк", "ГенБанк"],
    ["ДОМ.РФ", "Дальневосточный банк"],
    ["Долинск Банк", "Живаго банк"],
    ["ЗЕНИТ", "Ингострах"],
    ["Интерпрогрессбанк", "Ключева банк"],
    ["Кошелек ЦУПИС (Мобильна...", "Крайинвестбанк"],
    ["Кредит Европа банк", "Кубань Кредит"],
    ["ЛОКО-Банк", "Левобережный"],
    ["МТС банк", "МТС деньги"],
    ["Мегафон банк", "Металлинвестбанк"],
    ["Московский кредитный банк", "ОТП банк"],
    ["Озон Банк", "Открытие"],
    ["Плюс банк", "Пойдем банк"],
    ["ПриватБанк", "Приморье Банк"],
    ["ПромСвязьбанк", "РНК банк"],
    ["РОСБАНК", "Райффайзен"],
    ["Райффайзен", "Ренессанс Кредит"],
    ["Рокетбанк", "Россельхозбанк"],
    ["РостФинанс Банк", "Русский Стандарт"],
    ["СДМ банк", "СКБ-банк"],
    ["СМП банк", "Санкт-Петербург"],
    ["Сбербанк", "Сбербанк Казахстана"],
    ["Свой банк", "Связь-Банк"],
    ["Сибсоц банк", "Ситибанк"],
    ["Совкомбанк", "Солид Банк"],
    ["Солидарность", "СургутНефтегаз"],
    ["Т-Банк", "Тинькофф"],
    ["Точка банк", "Транскапитал банк"],
    ["Траст", "УБРиР"],
    ["Уралсиб", "Финам банк"],
    ["Фора банк", "Хлынов"],
    ["Хоум банк", "Центр-инвест"],
    ["Цифра", "Челябинвестбанк"],
    ["ЭкспоБанк", "ЮГ-ИНВЕСТ банк"],
    ["ЮМани YooMoney", "Юнистрим"],
    ["Яндекс банк", ""],
    ["Другой банк", ""]
]
# Binance для BTC/USDT и LTC/USDT + Coingecko для USDT/RUB
BINANCE_BASE_URL = "https://api.binance.com/api/v3/ticker/price"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub"
# Fallback URL для USDT/RUB (резервный источник)
FALLBACK_COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=rub"
RATES_CACHE = {"bitcoin": None, "litecoin": None, "tether": None}
RATES_LAST_UPDATE = 0
RATES_TTL = 300 # 5 минут

async def fetch_usdt_rub_from_coingecko(session, url: str) -> float:
    """Fetch USDT/RUB rate from CoinGecko with error handling."""
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                usdt_rub = data.get("tether", {}).get("rub", 0)
                if usdt_rub > 0:
                    return usdt_rub
            elif resp.status == 429:
                print(f"CoinGecko rate limited (429)")
            else:
                print(f"CoinGecko API error: {resp.status}")
    except Exception as e:
        print(f"CoinGecko request failed: {e}")
    return 0.0

async def fetch_rates_from_binance() -> dict:
    """Fetch rates from Binance (BTC/USDT, LTC/USDT) and CoinGecko (USDT/RUB)."""
    try:
        async with aiohttp.ClientSession() as session:
            rates = {}

            # 1. BTC/USDT и LTC/USDT с Binance
            crypto_usdt = {}
            for coin, symbol in {
                "bitcoin": "BTCUSDT",
                "litecoin": "LTCUSDT"
            }.items():
                try:
                    async with session.get(f"{BINANCE_BASE_URL}?symbol={symbol}", timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            price = float(data.get("price", 0))
                            if price > 0:
                                crypto_usdt[coin] = price
                                print(f"{coin.upper()}/USDT: {price}")
                except Exception as e:
                    print(f"Binance {coin} error: {e}")

            # 2. USDT/RUB с CoinGecko (основной источник)
            usdt_rub = await fetch_usdt_rub_from_coingecko(session, COINGECKO_URL)

            # 3. Если CoinGecko не работает, используем fallback
            if usdt_rub <= 0:
                print("Primary CoinGecko failed, trying fallback...")
                usdt_rub = await fetch_usdt_rub_from_coingecko(session, FALLBACK_COINGECKO_URL)

            if usdt_rub <= 0:
                print("WARNING: Could not fetch USDT/RUB rate")
                # Используем кэшированный USDT rate если есть
                cached_usdt = RATES_CACHE.get("tether", {}).get("rub")
                if cached_usdt and cached_usdt > 0:
                    usdt_rub = cached_usdt
                    print(f"Using cached USDT rate: {usdt_rub}")
                else:
                    return {}

            print(f"USDT/RUB: {usdt_rub}")

            # 4. Конвертируем BTC и LTC в RUB
            for coin, usdt_price in crypto_usdt.items():
                rub_price = usdt_price * usdt_rub
                rates[coin] = {"rub": rub_price}

            # 5. Добавляем USDT напрямую
            rates["tether"] = {"rub": usdt_rub}

            return rates
    except Exception as e:
        print(f"Error fetching rates: {e}")
        return {}
async def rates_updater():
    global RATES_CACHE, RATES_LAST_UPDATE
    while True:
        rates = await fetch_rates_from_binance()
        if rates:
            RATES_CACHE = rates
            RATES_LAST_UPDATE = time.time()
            btc_rub = rates.get("bitcoin", {}).get("rub")
            ltc_rub = rates.get("litecoin", {}).get("rub")
            print(f"Курсы обновлены: BTC ≈ {btc_rub:,.0f} ₽ | LTC ≈ {ltc_rub:,.0f} ₽")
        else:
            print("Не удалось обновить курсы — используется старый кэш")
        await asyncio.sleep(RATES_TTL)
def get_cached_rate(coin: str) -> float | None:
    try:
        return RATES_CACHE[coin]["rub"]
    except Exception:
        return None
def format_pair(price_rub: float) -> str:
    buy = round(price_rub * 0.98, 2) # -2% для покупки
    sell = round(price_rub * 1.02, 2) # +2% для продажи
    return f"│ Покупка: {buy:,.2f} ₽\n└ Продажа: {sell:,.2f} ₽"
async def rates_text():
    btc = get_cached_rate("bitcoin")
    ltc = get_cached_rate("litecoin")
    usdt = get_cached_rate("tether")
    if btc is None or ltc is None:
        return "❌ Курсы ещё не загружены. Попробуйте позже."
    return (
        "<b>📊 Актуальные курсы обмена</b>\n\n"
        "<b>₿ Bitcoin (BTC)</b>\n"
        f"{format_pair(btc)}\n\n"
        "<b>Ł Litecoin (LTC)</b>\n"
        f"{format_pair(ltc)}\n\n"
        "<b>₮ Tether (USDT TRC20)</b>\n"
        f"{format_pair(usdt)}"
    )
def format_rub(value: float) -> str:
    rounded = round(value)
    return f"{rounded:,.0f}".replace(",", " ").replace(".", ",")
def format_crypto(value: float, decimals: int = 8) -> str:
    return f"{value:.{decimals}f}"
def format_card_number(number: str) -> str:
    clean = number.replace(" ", "").replace("-", "")
    return ' '.join([clean[i:i+4] for i in range(0, len(clean), 4)])
def mask_card(card_number: str) -> str:
    card_clean = card_number.replace(" ", "")
    if len(card_clean) >= 16:
        return f"{card_clean[:4]} **** **** {card_clean[-4:]}"
    return card_number
def mask_phone(phone: str) -> str:
    if len(phone) >= 11:
        return f"+{phone[:4]}*****{phone[-2:]}"
    return phone
menu_button_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📋 Меню")]],
    resize_keyboard=True,
    is_persistent=True,
)
def kb_main_menu():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="💵 Купить", callback_data="buy"),
        InlineKeyboardButton(text="💰 Продать", callback_data="sell"),
    )
    kb.row(
        InlineKeyboardButton(text="📊 Курсы", callback_data="rates"),
        InlineKeyboardButton(text="📋 Мои заявки", callback_data="orders"),
    )
    kb.row(
        InlineKeyboardButton(text="👥 Рефералка", callback_data="ref"),
        InlineKeyboardButton(text="🎁 Промокоды", callback_data="promo"),
    )
    kb.row(
        InlineKeyboardButton(text="📢 Канал", url=CHANNEL_URL),
        InlineKeyboardButton(text="⭐ Отзывы", url=REVIEW_URL),
    )
    kb.row(InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings"))
    kb.row(
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"),
        InlineKeyboardButton(text="💬 Чат", url=get_support_chat_url()),
    )
    return kb.as_markup()
def kb_back():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    return kb.as_markup()
def kb_buy_select():
    kb = InlineKeyboardBuilder()
    kb.button(text="₿ Bitcoin", callback_data="buy_btc")
    kb.button(text="Ł Litecoin", callback_data="buy_ltc")
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    return kb.as_markup()
def kb_sell_select():
    kb = InlineKeyboardBuilder()
    kb.button(text="₿ Bitcoin", callback_data="sell_btc")
    kb.button(text="Ł Litecoin", callback_data="sell_ltc")
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    return kb.as_markup()
def kb_payment_methods():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Карта", callback_data="pay_card"))
    kb.row(InlineKeyboardButton(text="📱 СБП", callback_data="pay_sbp"))
    kb.row(InlineKeyboardButton(text="📸 QR-код", callback_data="pay_qr"))
    kb.row(InlineKeyboardButton(text="🌍 Трансгран", callback_data="pay_transgran"))
    kb.row(
        InlineKeyboardButton(text="« Назад", callback_data="buy"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_sell_payment_methods():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💳 Карта", callback_data="sell_pay_card"))
    kb.row(InlineKeyboardButton(text="📱 СБП", callback_data="sell_pay_sbp"))
    kb.row(
        InlineKeyboardButton(text="« Назад", callback_data="sell"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_banks():
    kb = InlineKeyboardBuilder()
    for row in BANKS_LIST:
        buttons_in_row = []
        for bank in row:
            if bank:
                buttons_in_row.append(InlineKeyboardButton(
                    text=bank,
                    callback_data=f"bank_{bank[:30]}"
                ))
        if buttons_in_row:
            kb.row(*buttons_in_row)
    kb.row(
        InlineKeyboardButton(text="« Назад", callback_data="sell"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_amount_back_cancel():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="« Назад", callback_data="buy"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_sell_amount_back_cancel():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="« Назад", callback_data="sell"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_wallet_back_cancel():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="« Назад", callback_data="back_to_amount"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_promo_skip():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="▶️ Пропустить", callback_data="skip_promo"))
    return kb.as_markup()
def kb_sell_promo_skip():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="▶️ Пропустить", callback_data="skip_sell_promo"))
    return kb.as_markup()
def kb_confirm_order():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_order"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_confirm_sell_order():
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_sell_order"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
    )
    return kb.as_markup()
def kb_cancel_order(order_id: str):
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_order_{order_id}"))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    return kb.as_markup()
def get_notifications_kb(user_id: int):
    settings = load_settings()
    notifications_on = settings.get(str(user_id), {}).get("notifications", True)
    kb = InlineKeyboardBuilder()
    if notifications_on:
        kb.row(InlineKeyboardButton(text="🔔 Уведомления: ВКЛ", callback_data="notif_off"))
    else:
        kb.row(InlineKeyboardButton(text="🔕 Уведомления: ВЫКЛ", callback_data="notif_on"))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    return kb.as_markup()
def kb_admin_main():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    kb.row(InlineKeyboardButton(text="💳 Реквизиты покупки", callback_data="admin_payment_details"))
    kb.row(InlineKeyboardButton(text="🔑 Адреса кошельков продажи", callback_data="admin_wallet_addresses"))
    kb.row(InlineKeyboardButton(text="👥 Операторы", callback_data="admin_operators"))
    kb.row(InlineKeyboardButton(text="💱 Изменить комиссию", callback_data="admin_change_commission"))
    kb.row(InlineKeyboardButton(text="💬 Изменить ссылку оператора", callback_data="admin_change_support_url"))
    kb.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    return kb.as_markup()
def kb_payment_details_menu():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="🔄 Изменить все сразу", callback_data="admin_change_all"))
    kb.row(InlineKeyboardButton(text="💳 Изменить номер карты", callback_data="admin_change_card"))
    kb.row(InlineKeyboardButton(text="🏦 Изменить банк карты", callback_data="admin_change_card_bank"))
    kb.row(InlineKeyboardButton(text="👤 Изменить получателя карты", callback_data="admin_change_card_holder"))
    kb.row(InlineKeyboardButton(text="📱 Изменить СБП телефон", callback_data="admin_change_sbp_phone"))
    kb.row(InlineKeyboardButton(text="🏦 Изменить СБП банк", callback_data="admin_change_sbp_bank"))
    kb.row(InlineKeyboardButton(text="🌍 Изменить трансгран номер", callback_data="admin_change_transgran_number"))
    kb.row(InlineKeyboardButton(text="🏦 Изменить трансгран банк", callback_data="admin_change_transgran_bank"))
    kb.row(InlineKeyboardButton(text="👤 Изменить трансгран получателя", callback_data="admin_change_transgran_holder"))
    kb.row(InlineKeyboardButton(text="📸 Изменить QR изображение", callback_data="admin_change_qr_image"))
    kb.row(InlineKeyboardButton(text="📝 Изменить QR описание", callback_data="admin_change_qr_description"))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="back_to_menu"))
    return kb.as_markup()
def kb_wallet_addresses_menu():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="₿ Изменить BTC адрес", callback_data="admin_change_btc"))
    kb.row(InlineKeyboardButton(text="Ł Изменить LTC адрес", callback_data="admin_change_ltc"))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="back_to_menu"))
    return kb.as_markup()
def kb_operators_menu():
    global config
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_operator"))
    for admin_id in config["admins"]:
        kb.row(InlineKeyboardButton(text=f"❌ Удалить {admin_id}", callback_data=f"admin_remove_operator_{admin_id}"))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="back_to_menu"))
    return kb.as_markup()
def kb_back_to_menu():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="« Назад в меню", callback_data="back_to_menu"))
    return kb.as_markup()
def kb_cancel_broadcast():
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_menu"))
    return kb.as_markup()
def kb_order_approval(order_id: str):
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_order_{order_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_order_{order_id}"),
    )
    return kb.as_markup()
WELCOME_TEXT_TPL = (
    "👋 Добро пожаловать, {name}!\n\n"
    "🔄 Это бот для обмена криптовалют.\n\n"
    "💱 Доступные валюты:\n"
    "• Bitcoin (BTC)\n"
    "• USDT (TRC20)\n"
    "• Litecoin (LTC)\n\n"
    "✅ Быстро, безопасно, выгодно!\n\n"
    "Жми меню чтобы начать пользоваться ботом"
)
MAIN_MENU_TEXT = "📋 Главное меню\n\nВыберите необходимое действие:"
BUY_TEXT = "💵 <b>Покупка криптовалюты</b>\n\nВыберите валюту для покупки:"
SELL_TEXT = "💸 <b>Продажа криптовалюты</b>\n\nВыберите валюту для продажи:"
SETTINGS_TEXT = (
    "⚙️ Настройки\n\n"
    "Здесь вы можете управлять настройками бота.\n\n"
    "🔔 Уведомления — получение рассылок и новостей от бота."
)
init_database()
@dp.message(CommandStart())
async def start(message: Message):
    add_user(message.from_user.id, message.from_user.first_name)
    text = WELCOME_TEXT_TPL.format(name=message.from_user.full_name)
    await message.answer(text, reply_markup=menu_button_kb)
@dp.message(F.text == "/adminpanel")
async def admin_panel_start(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        text = "🔐 <b>Админ-панель</b> 👨‍💻\n\nВыберите действие:"
        await message.answer(text, reply_markup=kb_admin_main(), parse_mode=ParseMode.HTML)
    # else: ignore
@dp.message(F.text == "📋 Меню")
async def open_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(MAIN_MENU_TEXT, reply_markup=kb_main_menu())
@dp.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(MAIN_MENU_TEXT, reply_markup=kb_main_menu())
    await call.answer()
@dp.callback_query(F.data == "cancel")
async def cancel_order_process(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Операция отменена.")
    await call.message.answer(MAIN_MENU_TEXT, reply_markup=kb_main_menu())
    await call.answer()
@dp.callback_query(F.data == "buy")
async def open_buy(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(BUY_TEXT, reply_markup=kb_buy_select(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "buy_btc")
async def buy_btc(call: CallbackQuery, state: FSMContext):
    await state.update_data(currency="BTC", coin_id="bitcoin", order_type="buy")
    rate = get_cached_rate("bitcoin")
    if rate is None:
        await call.message.edit_text("❌ Курс BTC ещё не загружен. Попробуйте позже.", reply_markup=kb_back())
        await call.answer()
        return
    await state.update_data(rate=rate)
    text = f"✅ Выбрана валюта: <b>BTC</b>\n✅ Курс обмена: <b>{format_rub(rate)} ₽</b>\n\nВыберите способ оплаты:"
    await call.message.edit_text(text, reply_markup=kb_payment_methods(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "buy_ltc")
async def buy_ltc(call: CallbackQuery, state: FSMContext):
    await state.update_data(currency="LTC", coin_id="litecoin", order_type="buy")
    rate = get_cached_rate("litecoin")
    if rate is None:
        await call.message.edit_text("❌ Курс LTC ещё не загружен. Попробуйте позже.", reply_markup=kb_back())
        await call.answer()
        return
    await state.update_data(rate=rate)
    text = f"✅ Выбрана валюта: <b>LTC</b>\n✅ Курс обмена: <b>{format_rub(rate)} ₽</b>\n\nВыберите способ оплаты:"
    await call.message.edit_text(text, reply_markup=kb_payment_methods(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "reviews")
async def show_reviews(call: CallbackQuery):
    text = "⭐ Здесь наши отзывы и мнения клиентов!\n\nПерейти к отзывам 👇"
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="📖 Открыть отзывы", url=REVIEW_URL))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    
    await call.message.edit_text(text, reply_markup=kb.as_markup())
    await call.answer()
@dp.callback_query(F.data.in_({"pay_card", "pay_sbp", "pay_qr", "pay_transgran"}))
async def select_payment_method(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    payment_methods = {
        "pay_card": "Банковская карта",
        "pay_sbp": "СБП",
        "pay_qr": "QR-код",
        "pay_transgran": "Трансгран"
    }
    payment_method = payment_methods[call.data]
    await state.update_data(payment_method=payment_method)
    if payment_method == "QR-код":
        qr_details = config["payment_details"].get("qr", {})
        if qr_details.get("image_file_id") is None:
            await call.message.edit_text("❌ Ошибка: данный метод для покупки не доступен. Попробуйте позже или измените выбор оплаты.", reply_markup=kb_amount_back_cancel(), parse_mode=ParseMode.HTML)
            await call.answer()
            return
    min_amounts = {
        "BTC": {"btc": 0.00025561, "rub": 2112},
        "LTC": {"ltc": 0.23, "rub": 1445}
    }
    min_info = min_amounts.get(currency, {"btc": 0.00025561, "rub": 2112})
    min_crypto = min_info.get(currency.lower(), min_info.get("btc"))
    min_rub = min_info["rub"]
    text = (
        f"✅ Валюта: <b>{currency}</b>\n"
        f"✅ Курс обмена: <b>{format_rub(rate)} ₽</b>\n"
        f"✅ Способ оплаты: <b>{payment_method}</b>\n\n"
        "<b>💰 Введите сумму покупки</b>\n\n"
        f"Минимальная сумма: {format_crypto(min_crypto)} {currency} (~{min_rub} ₽)\n"
        "Вы можете ввести:\n"
        "• Сумму в рублях (например: 5000)\n"
        f"• Сумму в {currency} (например: 0.001 {currency})"
    )
    await call.message.edit_text(text, reply_markup=kb_amount_back_cancel(), parse_mode=ParseMode.HTML)
    await state.set_state(OrderStates.waiting_amount)
    await call.answer()
@dp.callback_query(F.data == "back_to_amount")
async def back_to_amount(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    payment_method = data.get("payment_method", "")
    min_amounts = {
        "BTC": {"btc": 0.00025561, "rub": 2112},
        "LTC": {"ltc": 0.23, "rub": 1445}
    }
    min_info = min_amounts.get(currency, {"btc": 0.00025561, "rub": 2112})
    min_crypto = min_info.get(currency.lower(), min_info.get("btc"))
    min_rub = min_info["rub"]
    text = (
        f"✅ Валюта: <b>{currency}</b>\n"
        f"✅ Курс обмена: <b>{format_rub(rate)} ₽</b>\n"
        f"✅ Способ оплаты: <b>{payment_method}</b>\n\n"
        "💰 Введите сумму покупки\n\n"
        f"Минимальная сумма: {format_crypto(min_crypto)} {currency} (~{min_rub} ₽)\n"
        "Вы можете ввести:\n"
        "• Сумму в рублях (например: 5000)\n"
        f"• Сумму в {currency} (например: 0.001 {currency})"
    )
    await call.message.edit_text(text, reply_markup=kb_amount_back_cancel(), parse_mode=ParseMode.HTML)
    await state.set_state(OrderStates.waiting_amount)
    await call.answer()
@dp.message(OrderStates.waiting_amount)
async def process_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    payment_method = data.get("payment_method", "")
    user_input = message.text.strip().upper().replace(",", ".")
    is_crypto = currency in user_input or "." in user_input

    try:
        commission_percent = config["commission_percent"]

        if is_crypto:
            # Пользователь ввёл сколько хочет ПОЛУЧИТЬ чистыми в крипте
            amount_str = user_input.replace("BTC", "").replace("LTC", "").strip()
            crypto_amount_net = float(amount_str)

            # Сколько нужно отправить "грязными" (до вычета комиссии)
            crypto_amount_gross = crypto_amount_net / (1 - commission_percent)

            # Сумма к оплате (увеличенная)
            rub_amount = crypto_amount_gross * rate

            commission_crypto = crypto_amount_gross - crypto_amount_net

        else:
            # Пользователь ввёл сколько хочет ПОЛУЧИТЬ чистыми в рублях
            rub_amount_net = float(user_input)

            # Сколько нужно заплатить с комиссией
            rub_amount = rub_amount_net / (1 - commission_percent)

            # Сколько крипты получится чистыми
            crypto_amount_net = rub_amount_net / rate

            commission_crypto = (rub_amount - rub_amount_net) / rate

        # Проверка минимальной суммы (по сумме к оплате)
        if rub_amount < 1500:
            min_rub = 1500
            min_crypto_net = (min_rub * (1 - commission_percent)) / rate
            await message.answer(
                f"❌ Минимальная сумма к оплате: {format_rub(min_rub)} ₽\n"
                f"(Вы получите ~{format_crypto(min_crypto_net)} {currency})\n"
                "Попробуйте ввести большую сумму.",
                reply_markup=kb_amount_back_cancel()
            )
            return

        # Сохраняем в состояние ЧИСТЫЕ значения (то, что пользователь реально получит)
        received_rub = crypto_amount_net * rate
        commission_rub = commission_crypto * rate
        await state.update_data(
            rub_amount=rub_amount,              # ← реальная сумма к оплате (с комиссией)
            crypto_amount=crypto_amount_net,    # ← чистая сумма крипты, которую получит
            commission_crypto=commission_crypto,
            received_rub=received_rub,
            commission_rub=commission_rub
        )

        # Сообщение — показываем УВЕЛИЧЕННУЮ сумму к оплате
        text = (
            f"✅ Валюта: <b>{currency}</b>\n"
            f"✅ Курс обмена: <b>{format_rub(rate)} ₽</b>\n"
            f"✅ Способ оплаты: <b>{payment_method}</b>\n"
            f"✅ Сумма к оплате: <b>{format_rub(rub_amount)} ₽</b>\n"              # ← уже с комиссией!
            f"✅ Вы получите: <b>{format_crypto(crypto_amount_net)} {currency}</b>\n"
            f"✅ Комиссия обменника ({commission_percent*100:.0f}%): <b>≈ {format_rub(commission_rub)} ₽</b>\n\n"
            f"<b>📍 Введите адрес {currency} кошелька для получения криптовалюты:</b>"
        )

        await message.answer(
            text,
            reply_markup=kb_wallet_back_cancel(),
            parse_mode="HTML"
        )
        await state.set_state(OrderStates.waiting_wallet)

    except ValueError:
        await message.answer("❌ Неверный формат суммы. Попробуйте еще раз.", reply_markup=kb_amount_back_cancel())
@dp.message(OrderStates.waiting_wallet)
async def process_wallet(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    wallet_address = message.text.strip()
    is_valid = False
    if currency == "BTC":
        is_valid = validate_btc_address(wallet_address)
    elif currency == "LTC":
        is_valid = validate_ltc_address(wallet_address)
    if not is_valid:
        await message.answer(f"❌ Неверный адрес {currency} кошелька.\nПроверьте адрес и попробуйте еще раз.", reply_markup=kb_wallet_back_cancel())
        return
    await state.update_data(wallet_address=wallet_address)
    text = "🎁 У вас есть промокод?\n\nВведите промокод или нажмите \"Пропустить\""
    await message.answer(text, reply_markup=kb_promo_skip())
    await state.set_state(OrderStates.waiting_promo)
@dp.callback_query(F.data == "skip_promo", OrderStates.waiting_promo)
async def skip_promo(call: CallbackQuery, state: FSMContext):
    await show_order_confirmation(call.message, state)
    await call.answer()
@dp.message(OrderStates.waiting_promo)
async def process_promo(message: Message, state: FSMContext):
    promo_code = message.text.strip()
    await state.update_data(promo_code=promo_code)
    await show_order_confirmation(message, state)
async def show_order_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    crypto_amount = data.get("crypto_amount", 0)
    rate = data.get("rate", 0)
    rub_amount = data.get("rub_amount", 0)
    payment_method = data.get("payment_method", "")
    wallet_address = data.get("wallet_address", "")
    text = (
    "📋 <b>Подтверждение заявки</b>\n\n"
    f"Валюта: <b>{currency}</b>\n"
    f"Количество: <b>{format_crypto(crypto_amount)} {currency}</b>\n"
    f"Курс: <b>{format_rub(rate)} ₽</b>\n"
    f"Сумма: <b>{format_rub(rub_amount)} ₽</b>\n\n"
    f"Способ оплаты: <b>{payment_method}</b>\n\n"
    f"Адрес для получения:\n<code>{wallet_address}</code>"
)
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb_confirm_order(), parse_mode=ParseMode.HTML)
    else:
        await message.edit_text(text, reply_markup=kb_confirm_order(), parse_mode=ParseMode.HTML)
@dp.callback_query(F.data == "confirm_order")
async def confirm_order(call: CallbackQuery, state: FSMContext):
    global config
    data = await state.get_data()
    await call.message.edit_text("⏳ Создаем заявку... Пожалуйста, подождите.", parse_mode=ParseMode.HTML)
    await asyncio.sleep(3)
    payment_details = config["payment_details"]
    payment_method = data.get("payment_method", "")
    rub_amount = data.get("rub_amount", 0)
    payment_key_map = {
        "Банковская карта": "card",
        "СБП": "sbp",
        "QR-код": "qr",
        "Трансгран": "transgran"
    }
    payment_key = payment_key_map.get(payment_method)
    details = payment_details.get(payment_key, {}) if payment_key else {}
    if not details or not any(details.values()):
        error_text = "❌ Не удалось получить реквизиты для оплаты.\n\n⏳ Вы можете повторить запрос через 10 сек."
        await call.message.edit_text(error_text, reply_markup=kb_back(), parse_mode=ParseMode.HTML)
        await call.answer()
        await state.clear()
        return
    order_id = create_order(
        user_id=call.from_user.id,
        order_type="buy",
        currency=data.get("currency"),
        crypto_amount=data.get("crypto_amount"),
        rub_amount=rub_amount,
        rate=data.get("rate"),
        commission=data.get("commission_crypto"),
        payment_method=payment_method,
        payment_details=json.dumps(details),
        wallet_address=data.get("wallet_address"),
        promo_code=data.get("promo_code")
    )
    # Клавиатура только с кнопкой "Отмена заявки"
    kb_paid_cancel = InlineKeyboardBuilder()
    kb_paid_cancel.row(
        InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_order_{order_id}")
    )
    kb_paid_cancel.row(
        InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_order_{order_id}")
    )
    kb_paid_cancel = kb_paid_cancel.as_markup()
    formatted_rub = format_rub(rub_amount)
    text_base = (
        f"✅ <b>Заявка <code>#{order_id}</code> создана!</b>\n\n"
        f"<b>💳 Реквизиты для оплаты:</b>\n\n"
    )
    if payment_method == "Банковская карта":
        formatted_number = format_card_number(details.get('number', 'Не указан'))
        bank = details.get('bank', 'Не указан')
        holder = details.get('holder', '')
        text = (
            text_base +
            f"Номер карты: <code>{formatted_number}</code>\n"
            f"Получатель: <code>{bank}</code> <code>{holder}</code>\n\n"
            f"<b>💰 Сумма к оплате: {formatted_rub} ₽</b>\n\n"
            f"⏱️ Оплатите в течение 30 минут. После оплаты ожидайте подтверждение."
        )
        await call.message.edit_text(text, reply_markup=kb_paid_cancel, parse_mode=ParseMode.HTML)
    elif payment_method == "Трансгран":
        formatted_number = format_card_number(details.get('number', 'Не указан'))
        bank = details.get('bank', 'Не указан')
        holder = details.get('holder', '')
        text = (
            text_base +
            f"🌍 Трансграничная карта: <code>{formatted_number}</code>\n"
            f"Получатель: <code>{bank}</code> <code>{holder}</code>\n\n"
            f"<b>💰 Сумма к оплате: {formatted_rub} ₽</b>\n\n"
            f"⏱️ Оплатите в течение 30 минут. После оплаты ожидайте подтверждение."
        )
        await call.message.edit_text(text, reply_markup=kb_paid_cancel, parse_mode=ParseMode.HTML)
    else:
        # Для СБП
        phone = details.get('phone', 'Не указан')
        bank = details.get('bank', 'Не указан')
        text = (
            text_base +
            f"Телефон: <code>{phone}</code>\n"
            f"Банк: <code>{bank}</code>\n\n"
            f"<b>💰 Сумма к оплате: {formatted_rub} ₽</b>\n\n"
            f"⏱️ Оплатите в течение 30 минут. После оплаты ожидайте подтверждение."
        )
        await call.message.edit_text(text, reply_markup=kb_paid_cancel, parse_mode=ParseMode.HTML)

    # Последний — QR-код (отдельный блок, как ты просил)
    if payment_method == "QR-код":
       qr_details = config["payment_details"].get("qr", {})
       image_file_id = qr_details.get("image_file_id")
    
       if image_file_id is None:
        await call.message.edit_text(
            "❌ Ошибка: данный метод для покупки не доступен.\n"
            "QR-код не настроен. Попробуйте позже или выберите другой способ оплаты.",
            reply_markup=kb_amount_back_cancel(),
            parse_mode=ParseMode.HTML
        )
        await call.answer()
        return  # ← выходим, чтобы не продолжать
    
    # Если QR есть — отправляем фото
    description = qr_details.get('description', 'Отсканируйте QR-код для оплаты')
    text = (
        text_base +
        f"{description}\n\n"
        f"<b>💰 Сумма к оплате: {formatted_rub} ₽</b>\n\n"
        f"⏱️ Оплатите в течение 30 минут.\n"
        f"После оплаты нажмите «Я оплатил» или пришлите чек."
    )
    
    await call.message.delete()  # удаляем старое сообщение
    await call.message.answer_photo(
        photo=image_file_id,
        caption=text,
        reply_markup=kb_paid_cancel,
        parse_mode=ParseMode.HTML
    )
    await state.set_state(OrderStates.waiting_check)
    await state.update_data(order_id=order_id, order_type="buy")
    await call.answer("Заявка успешно создана!")
@dp.callback_query(F.data.startswith("paid_order_"))
async def process_paid_button(call: CallbackQuery, state: FSMContext):
    order_id = call.data.replace("paid_order_", "")
    
    # Проверяем, что заявка ещё активна
    status = get_order_status(order_id)
    if status != "pending":
        await call.answer("Заявка уже обработана или отменена.", show_alert=True)
        return
    
    # Убираем клавиатуру, чтобы кнопка исчезла
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except:
        pass  # если не получилось — просто продолжаем
    
    # Отвечаем пользователю
    await call.message.answer(
        "✅ пришлите, пожалуйста, чек оплаты (фото или скриншот)."
    )
    
    # Переводим в состояние ожидания чека
    await state.set_state(OrderStates.waiting_check)
    await state.update_data(order_id=order_id)
    
    # Завершаем обработку callback
    await call.answer("Отмечено как оплачено!")
@dp.callback_query(F.data == "sell")
async def open_sell(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(SELL_TEXT, reply_markup=kb_sell_select(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "sell_btc")
async def sell_btc(call: CallbackQuery, state: FSMContext):
    await state.update_data(currency="BTC", coin_id="bitcoin", order_type="sell")
    rate = get_cached_rate("bitcoin")
    if rate is None:
        await call.message.edit_text("❌ Курс BTC ещё не загружен. Попробуйте позже.", reply_markup=kb_back())
        await call.answer()
        return
    await state.update_data(rate=rate)
    text = f"✅ Валюта: <b>BTC</b>\n✅ Курс продажи: <b>{format_rub(rate)} ₽</b>\n\nВыберите способ получения средств:"
    await call.message.edit_text(text, reply_markup=kb_sell_payment_methods(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "sell_ltc")
async def sell_ltc(call: CallbackQuery, state: FSMContext):
    await state.update_data(currency="LTC", coin_id="litecoin", order_type="sell")
    rate = get_cached_rate("litecoin")
    if rate is None:
        await call.message.edit_text("❌ Курс LTC ещё не загружен. Попробуйте позже.", reply_markup=kb_back())
        await call.answer()
        return
    await state.update_data(rate=rate)
    text = f"✅ Валюта: <b>LTC</b>\n✅ Курс продажи: <b>{format_rub(rate)} ₽</b>\n\nВыберите способ получения средств:"
    await call.message.edit_text(text, reply_markup=kb_sell_payment_methods(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "sell_pay_card")
async def sell_pay_card(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    await state.update_data(payment_method="Банковская карта")
    text = (
        f"✅ Валюта: <b>{currency}</b>\n"
        f"✅ Курс продажи: <b>{format_rub(rate)} ₽</b>\n"
        "✅ Способ получения: <b>Банковская карта</b>\n\n"
        "💳 Введите реквизиты для получения средств:\n\n"
        "Номер карты (16 цифр без пробелов):"
    )
    await call.message.edit_text(text, reply_markup=kb_sell_amount_back_cancel(), parse_mode=ParseMode.HTML)
    await state.set_state(OrderStates.waiting_sell_payment_details)
    await call.answer()
@dp.callback_query(F.data == "sell_pay_sbp")
async def sell_pay_sbp(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    await state.update_data(payment_method="СБП (Система быстрых платежей)")
    text = (
        f"✅ Валюта: <b>{currency}</b>\n"
        f"✅ Курс продажи: <b>{format_rub(rate)} ₽</b>\n"
        "✅ Способ получения: <b>СБП (Система быстрых платежей)</b>\n\n"
        "Выберите ваш банк для получения средств через СБП:"
    )
    await call.message.edit_text(text, reply_markup=kb_banks(), parse_mode=ParseMode.HTML)
    await state.set_state(OrderStates.waiting_sell_bank)
    await call.answer()
@dp.callback_query(F.data.startswith("bank_"), OrderStates.waiting_sell_bank)
async def process_bank_selection(call: CallbackQuery, state: FSMContext):
    bank_name = call.data.replace("bank_", "")
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    await state.update_data(bank_name=bank_name)
    text = (
        f"✅ Валюта: <b>{currency}</b>\n"
        f"✅ Курс продажи: <b>{format_rub(rate)} ₽</b>\n"
        "✅ Способ получения: <b>СБП (Система быстрых платежей)</b>\n"
        f"✅ Банк: <b>{bank_name}</b>\n\n"
        "💳 Введите реквизиты для получения средств:\n\n"
        f"Номер телефона для {bank_name}\n"
        "Формат: 79001234567 (без +, скобок и дефисов):"
    )
    await call.message.edit_text(text, reply_markup=kb_sell_amount_back_cancel(), parse_mode=ParseMode.HTML)
    await state.set_state(OrderStates.waiting_sell_payment_details)
    await call.answer()
@dp.message(OrderStates.waiting_sell_payment_details)
async def process_sell_payment_details(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    payment_method = data.get("payment_method", "")
    user_input = message.text.strip()
    if "Банковская карта" in payment_method:
        masked_details = mask_card(user_input)
        await state.update_data(payment_details=user_input, masked_details=masked_details)
    else:
        masked_details = mask_phone(user_input)
        await state.update_data(payment_details=user_input, masked_details=masked_details)
    bank_name = data.get("bank_name", "")
    bank_text = f"\n✅ Банк: <b>{bank_name}</b>" if bank_name else ""
    text = (
        f"✅ Валюта: <b>{currency}</b>\n"
        f"✅ Курс продажи: <b>{format_rub(rate)} ₽</b>\n"
        f"✅ Способ получения: <b>{payment_method}</b>{bank_text}\n"
        f"✅ Реквизиты: <code>{masked_details}</code>\n\n"
        "💰 Введите сумму продажи\n\n"
        f"Минимальная сумма: 0.00026071 {currency} (~2000 ₽)\n"
        "Вы можете ввести:\n"
        f"• Сумму в {currency} (например: 0.001 {currency})\n"
        "• Сумму в рублях (например: 5000)"
    )
    await message.answer(text, reply_markup=kb_sell_amount_back_cancel(), parse_mode=ParseMode.HTML)
    await state.set_state(OrderStates.waiting_sell_amount)
@dp.message(OrderStates.waiting_sell_amount)
async def process_sell_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    rate = data.get("rate", 0)
    user_input = message.text.strip().upper().replace(",", ".")
    is_crypto = currency in user_input or "." in user_input

    try:
        if is_crypto:
            amount_str = user_input.replace("BTC", "").replace("LTC", "").strip()
            crypto_amount = float(amount_str)
            rub_amount = crypto_amount * rate
        else:
            rub_amount = float(user_input)
            crypto_amount = rub_amount / rate
    except ValueError:
        await message.answer("❌ Неверный формат суммы. Попробуйте еще раз.")
        return

    if rub_amount < 2000:
        min_crypto = 2000 / rate
        await message.answer(
            f"❌ Минимальная сумма продажи: {format_crypto(min_crypto)} {currency}\n"
            "Попробуйте ввести большую сумму."
        )
        return

    commission_percent = config["commission_percent"]
    commission_crypto = crypto_amount * commission_percent
    commission_rub = commission_crypto * rate
    rub_amount_net = rub_amount - commission_rub

    await state.update_data(
        rub_amount=rub_amount_net,
        crypto_amount=crypto_amount,
        commission_crypto=commission_crypto,
        commission_rub=commission_rub
    )

    text = (
        "💰 <b>Детали продажи:</b>\n\n"
        f"Вы отдаете: <b>{format_crypto(crypto_amount)} {currency}</b>\n"
        f"Вы получите: <b>{format_rub(rub_amount_net)} ₽</b>\n"
        f"Курс {currency}: <b>{format_rub(rate)} ₽</b>\n"
        f"Комиссия обменника ({commission_percent*100:.0f}%): <b>≈ {format_rub(commission_rub)} ₽</b>\n\n"
        "🎁 У вас есть промокод?\n\n"
        "Введите промокод или нажмите \"Пропустить\""
    )

    await message.answer(
        text,
        reply_markup=kb_sell_promo_skip(),
        parse_mode=ParseMode.HTML
    )
    await state.set_state(OrderStates.waiting_sell_promo)
@dp.callback_query(F.data == "skip_sell_promo", OrderStates.waiting_sell_promo)
async def skip_sell_promo(call: CallbackQuery, state: FSMContext):
    await show_sell_confirmation(call.message, state)
    await call.answer()
@dp.message(OrderStates.waiting_sell_promo)
async def process_sell_promo(message: Message, state: FSMContext):
    promo_code = message.text.strip()
    await state.update_data(promo_code=promo_code)
    await show_sell_confirmation(message, state)
async def show_sell_confirmation(message: Message, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "BTC")
    crypto_amount = data.get("crypto_amount", 0)
    rate = data.get("rate", 0)
    rub_amount = data.get("rub_amount", 0)
    payment_method = data.get("payment_method", "")
    masked_details = data.get("masked_details", "")
    bank_name = data.get("bank_name", "")
    bank_text = f"\n<b>Банк:</b> {bank_name}" if bank_name else ""
    text = (
        "📋 <b>Подтверждение заявки</b>\n\n"
        f"<b>Валюта:</b> {currency}\n"
        f"<b>Количество:</b> {format_crypto(crypto_amount)} {currency}\n"
        f"<b>Курс:</b> {format_rub(rate)} ₽\n"
        f"<b>Сумма:</b> {format_rub(rub_amount)} ₽\n\n"
        f"<b>Способ получения:</b> {payment_method}{bank_text}\n"
        f"<b>Реквизиты:</b> {masked_details}\n\n"
        "⚠️ После подтверждения вам будет отправлен адрес для перевода криптовалюты"
    )
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb_confirm_sell_order(), parse_mode=ParseMode.HTML)
    else:
        await message.edit_text(text, reply_markup=kb_confirm_sell_order(), parse_mode=ParseMode.HTML)
@dp.callback_query(F.data == "confirm_sell_order")
async def confirm_sell_order_handler(call: CallbackQuery, state: FSMContext):
    global config
    data = await state.get_data()
    await call.message.edit_text("⏳ Создаем заявку... Пожалуйста, подождите.", parse_mode=ParseMode.HTML)
    await asyncio.sleep(3)
    wallet_addresses = config["wallet_addresses"]
    currency = data.get("currency", "BTC")
    bot_wallet = wallet_addresses.get(currency)
    if not bot_wallet:
        error_text = "❌ Не удалось получить адрес для отправки криптовалюты.\n\n⏳ Попробуйте позже."
        await call.message.edit_text(error_text, reply_markup=kb_back(), parse_mode=ParseMode.HTML)
        await call.answer()
        await state.clear()
        return
    order_id = create_order(
        user_id=call.from_user.id,
        order_type="sell",
        currency=currency,
        crypto_amount=data.get("crypto_amount"),
        rub_amount=data.get("rub_amount"),
        rate=data.get("rate"),
        commission=data.get("commission_crypto"),
        payment_method=data.get("payment_method"),
        payment_details=data.get("payment_details"),
        wallet_address=bot_wallet,
        promo_code=data.get("promo_code")
    )
    crypto_amount = data.get("crypto_amount", 0)
    rub_amount = data.get("rub_amount", 0)
    text = (
        f"✅ Заявка #{order_id} создана!\n\n"
        f"📍 Отправьте {format_crypto(crypto_amount)} {currency} на адрес:\n\n"
        f"<code>{bot_wallet}</code>\n\n"
        f"💰 Вы получите: {format_rub(rub_amount)} ₽\n\n"
        "⏱️ Оплатите в течение 30 минут. После оплаты ожидайте подтверждение."
    )
    await call.message.edit_text(text, reply_markup=kb_cancel_order(order_id), parse_mode=ParseMode.HTML)
    await call.message.answer("Прикрепите чек оплаты (скрин транзакции в формате PDF/DOCX или изображение).")
    await state.set_state(OrderStates.waiting_check)
    await state.update_data(order_id=order_id, order_type="sell")
    await call.answer("Заявка успешно создана!")
@dp.message(OrderStates.waiting_check, F.photo | F.document.as_("doc"))
async def process_check(message: Message, state: FSMContext, doc: Document = None):
    data = await state.get_data()
    order_id = data.get("order_id")
    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
    elif doc:
        mime = doc.mime_type
        allowed_mimes = [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "image/jpeg",
            "image/png"
        ]
        if mime not in allowed_mimes:
            await message.answer("Неверный формат. Пришлите PDF, DOCX или изображение.")
            return
        file_id = doc.file_id
        file_type = "document"
    else:
        await message.answer("Пришлите фото или документ.")
        return
    update_order_check(order_id, file_id, file_type)
    await message.answer("Спасибо! ✅ Чек принят!\n Ожидайте подтверждения от оператора!")
    await notify_admins_order_with_check(message.bot, order_id, file_id, file_type)
    await state.clear()
async def notify_admins_order_with_check(bot: Bot, order_id: str, file_id: str, file_type: str):
    global config
    user_id = get_order_user_id(order_id)
    first_name = get_user_first_name(user_id)
    order_type, currency, crypto_amount, rub_amount, rate, commission, payment_method, payment_details_str, wallet_address, promo_code = get_order_details(order_id)
    payment_details = json.loads(payment_details_str) if payment_details_str else {}
    type_text = "Покупка" if order_type == "buy" else "Продажа"
    details_text = f"Метод оплаты: {payment_method}\n"
    if order_type == "buy":
        details_text += f"Реквизиты: {payment_details.get('bank', '')} {format_card_number(payment_details.get('number', ''))}\n"
    else:
        details_text += f"Реквизиты: {payment_details_str}\n"
    text = (
        f"🆕 Новая заявка! #{order_id}\n\n"
        f"Тип: <b>{type_text}</b>\n"
        f"Пользователь: {first_name} <code>({user_id})</code>\n"
        f"Валюта: <b>{currency}</b>\n"
        f"Сумма в крипте: <i>{format_crypto(crypto_amount)} {currency}</i>\n"
        f"Сумма в RUB: <code>{format_rub(rub_amount)}</code> ₽\n"
        f"{details_text}"
        f"Кошелек: <code>{wallet_address}</code>\n"
        f"Промокод: <u>{promo_code if promo_code else 'Нет'}</u>\n"
        f"Время (MSK): <i>{(datetime.now() + timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S MSK')}</i>"
    )
    for admin_id in config["admins"]:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML)
            if file_type == "photo":
                await bot.send_photo(admin_id, file_id, caption="Чек оплаты", reply_markup=kb_order_approval(order_id))
            elif file_type == "document":
                await bot.send_document(admin_id, file_id, caption="Чек оплаты", reply_markup=kb_order_approval(order_id))
        except:
            pass
async def notify_admins_order_cancelled(user_id, order_id, order_type):
    bot = Bot(token=BOT_TOKEN)
    first_name = get_user_first_name(user_id)
    msk_time = (datetime.now() + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S MSK")
    type_text = "Покупка" if order_type == "buy" else "Продажа"
    text = (
        f"❌ Заявка #{order_id} отменена!\n\n"
        f"Тип: {type_text}\n"
        f"Пользователь: {first_name} ({user_id})\n"
        f"Время (MSK): {msk_time}"
    )
    for admin_id in config["admins"]:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML)
        except:
            pass
    await bot.session.close()
@dp.callback_query(F.data.startswith("approve_order_"))
async def approve_order_handler(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    order_id = call.data.replace("approve_order_", "")
    status = get_order_status(order_id)
    if status != "pending":
        await call.answer("Заявка уже обработана.")
        return
    update_order_status(order_id, "approved")
    user_id = get_order_user_id(order_id)
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(user_id, f"✅ Ваша заявка #{order_id} подтверждена!", parse_mode=ParseMode.HTML)
    await bot.session.close()
    await call.message.edit_text(call.message.text + "\n\n✅ Подтверждено!", reply_markup=None)
    await call.answer("Заявка подтверждена!")
@dp.callback_query(F.data.startswith("reject_order_"))
async def reject_order_handler(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    order_id = call.data.replace("reject_order_", "")
    status = get_order_status(order_id)
    if status != "pending":
        await call.answer("Заявка уже обработана.")
        return
    update_order_status(order_id, "rejected")
    user_id = get_order_user_id(order_id)
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(user_id, f"❌ Ваша заявка #{order_id} отклонена.", parse_mode=ParseMode.HTML)
    await bot.session.close()
    await call.message.edit_text(call.message.text + "\n\n❌ Отклонено!", reply_markup=None)
    await call.answer("Заявка отклонена!")
@dp.callback_query(F.data == "orders")
async def show_orders(call: CallbackQuery):
    orders = get_user_active_orders(call.from_user.id)
    if not orders:
        await call.message.edit_text("У вас нет активных заявок.", reply_markup=kb_back())
        await call.answer()
        return
    text = "📋 <b>Ваши активные заявки:</b>\n\n"
    for order_id, order_type, currency, crypto_amount, rub_amount, status, created_at, expires_at in orders:
        order_type_text = "🟢 Покупка" if order_type == "buy" else "🔴 Продажа"
        text += (
            f"{order_type_text} | {currency}\n"
            f"├ Количество: {format_crypto(crypto_amount)} {currency}\n"
            f"├ Сумма: {format_rub(rub_amount)} ₽\n"
            f"└ ID: <code>{order_id}</code>\n\n"
        )
    await call.message.edit_text(text, reply_markup=kb_back(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order_handler(call: CallbackQuery):
    order_id = call.data.replace("cancel_order_", "")
    # Получаем детали заявки до отмены
    order_details = get_order_details(order_id)
    if order_details:
        order_type, currency, crypto_amount, rub_amount, rate, commission, payment_method, payment_details_str, wallet_address, promo_code = order_details
    
        # Парсим payment_details обратно в словарь
        try:
            payment_details = json.loads(payment_details_str)
        except:
            payment_details = {}
    
        # Формируем текст заявки (как при создании)
        if "Банковская карта" in payment_method:
            formatted_number = format_card_number(payment_details.get('number', 'Не указан'))
            bank = payment_details.get('bank', 'Не указан')
            holder = payment_details.get('holder', '')
        
            details_text = (
                f"✅ Заявка #{order_id} создана!\n\n"
                f"💳 Реквизиты для оплаты:\n\n"
                f"Номер карты: {formatted_number}\n"
                f"Получатель: <code>{bank}</code> <code>{holder}</code>\n\n"
                f"💰 Сумма к оплате: {format_rub(rub_amount)} ₽\n\n"
                f"⏱️ Оплатите в течение 30 минут. После оплаты ожидайте подтверждение."
            )
            await call.message.answer(details_text)
    # Отменяем заявку
    cancel_order(order_id)
    # Сообщение об отмене
    await call.message.answer(
        f"❌ Заявка #{order_id} отменена.\n"
        f"Вы можете создать новую заявку в главном меню.",
        reply_markup=kb_main_menu() # лучше вернуться в главное меню
    )
    user_id = get_order_user_id(order_id)
    if user_id:
        await notify_admins_order_cancelled(user_id, order_id, order_type)
    await call.answer("Заявка отменена")
@dp.callback_query(F.data == "rates")
async def show_rates(call: CallbackQuery):
    text = await rates_text()
    await call.message.edit_text(text, reply_markup=kb_back(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "settings")
async def open_settings(call: CallbackQuery):
    await call.message.edit_text(SETTINGS_TEXT, reply_markup=get_notifications_kb(call.from_user.id), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "notif_on")
async def notif_on(call: CallbackQuery):
    settings = load_settings()
    user_id = str(call.from_user.id)
    if user_id not in settings:
        settings[user_id] = {}
    settings[user_id]["notifications"] = True
    save_settings(settings)
    await call.message.edit_text(SETTINGS_TEXT, reply_markup=get_notifications_kb(call.from_user.id), parse_mode=ParseMode.HTML)
    await call.answer("🔔 Уведомления включены")
@dp.callback_query(F.data == "notif_off")
async def notif_off(call: CallbackQuery):
    settings = load_settings()
    user_id = str(call.from_user.id)
    if user_id not in settings:
        settings[user_id] = {}
    settings[user_id]["notifications"] = False
    save_settings(settings)
    await call.message.edit_text(SETTINGS_TEXT, reply_markup=get_notifications_kb(call.from_user.id), parse_mode=ParseMode.HTML)
    await call.answer("🔕 Уведомления отключены")
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    text = (
        "🆘 <b>Поддержка</b>\n\n"
        "Для получения помощи обратитесь к нашему оператору:\n\n"
        "⏱️ Время работы: 24/7\n"
        "⏱️ Время ответа: ⚡️ моментально\n\n"
        "❓ <b>Частые вопросы:</b>\n"
        "1. Как долго обрабатываются заявки?\n"
        " - До 10 минут\n"
        " - Зависит от нагрузки сети и как быстро вы проведете оплату\n"
        "2. Какие комиссии взимаются?\n"
        " - 18% за покупку BTC/USDT/LTC\n"
        " - 18% за продажу BTC/USDT/LTC\n"
        "3. Как работает реферальная программа?\n"
        " - Приглашайте друзей и получайте 0.2% от их обменов"
    )
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💬 Написать оператору", url=get_support_chat_url()))
    kb.row(InlineKeyboardButton(text="« Назад", callback_data="menu"))
    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "ref")
async def referral(call: CallbackQuery):
    text = (
        "👥 <b>Реферальная программа</b>\n\n"
        "💰 Получайте <b>0.2%</b> от суммы каждой сделки ваших рефералов!\n\n"
        "⬇️ <b>Ваша партнерская ссылка:</b>\n"
        f"<code>https://t.me/{BOT_USERNAME}?start=ref{call.from_user.id}</code>\n\n"
        "📊 <b>Статистика:</b>\n"
        "├ Количество рефералов: 0\n"
        "├ Всего заработано: 0.00 ₽\n"
        "└ Доступно для вывода: 0.00 ₽\n\n"
        "💡 Приглашайте друзей и зарабатывайте!"
    )
    await call.message.edit_text(text, reply_markup=kb_back(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "promo")
async def promo_info(call: CallbackQuery):
    text = (
        "🎁 <b>Промокоды</b>\n\n"
        "❓ <b>Как использовать:</b>\n"
        "Промокод применяется при создании заявки на обмен.\n"
        "Один промокод можно использовать только один раз."
    )
    await call.message.edit_text(text, reply_markup=kb_back(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "back_to_menu")
async def admin_back_to_menu(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    await state.clear()
    text = "🔐 <b>Админ-панель</b> 👨‍💻\n\nВыберите действие:"
    await call.message.edit_text(text, reply_markup=kb_admin_main(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = (
        "📢 <b>Рассылка сообщений</b> 📮\n\n"
        "Введите текст для рассылки всем пользователям:\n\n"
        "Вы можете использовать HTML форматирование:\n"
        "<code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "<code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "<code>&lt;code&gt;код&lt;/code&gt;</code>"
    )
    await call.message.edit_text(text, reply_markup=kb_cancel_broadcast(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_broadcast)
    await call.answer()
@dp.message(AdminStates.waiting_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    broadcast_text = message.text
    bot = Bot(token=BOT_TOKEN)
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    success = 0
    failed = 0
    status_msg = await message.answer("📤 Начинаю рассылку...")
    for user_tuple in users:
        user_id = user_tuple[0]
        try:
            await bot.send_message(user_id, broadcast_text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await bot.session.close()
    await status_msg.edit_text(
        f"✅ Рассылка завершена! 🎉\n\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}",
        reply_markup=kb_back_to_menu()
    )
    await state.clear()
@dp.callback_query(F.data == "admin_payment_details")
async def admin_payment_details(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    global config
    payment_details = config["payment_details"]
    card = payment_details.get("card", {})
    sbp = payment_details.get("sbp", {})
    transgran = payment_details.get("transgran", {})
    qr = payment_details.get("qr", {})
    text = (
        "💳 <b>Текущие реквизиты для покупки:</b> 💰\n\n"
        f"Карта: <code>{card.get('number', 'Не указана')}</code>\n"
        f"Банк карты: {card.get('bank', 'Не указан')}\n"
        f"Владелец: {card.get('holder', 'Не указан')}\n\n"
        f"СБП телефон: <code>{sbp.get('phone', 'Не указан')}</code>\n"
        f"СБП банк: {sbp.get('bank', 'Не указан')}\n\n"
        f"Трансгран карта: <code>{transgran.get('number', 'Не указана')}</code>\n"
        f"Трансгран банк: {transgran.get('bank', 'Не указан')}\n"
        f"Трансгран получатель: {transgran.get('holder', 'Не указан')}\n\n"
        f"QR описание: {qr.get('description', 'Не указано')}\n"
        f"QR изображение: {'Указано' if qr.get('image_file_id') else 'Не указано'}"
    )
    await call.message.edit_text(text, reply_markup=kb_payment_details_menu(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "admin_change_all")
async def admin_change_all(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "🔄 Изменение всех реквизитов сразу\n\nВведите банк:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_all_bank)
    await call.answer()
@dp.message(AdminStates.waiting_new_all_bank)
async def process_new_all_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    bank = message.text.strip()
    await state.update_data(new_all_bank=bank)
    text = "Введите номер карты (для card и transgran):"
    await message.answer(text)
    await state.set_state(AdminStates.waiting_new_all_number)
@dp.message(AdminStates.waiting_new_all_number)
async def process_new_all_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    number = message.text.strip()
    await state.update_data(new_all_number=number)
    text = "Введите имя получателя (для card и transgran):"
    await message.answer(text)
    await state.set_state(AdminStates.waiting_new_all_holder)
@dp.message(AdminStates.waiting_new_all_holder)
async def process_new_all_holder(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    holder = message.text.strip()
    await state.update_data(new_all_holder=holder)
    text = "Введите телефон для СБП:"
    await message.answer(text)
    await state.set_state(AdminStates.waiting_new_all_phone)
@dp.message(AdminStates.waiting_new_all_phone)
async def process_new_all_phone(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    phone = message.text.strip()
    data = await state.get_data()
    bank = data.get('new_all_bank')
    number = data.get('new_all_number')
    holder = data.get('new_all_holder')
    if "card" not in config["payment_details"] or not isinstance(config["payment_details"]["card"], dict):
        config["payment_details"]["card"] = {}
    if "sbp" not in config["payment_details"] or not isinstance(config["payment_details"]["sbp"], dict):
        config["payment_details"]["sbp"] = {}
    if "transgran" not in config["payment_details"] or not isinstance(config["payment_details"]["transgran"], dict):
        config["payment_details"]["transgran"] = {}
    config["payment_details"]["card"]["bank"] = bank
    config["payment_details"]["card"]["number"] = number
    config["payment_details"]["card"]["holder"] = holder
    config["payment_details"]["sbp"]["bank"] = bank
    config["payment_details"]["sbp"]["phone"] = phone
    config["payment_details"]["transgran"]["bank"] = bank
    config["payment_details"]["transgran"]["number"] = number
    config["payment_details"]["transgran"]["holder"] = holder
    save_config(config)
    await message.answer("✅ Все реквизиты обновлены! 🎉", reply_markup=kb_back_to_menu())
    await state.clear()
@dp.callback_query(F.data == "admin_change_card")
async def admin_change_card(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "💳 Введите новый номер карты:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_card)
    await call.answer()
@dp.message(AdminStates.waiting_new_card)
async def process_new_card(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    card = message.text.strip()
    if "card" not in config["payment_details"] or not isinstance(config["payment_details"]["card"], dict):
        config["payment_details"]["card"] = {}
    config["payment_details"]["card"]["number"] = card
    save_config(config)
    await message.answer(
        f"✅ Номер карты успешно изменен на:\n<code>{card}</code> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_card_bank")
async def admin_change_card_bank(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "🏦 Введите новый банк для карты:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_card_bank)
    await call.answer()
@dp.message(AdminStates.waiting_new_card_bank)
async def process_new_card_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    bank = message.text.strip()
    if "card" not in config["payment_details"] or not isinstance(config["payment_details"]["card"], dict):
        config["payment_details"]["card"] = {}
    config["payment_details"]["card"]["bank"] = bank
    save_config(config)
    await message.answer(
        f"✅ Банк карты успешно изменен на: <b>{bank}</b> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_card_holder")
async def admin_change_card_holder(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "👤 Введите нового получателя для карты:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_card_holder)
    await call.answer()
@dp.message(AdminStates.waiting_new_card_holder)
async def process_new_card_holder(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    holder = message.text.strip()
    if "card" not in config["payment_details"] or not isinstance(config["payment_details"]["card"], dict):
        config["payment_details"]["card"] = {}
    config["payment_details"]["card"]["holder"] = holder
    save_config(config)
    await message.answer(
        f"✅ Получатель карты успешно изменен на: <b>{holder}</b> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_sbp_phone")
async def admin_change_sbp_phone(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "📱 Введите новый номер телефона для СБП:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_sbp_phone)
    await call.answer()
@dp.message(AdminStates.waiting_new_sbp_phone)
async def process_new_sbp_phone(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    phone = message.text.strip()
    if "sbp" not in config["payment_details"] or not isinstance(config["payment_details"]["sbp"], dict):
        config["payment_details"]["sbp"] = {}
    config["payment_details"]["sbp"]["phone"] = phone
    save_config(config)
    await message.answer(
        f"✅ Номер телефона СБП успешно изменен на:\n<code>{phone}</code> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_sbp_bank")
async def admin_change_sbp_bank(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "🏦 Введите название банка для СБП:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_sbp_bank)
    await call.answer()
@dp.message(AdminStates.waiting_new_sbp_bank)
async def process_new_sbp_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    bank = message.text.strip()
    if "sbp" not in config["payment_details"] or not isinstance(config["payment_details"]["sbp"], dict):
        config["payment_details"]["sbp"] = {}
    config["payment_details"]["sbp"]["bank"] = bank
    save_config(config)
    await message.answer(
        f"✅ Банк СБП успешно изменен на: <b>{bank}</b> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_transgran_number")
async def admin_change_transgran_number(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "🌍 Введите новый номер трансгран карты:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_transgran_number)
    await call.answer()
@dp.message(AdminStates.waiting_new_transgran_number)
async def process_new_transgran_number(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    number = message.text.strip()
    if "transgran" not in config["payment_details"] or not isinstance(config["payment_details"]["transgran"], dict):
        config["payment_details"]["transgran"] = {}
    config["payment_details"]["transgran"]["number"] = number
    save_config(config)
    await message.answer(
        f"✅ Номер трансгран карты успешно изменен на:\n<code>{number}</code> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_transgran_bank")
async def admin_change_transgran_bank(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "🏦 Введите новый банк для трансгран:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_transgran_bank)
    await call.answer()
@dp.message(AdminStates.waiting_new_transgran_bank)
async def process_new_transgran_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    bank = message.text.strip()
    if "transgran" not in config["payment_details"] or not isinstance(config["payment_details"]["transgran"], dict):
        config["payment_details"]["transgran"] = {}
    config["payment_details"]["transgran"]["bank"] = bank
    save_config(config)
    await message.answer(
        f"✅ Банк трансгран успешно изменен на: <b>{bank}</b> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_transgran_holder")
async def admin_change_transgran_holder(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "👤 Введите нового получателя для трансгран:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_transgran_holder)
    await call.answer()
@dp.message(AdminStates.waiting_new_transgran_holder)
async def process_new_transgran_holder(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    holder = message.text.strip()
    if "transgran" not in config["payment_details"] or not isinstance(config["payment_details"]["transgran"], dict):
        config["payment_details"]["transgran"] = {}
    config["payment_details"]["transgran"]["holder"] = holder
    save_config(config)
    await message.answer(
        f"✅ Получатель трансгран успешно изменен на: <b>{holder}</b> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_qr_image")
async def admin_change_qr_image(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "📸 Отправьте новое изображение QR-кода:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_qr_image)
    await call.answer()
@dp.message(AdminStates.waiting_new_qr_image, F.photo)
async def process_new_qr_image(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    file_id = message.photo[-1].file_id
    if "qr" not in config["payment_details"] or not isinstance(config["payment_details"]["qr"], dict):
        config["payment_details"]["qr"] = {}
    config["payment_details"]["qr"]["image_file_id"] = file_id
    save_config(config)
    await message.answer(
        f"✅ Изображение QR успешно обновлено! 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_qr_description")
async def admin_change_qr_description(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "📝 Введите новое описание для QR:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_qr_description)
    await call.answer()
@dp.message(AdminStates.waiting_new_qr_description)
async def process_new_qr_description(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    description = message.text.strip()
    if "qr" not in config["payment_details"] or not isinstance(config["payment_details"]["qr"], dict):
        config["payment_details"]["qr"] = {}
    config["payment_details"]["qr"]["description"] = description
    save_config(config)
    await message.answer(
        f"✅ Описание QR успешно изменено на: <b>{description}</b> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_wallet_addresses")
async def admin_wallet_addresses(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    global config
    wallet_addresses = config["wallet_addresses"]
    text = (
        "🔑 <b>Текущие адреса кошельков для продажи:</b> 🔐\n\n"
        f"BTC: <code>{wallet_addresses.get('BTC', 'Не указан')}</code>\n"
        f"LTC: <code>{wallet_addresses.get('LTC', 'Не указан')}</code>"
    )
    await call.message.edit_text(text, reply_markup=kb_wallet_addresses_menu(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "admin_change_btc")
async def admin_change_btc(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "₿ Введите новый BTC адрес:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_btc_address)
    await call.answer()
@dp.message(AdminStates.waiting_new_btc_address)
async def process_new_btc_address(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    address = message.text.strip()
    if not validate_btc_address(address):
        await message.answer("❌ Неверный формат BTC адреса. Попробуйте еще раз.")
        return
    config["wallet_addresses"]["BTC"] = address
    save_config(config)
    await message.answer(
        f"✅ BTC адрес успешно изменен на:\n<code>{address}</code> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_change_ltc")
async def admin_change_ltc(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "Ł Введите новый LTC адрес:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_ltc_address)
    await call.answer()
@dp.message(AdminStates.waiting_new_ltc_address)
async def process_new_ltc_address(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    address = message.text.strip()
    if not validate_ltc_address(address):
        await message.answer("❌ Неверный формат LTC адреса. Попробуйте еще раз.")
        return
    config["wallet_addresses"]["LTC"] = address
    save_config(config)
    await message.answer(
        f"✅ LTC адрес успешно изменен на:\n<code>{address}</code> 🎉",
        reply_markup=kb_back_to_menu(),
        parse_mode=ParseMode.HTML
    )
    await state.clear()
@dp.callback_query(F.data == "admin_operators")
async def admin_operators(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    global config
    admins = config["admins"]
    text = "👥 <b>Управление админами:</b> 👨‍💼\n\n" + "\n".join([f"• {admin_id}" for admin_id in admins])
    await call.message.edit_text(text, reply_markup=kb_operators_menu(), parse_mode=ParseMode.HTML)
    await call.answer()
@dp.callback_query(F.data == "admin_add_operator")
async def admin_add_operator(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    text = "➕ Введите ID нового оператора:"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_operator_id)
    await call.answer()
@dp.message(AdminStates.waiting_new_operator_id)
async def process_new_operator_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    try:
        new_id = int(message.text.strip())
        if new_id not in config["admins"]:
            add_admin(new_id)
            await message.answer(f"✅ Оператор {new_id} добавлен! 🎉", reply_markup=kb_back_to_menu())
        else:
            await message.answer(f"❌ Оператор {new_id} уже существует.", reply_markup=kb_back_to_menu())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.", reply_markup=kb_back_to_menu())
    await state.clear()
@dp.message(AdminStates.waiting_new_operator_id)
async def process_new_operator_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    try:
        new_id = int(message.text.strip())
        if new_id not in config["admins"]:
            add_admin(new_id)
            await message.answer(f"✅ Оператор {new_id} добавлен! 🎉", reply_markup=kb_back_to_menu())
        else:
            await message.answer(f"❌ Оператор {new_id} уже существует.", reply_markup=kb_back_to_menu())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.", reply_markup=kb_back_to_menu())
    await state.clear()
@dp.callback_query(F.data.startswith("admin_remove_operator_"))
async def admin_remove_operator(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    global config
    remove_id = int(call.data.replace("admin_remove_operator_", ""))
    if remove_id == ADMIN_ID:
        await call.answer("❌ Нельзя удалить основного администратора.", show_alert=True)
        return
    remove_admin(remove_id)
    admins = config["admins"]
    text = "👥 <b>Управление операторами:</b> 👨‍💼\n\n" + "\n".join([f"• {admin_id}" for admin_id in admins])
    await call.message.edit_text(text, reply_markup=kb_operators_menu(), parse_mode=ParseMode.HTML)
    await call.answer(f"✅ Оператор {remove_id} удален! 🎉")
@dp.callback_query(F.data == "admin_change_commission")
async def admin_change_commission(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    current_commission = config["commission_percent"] * 100
    text = f"💱 Текущая комиссия: {current_commission:.0f}%\n\nВведите новый процент комиссии (например: 18 для 18%):"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_commission)
    await call.answer()
@dp.message(AdminStates.waiting_new_commission)
async def process_new_commission(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    try:
        percent = float(message.text.strip())
        if percent < 0 or percent > 100:
            raise ValueError
        config["commission_percent"] = percent / 100
        save_config(config)
        await message.answer(
            f"✅ Комиссия успешно изменена на {percent:.0f}%! 🎉",
            reply_markup=kb_back_to_menu(),
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число от 0 до 100.", reply_markup=kb_back_to_menu())
    await state.clear()
@dp.callback_query(F.data == "admin_change_support_url")
async def admin_change_support_url(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    current_url = get_support_chat_url()
    text = f"💬 Текущая ссылка оператора: {current_url}\n\nВведите новую ссылку (например: https://t.me/new_support):"
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_new_support_url)
    await call.answer()
@dp.message(AdminStates.waiting_new_support_url)
async def process_new_support_url(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    global config
    new_url = message.text.strip()
    if not new_url.startswith(("http://", "https://", "t.me/", "@")):
        await message.answer("❌ Неверный формат ссылки. Введите корректную ссылку (например: https://t.me/support):", reply_markup=kb_back_to_menu())
        return
    config["support_chat_url"] = new_url
    save_config(config)
    await message.answer(f"✅ Ссылка оператора успешно изменена! 🎉\n\nНовая ссылка: {new_url}", reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await state.clear()
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌ Доступ запрещен", show_alert=True)
        return
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
    except:
        total_users = 0
    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
    pending_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM orders WHERE status = 'cancelled'")
    cancelled_orders = cursor.fetchone()[0]
    conn.close()
    text = (
        "📊 <b>Статистика бота</b> 📈\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"📋 Всего заявок: <b>{total_orders}</b>\n"
        f"⏳ Активных заявок: <b>{pending_orders}</b>\n"
        f"❌ Отмененных заявок: <b>{cancelled_orders}</b>"
    )
    await call.message.edit_text(text, reply_markup=kb_back_to_menu(), parse_mode=ParseMode.HTML)
    await call.answer()
async def main():
    asyncio.create_task(rates_updater())
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
