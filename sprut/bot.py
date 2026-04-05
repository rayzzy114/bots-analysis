import asyncio
import logging
import math
import os
import re
import sqlite3
import aiohttp
import string
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from utils.env_writer import update_env_var

load_dotenv()

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_FILE = "bot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verified_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS luck_last_used (
            user_id INTEGER PRIMARY KEY,
            last_used TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency TEXT NOT NULL,
            method_name TEXT NOT NULL,
            price_rub REAL NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_requisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER NOT NULL,
            requisite_type TEXT NOT NULL,
            requisite_value TEXT NOT NULL,
            FOREIGN KEY (method_id) REFERENCES exchange_payment_methods(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposit_addresses (
            currency TEXT PRIMARY KEY,
            address TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            currency TEXT NOT NULL,
            amount_rub REAL NOT NULL,
            crypto_amount REAL NOT NULL,
            method_id INTEGER NOT NULL,
            wallet_address TEXT,
            status TEXT DEFAULT 'processing',
            created_at TEXT NOT NULL,
            receipt_sent INTEGER DEFAULT 0
        )
    ''')
    
    try:
        cursor.execute('ALTER TABLE orders ADD COLUMN wallet_address TEXT')
    except Exception as e:
        print(f'Exception caught: {e}')
    
    conn.commit()
    conn.close()

def is_user_verified(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM verified_users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone() is not None
    conn.close()
    return result

def add_verified_user(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO verified_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()

def get_luck_last_used(user_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('SELECT last_used FROM luck_last_used WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return datetime.fromisoformat(result[0])
    return None

def set_luck_last_used(user_id, last_used):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO luck_last_used (user_id, last_used)
        VALUES (?, ?)
    ''', (user_id, last_used.isoformat()))
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id):
    admin_ids_str = os.getenv("ADMIN_ID", "")
    if admin_ids_str:
        admin_ids = admin_ids_str.split(",")
        for admin_id_str in admin_ids:
            admin_id_str = admin_id_str.strip()
            if admin_id_str.isdigit():
                try:
                    if int(admin_id_str) == user_id:
                        return True
                except:
                    continue
    return False

def get_exchange_payment_methods(currency):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, method_name, price_rub 
        FROM exchange_payment_methods 
        WHERE is_active = 1
        ORDER BY id
    ''')
    result = cursor.fetchall()
    conn.close()
    return result

def get_exchange_requisites(method_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT requisite_type, requisite_value 
        FROM exchange_requisites 
        WHERE method_id = ?
    ''', (method_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_exchange_requisites_with_id(method_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, requisite_type, requisite_value 
        FROM exchange_requisites 
        WHERE method_id = ?
    ''', (method_id,))
    result = cursor.fetchall()
    conn.close()
    return result

def delete_exchange_requisite(requisite_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM exchange_requisites WHERE id = ?', (requisite_id,))
    conn.commit()
    conn.close()

def update_exchange_requisite(requisite_id, requisite_value):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('UPDATE exchange_requisites SET requisite_value = ? WHERE id = ?', (requisite_value, requisite_id))
    conn.commit()
    conn.close()

def format_requisite_display(req_type, req_value):
    req_type_clean = req_type.strip()
    if req_type_clean and re.match(r'^[\d\s\-]+$', req_type_clean):
        return f"• <code>{req_value}</code>"
    else:
        return f"• {req_type}: <code>{req_value}</code>"

def add_payment_method(currency, method_name, price_rub):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO exchange_payment_methods (currency, method_name, price_rub)
        VALUES (?, ?, ?)
    ''', ("ALL", method_name, price_rub))
    method_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return method_id

def update_payment_method(method_id, method_name, price_rub, is_active):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE exchange_payment_methods 
        SET method_name = ?, price_rub = ?, is_active = ?
        WHERE id = ?
    ''', (method_name, price_rub, is_active, method_id))
    conn.commit()
    conn.close()

def delete_payment_method(method_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM exchange_payment_methods WHERE id = ?', (method_id,))
    conn.commit()
    conn.close()

def get_all_payment_methods(currency):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, method_name, price_rub, is_active
        FROM exchange_payment_methods 
        ORDER BY id
    ''')
    result = cursor.fetchall()
    conn.close()
    return result

def get_payment_method_by_id(method_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM exchange_payment_methods WHERE id = ?', (method_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def add_requisite(method_id, requisite_type, requisite_value):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO exchange_requisites (method_id, requisite_type, requisite_value)
        VALUES (?, ?, ?)
    ''', (method_id, requisite_type, requisite_value))
    conn.commit()
    conn.close()

# ================== RATE FETCHING ==================

async def get_cbr_usd_rate() -> float:
    """Fetch USD/RUB rate from Central Bank of Russia."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    import json
                    data = json.loads(await response.text())
                    return float(data["Valute"]["USD"]["Value"])
    except Exception as e:
        print(f"CBR error: {e}")
    return 90.0


async def get_btc_rates() -> tuple:
    """Fetch BTC rates from Binance/CoinGecko. Returns (usd, rub)."""
    # Try Binance first
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                    "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                    timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    usd = float(data.get("price", 0))
                    if usd > 0:
                        rub = await get_cbr_usd_rate() * usd
                        return (usd, rub)
    except Exception as e:
        print(f"Binance BTC error: {e}")

    # Fallback to CoinGecko
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    btc = data.get("bitcoin", {})
                    usd = float(btc.get("usd", 0))
                    rub = float(btc.get("rub", 0))
                    if usd > 0 and rub > 0:
                        return (usd, rub)
    except Exception as e:
        print(f"CoinGecko BTC error: {e}")

    # Ultimate fallback to env/config
    btc_rate_rub = float(os.getenv("BTC_RATE_RUB", "9000000"))
    btc_rate_usd = btc_rate_rub / 90.0
    return (btc_rate_usd, btc_rate_rub)


async def get_crypto_rates() -> dict:
    """Get crypto rates. BTC is fetched from API, others from env."""
    btc_usd, btc_rub = await get_btc_rates()
    return {
        'BTC': btc_rub,
        'BTC_USD': btc_usd,
        'LTC': float(os.getenv("LTC_RATE", "6400")),
        'XMR': float(os.getenv("XMR_RATE", "15000")),
        'USDT': float(os.getenv("USDT_RATE", "100"))
    }

async def get_crypto_rate(currency):
    rates = await get_crypto_rates()
    return rates.get(currency)
    
def calculate_crypto_amount(rub_amount, crypto_type):
    rates = get_crypto_rates()
    rate = rates.get(crypto_type, 9000000)
    amount = rub_amount / rate
    return amount


class CaptchaStates(StatesGroup):
    waiting_for_captcha = State()
    waiting_for_promo = State()
    waiting_for_calculator_currency = State()
    waiting_for_calculator_value = State()
    calculator_currency = State()
    waiting_for_history_currency = State()
    waiting_for_history_category = State()
    history_currency = State()
    waiting_for_withdraw_currency = State()
    waiting_for_withdraw_address = State()
    waiting_for_withdraw_amount = State()
    waiting_for_withdraw_confirm = State()
    waiting_for_deposit_currency = State()
    waiting_for_exchange_currency = State()
    waiting_for_exchange_amount = State()
    waiting_for_exchange_payment = State()
    waiting_for_wallet_address = State()
    waiting_for_payment_confirmation = State()
    waiting_for_receipt = State()
    admin_panel = State()
    admin_deposit_address = State()
    admin_manage_methods_currency = State()
    admin_manage_methods_action = State()
    admin_add_method_name = State()
    admin_edit_method = State()
    admin_edit_method_name = State()
    admin_edit_method_price = State()
    admin_manage_requisites_currency = State()
    admin_manage_requisites_method = State()
    admin_add_method_requisite = State()
    admin_edit_requisite_value = State()
    admin_links = State()
    admin_edit_link = State()

def get_main_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📈 Купить"),
                KeyboardButton(text="📉 Продать")
            ],
            [
                KeyboardButton(text="🔐 Кошелек")
            ],
            [
                KeyboardButton(text="💻 Личный кабинет"),
                KeyboardButton(text="👨‍💻 Контакты")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_cabinet_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🏷️ Промокод"),
                KeyboardButton(text="Вывести реф. счет")
            ],
            [
                KeyboardButton(text="🎰 Испытай удачу")
            ],
            [
                KeyboardButton(text="🧮 Калькулятор")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_contacts_keyboard():
    contact_boss = os.getenv("CONTACT_BOSS", "")
    contact_support = os.getenv("CONTACT_SUPPORT", "")
    contact_reviews = os.getenv("CONTACT_REVIEWS", "")
    contact_chat = os.getenv("CONTACT_CHAT", "")
    contact_news = os.getenv("CONTACT_NEWS", "")
    
    buttons = []
    if contact_boss:
        buttons.append([InlineKeyboardButton(text="Босс", url=contact_boss)])
    if contact_support:
        buttons.append([InlineKeyboardButton(text="Поддержка", url=contact_support)])
    if contact_reviews:
        buttons.append([InlineKeyboardButton(text="Отзывы", url=contact_reviews)])
    if contact_chat:
        buttons.append([InlineKeyboardButton(text="Чат", url=contact_chat)])
    if contact_news:
        buttons.append([InlineKeyboardButton(text="Новости", url=contact_news)])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_wallet_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⬆️ Вывод"),
                KeyboardButton(text="⬇️ Пополнить")
            ],
            [
                KeyboardButton(text="💰 Баланс"),
                KeyboardButton(text="📜 История")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_promo_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_calculator_currency_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="BTC"),
                KeyboardButton(text="LTC"),
                KeyboardButton(text="XMR"),
                KeyboardButton(text="USDT")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_history_category_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Вывод"),
                KeyboardButton(text="Депозит")
            ],
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_withdraw_confirm_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="withdraw_confirm")
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="withdraw_cancel")
        ]
    ])
    return keyboard

def get_withdraw_all_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Вывести все"),
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_deposit_method_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⬇️ Депозит"),
                KeyboardButton(text="📩 Пополнить через обменник")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_deposit_info_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Сгенерировать новый адрес", callback_data="generate_new_address")
        ]
    ])
    return keyboard

def get_deposit_address(currency):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('SELECT address FROM deposit_addresses WHERE currency = ?', (currency,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return result[0]
    return ""

def set_deposit_address(currency, address):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO deposit_addresses (currency, address)
        VALUES (?, ?)
    ''', (currency, address))
    conn.commit()
    conn.close()

def get_deposit_min_amount(currency):
    min_amounts = {
        "BTC": "0.00001",
        "LTC": "0.001",
        "XMR": "0.01",
        "USDT": "10"
    }
    return min_amounts.get(currency, "0")

def get_withdraw_min_amount(currency):
    min_amounts = {
        "BTC": 0.00001,
        "LTC": 0.001,
        "XMR": 0.01,
        "USDT": 10
    }
    return min_amounts.get(currency, 0)

def get_user_balance(user_id, currency):
    return 0.0

def get_exchange_currency_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Купить BTC"),
                KeyboardButton(text="🔄 Купить LTC")
            ],
            [
                KeyboardButton(text="🔄 Купить XMR"),
                KeyboardButton(text="🔄 Купить USDT-TRC20")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_buy_currency_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Купить BTC"),
                KeyboardButton(text="🔄 Купить LTC")
            ],
            [
                KeyboardButton(text="🔄 Купить XMR"),
                KeyboardButton(text="🔄 Купить USDT-TRC20")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_exchange_payment_keyboard(methods, amount_to_pay):
    buttons = []
    for method_id, method_name, price_rub in methods:
        method_total = amount_to_pay + price_rub
        buttons.append([InlineKeyboardButton(text=f"✅ {method_name} ({int(method_total)} руб.)", callback_data=f"payment_method_{method_id}")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

def get_exchange_payment_cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❌ Отмена")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_methods_keyboard(methods):
    buttons = []
    for method_id, method_name, price_rub in methods:
        buttons.append([KeyboardButton(text=f"📝 {method_name}")])
    buttons.append([KeyboardButton(text="❌ Отмена")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def get_admin_manage_methods_keyboard(currency, methods):
    buttons = []
    for method_id, method_name, price_rub, is_active in methods:
        status = "✅" if is_active else "❌"
        buttons.append([KeyboardButton(text=f"{status} {method_name}")])
    buttons.append([KeyboardButton(text="➕ Добавить метод оплаты")])
    buttons.append([KeyboardButton(text="❌ Отмена")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def get_admin_method_actions_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="✏️ Редактировать"),
                KeyboardButton(text="🗑️ Удалить")
            ],
            [
                KeyboardButton(text="✅ Активировать"),
                KeyboardButton(text="❌ Деактивировать")
            ],
            [
                KeyboardButton(text="📝 Управление реквизитами")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_requisites_keyboard(requisites):
    buttons = []
    for req_id, req_type, req_value in requisites:
        display_value = req_value[:30] + "..." if len(req_value) > 30 else req_value
        req_type_clean = req_type.strip()
        if req_type_clean and re.match(r'^[\d\s\-]+$', req_type_clean):
            button_text = f"✏️ {display_value}"
        else:
            button_text = f"✏️ {req_type}: {display_value}"
        buttons.append([KeyboardButton(text=button_text)])
    buttons.append([KeyboardButton(text="➕ Добавить реквизит")])
    buttons.append([KeyboardButton(text="❌ Отмена")])
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def get_admin_links_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 rates")],
            [KeyboardButton(text="💰 sell_btc")],
            [KeyboardButton(text="📢 news_channel")],
            [KeyboardButton(text="👨‍💻 operator")],
            [KeyboardButton(text="👨‍💻 operator2")],
            [KeyboardButton(text="📣 operator3")],
            [KeyboardButton(text="🏧 work_operator")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_admin_panel_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⚙️ Управление методами оплаты")
            ],
            [
                KeyboardButton(text="💳 Управление адресами депозитов")
            ],
            [
                KeyboardButton(text="🔗 Ссылки")
            ],
            [
                KeyboardButton(text="⬅️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_payment_confirmation_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я оплатил", callback_data="payment_paid")
        ],
        [
            InlineKeyboardButton(text="❌ Отменить заявку", callback_data="payment_cancel")
        ]
    ])
    return keyboard

def get_receipt_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👍 Прислать чек", callback_data="receipt_send")
        ],
        [
            InlineKeyboardButton(text="👎 Без чека", callback_data="receipt_no")
        ]
    ])
    return keyboard

def get_admin_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_approve_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{order_id}")
        ]
    ])
    return keyboard

def generate_order_id():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(20))

def create_order(user_id, currency, amount_rub, crypto_amount, method_id, wallet_address=None):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    order_id = generate_order_id()
    created_at = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO orders (order_id, user_id, currency, amount_rub, crypto_amount, method_id, wallet_address, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, user_id, currency, amount_rub, crypto_amount, method_id, wallet_address, created_at))
    conn.commit()
    conn.close()
    return order_id

def get_order_by_id(order_id):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def update_order_status(order_id, status):
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, isolation_level=None)
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()

def get_withdraw_commission(currency):
    commissions = {
        "BTC": 0.00002625,
        "LTC": 0.0015,
        "XMR": 0.0032,
        "USDT": 2.5
    }
    return commissions.get(currency, 0)

def format_crypto_amount(amount, currency):
    if currency == "BTC":
        return f"{amount:.8f}".rstrip('0').rstrip('.')
    elif currency in ["LTC", "XMR"]:
        return f"{amount:.8f}".rstrip('0').rstrip('.')
    elif currency == "USDT":
        return f"{int(amount)}" if amount.is_integer() else f"{amount:.2f}".rstrip('0').rstrip('.')
    return str(amount)

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if is_user_verified(user_id):
        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
        return
    
    await state.set_state(CaptchaStates.waiting_for_captcha)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌙", callback_data="emoji_moon"),
            InlineKeyboardButton(text="🍰", callback_data="emoji_cake"),
            InlineKeyboardButton(text="🌹", callback_data="emoji_rose")
        ],
        [
            InlineKeyboardButton(text="🌍", callback_data="emoji_globe"),
            InlineKeyboardButton(text="🎁", callback_data="emoji_gift"),
            InlineKeyboardButton(text="☀️", callback_data="emoji_sun")
        ]
    ])
    
    text = (
        "Сработала антиспам система!\n"
        "❗ ВЫБЕРИТЕ роза, ЧТОБЫ ПРОДОЛЖИТЬ ❗\n"
        "<code>Бот не будет реагировать на сообщения до корректного ввода</code>"
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@dp.callback_query(lambda c: c.data.startswith("admin_"))
async def process_admin_order(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return
    
    if callback.data.startswith("admin_approve_"):
        order_id = callback.data.replace("admin_approve_", "")
        update_order_status(order_id, "approved")
        order = get_order_by_id(order_id)
        if order:
            user_id_order = order[2]
            await bot.send_message(user_id_order, f"✅ Ваша заявка №{order_id} подтверждена. Средства поступят на ваш кошелек.")
        await callback.answer("Заявка подтверждена", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ Подтверждена", reply_markup=None)
    elif callback.data.startswith("admin_reject_"):
        order_id = callback.data.replace("admin_reject_", "")
        update_order_status(order_id, "rejected")
        order = get_order_by_id(order_id)
        if order:
            user_id_order = order[2]
            await bot.send_message(user_id_order, f"❌ Ваша заявка №{order_id} отклонена.")
        await callback.answer("Заявка отклонена", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ Отклонена", reply_markup=None)

@dp.callback_query(lambda c: c.data.startswith("emoji_"))
async def process_captcha(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if callback.data == "emoji_rose":
        add_verified_user(user_id)
        await state.clear()
        await callback.answer("Проверка пройдена! Теперь вы можете использовать бота.")
        await callback.message.delete()
        await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
    else:
        await callback.answer("❌ Неверный эмодзи", show_alert=False)

@dp.callback_query(lambda c: c.data in ["payment_paid", "payment_cancel"])
async def process_payment_confirmation(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if callback.data == "payment_paid":
        data = await state.get_data()
        method_id = data.get("payment_method_id")
        currency = data.get("exchange_currency", "")
        amount_rub = data.get("exchange_amount", 0)
        crypto_amount = data.get("exchange_crypto_amount", 0)
        wallet_address = data.get("wallet_address", "")
        from_buy = data.get("from_buy", False)
        
        if not method_id or not currency:
            await callback.answer("Действие недоступно", show_alert=True)
            return
        
        if method_id:
            method = get_payment_method_by_id(method_id)
            method_price = method[3] if method else 0
            total_amount_rub = amount_rub + method_price
            total_str = format_crypto_amount(total, currency)
            order_id = create_order(user_id, currency, total_amount_rub, crypto_amount, method_id, wallet_address)
            
            text = (
                f"🗳 Заявка: №{order_id}\n\n"
                f"⏳ Статус: обрабатывается...\n"
                f"💵 Сумма внесения: {int(total_str)} RUB\n\n"
                f"🔺 Пожалуйста, отправьте чек или скриншот оплаты — это поможет быстрее найти ваш платёж.\n\n"
                f"❗️ Если этого не сделать - заявка может быть отменена, время обработки может значительно увеличится. Спасибо за понимание!\n\n"
                f"🔺 Если у Вас возникли какие-либо сложности с оплатой, то напишите нашему саппорту: {os.getenv('SELL_USERNAME', '@S_btcltcbot')}"
            )
            
            await state.update_data(order_id=order_id)
            await state.set_state(CaptchaStates.waiting_for_receipt)
            
            await callback.message.edit_text(text, reply_markup=get_receipt_keyboard(), parse_mode="HTML")
            await callback.answer()
            
            admin_ids = os.getenv("ADMIN_ID", "").split(",")
            for admin_id_str in admin_ids:
                if admin_id_str.strip().isdigit():
                    admin_id = int(admin_id_str.strip())
                    admin_text = (
                        f"🆕 Новая заявка\n\n"
                        f"🗳 Заявка: №{order_id}\n"
                        f"👤 Пользователь: {user_id}\n"
                        f"💵 Сумма: {int(total_amount_rub)} RUB\n"
                        f"💰 К получению: {crypto_amount:.8f} {currency}\n"
                        f"⏳ Статус: обрабатывается..."
                    )
                    try:
                        await bot.send_message(admin_id, admin_text, reply_markup=get_admin_order_keyboard(order_id))
                    except Exception as e:
                        print(f'Exception caught: {e}')
        else:
            await state.clear()
            await callback.answer("Ошибка создания заявки", show_alert=True)
            if from_buy:
                await callback.message.answer("Ошибка создания заявки", reply_markup=get_main_menu_keyboard())
            else:
                await callback.message.answer("Ошибка создания заявки", reply_markup=get_wallet_keyboard())
    
    elif callback.data == "payment_cancel":
        data = await state.get_data()
        from_buy = data.get("from_buy", False)
        await state.clear()
        await callback.answer("Заявка отменена")
        await callback.message.edit_text("⛔️ Заявка отменена", reply_markup=None)
        if from_buy:
            await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
        else:
            await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())

@dp.callback_query(lambda c: c.data.startswith("payment_method_"))
async def process_payment_method_selection(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    current_state = await state.get_state()
    
    if current_state != CaptchaStates.waiting_for_exchange_payment:
        await callback.answer("Действие недоступно", show_alert=True)
        return
    
    method_id = int(callback.data.replace("payment_method_", ""))
    requisites = get_exchange_requisites(method_id)
    
    if requisites:
        data = await state.get_data()
        currency = data.get("exchange_currency", "")
        
        await state.update_data(payment_method_id=method_id)
        await state.set_state(CaptchaStates.waiting_for_wallet_address)
        
        await callback.answer()
        await callback.message.answer(f"Введите свой {currency} адрес:", reply_markup=get_exchange_payment_cancel_keyboard())
    else:
        data = await state.get_data()
        from_buy = data.get("from_buy", False)
        if is_admin(user_id):
            await callback.answer("Настройте реквизиты перед тем как создать заявку", show_alert=True)
            if from_buy:
                await callback.message.answer("Настройте реквизиты перед тем как создать заявку", reply_markup=get_main_menu_keyboard())
            else:
                await callback.message.answer("Настройте реквизиты перед тем как создать заявку", reply_markup=get_wallet_keyboard())
        else:
            await callback.answer("Функция временно недоступна", show_alert=True)
            if from_buy:
                await callback.message.answer("Функция временно недоступна", reply_markup=get_main_menu_keyboard())
            else:
                await callback.message.answer("Функция временно недоступна", reply_markup=get_wallet_keyboard())

@dp.callback_query(lambda c: c.data in ["receipt_send", "receipt_no"])
async def process_receipt(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state != CaptchaStates.waiting_for_receipt:
        await callback.answer("Действие недоступно", show_alert=True)
        return
    
    data = await state.get_data()
    from_buy = data.get("from_buy", False)
    
    if callback.data == "receipt_send":
        await callback.answer()
        await callback.message.answer("📎 Отправьте фото или скриншот чека об оплате:")
    elif callback.data == "receipt_no":
        await state.clear()
        await callback.answer("Заявка принята")
        await callback.message.answer("✅ Заявка принята. Ожидайте обработки.")
        if from_buy:
            await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
        else:
            await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())

@dp.callback_query(lambda c: c.data == "generate_new_address")
async def process_generate_new_address(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    currency = data.get("deposit_currency", "")
    
    if not currency:
        await callback.answer("Выберите валюту для депозита", show_alert=True)
        return
    
    address = get_deposit_address(currency)
    min_amount = get_deposit_min_amount(currency)
    
    if address:
        text = (
            f"<b>Сеть: {currency}</b>\n"
            f"Адрес: <code>{address}</code>\n"
            f"<b>Мин. депозит: {min_amount} {currency}</b>"
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_deposit_info_keyboard(), parse_mode="HTML")
            await callback.answer("Новый адрес сгенерирован")
        except Exception:
            await callback.answer()
    else:
        await callback.answer("Адрес не настроен", show_alert=True)

@dp.callback_query(lambda c: c.data in ["withdraw_confirm", "withdraw_cancel"])
async def process_withdraw_confirmation(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state != CaptchaStates.waiting_for_withdraw_confirm:
        await callback.answer("Действие недоступно", show_alert=True)
        return
    
    if callback.data == "withdraw_confirm":
        await state.clear()
        await callback.answer("Транзакция подтверждена")
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ Транзакция подтверждена",
            reply_markup=None
        )
        await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
    elif callback.data == "withdraw_cancel":
        await state.clear()
        await callback.answer("Транзакция отменена")
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ Транзакция отменена",
            reply_markup=None
        )
        await callback.message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())

@dp.message()
async def handle_messages(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if not is_user_verified(user_id):
        current_state = await state.get_state()
        if current_state == CaptchaStates.waiting_for_captcha:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🌙", callback_data="emoji_moon"),
                    InlineKeyboardButton(text="🍰", callback_data="emoji_cake"),
                    InlineKeyboardButton(text="🌹", callback_data="emoji_rose")
                ],
                [
                    InlineKeyboardButton(text="🌍", callback_data="emoji_globe"),
                    InlineKeyboardButton(text="🎁", callback_data="emoji_gift"),
                    InlineKeyboardButton(text="☀️", callback_data="emoji_sun")
                ]
            ])
            
            text = (
                "Сработала антиспам система!\n"
                "❗ ВЫБЕРИТЕ роза, ЧТОБЫ ПРОДОЛЖИТЬ ❗\n"
                "<code>Бот не будет реагировать на сообщения до корректного ввода</code>"
            )
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        if message.text == "💻 Личный кабинет":
            bot_info = await bot.get_me()
            bot_username = bot_info.username
            referral_link = f"https://telegram.me/{bot_username}?start={user_id}"
            
            text = (
                f"Ваш уникальный ID: <code>{user_id}</code>\n"
                f"Количество обменов: 0\n"
                f"Количество рефералов: 0\n"
                f"Реферальный счет: 0 RUB\n\n"
                f"<code>Приводи активных рефералов и зарабатывай!</code>\n\n"
                f"Твоя реферальная ссылка:\n{referral_link}"
            )
            
            await message.answer(text, reply_markup=get_cabinet_keyboard(), parse_mode="HTML")
        elif message.text == "🔐 Кошелек":
            text = (
                "🔐 Это твой персональный крипто – кошелек.\n\n"
                "🔺 принимай и отправляй переводы\n"
                "🔺 храни криптовалюту\n"
                "🔺 создавай уникальные адреса\n\n"
                "Анонимно и безопасно.\n\n"
                "⚠️ За отправку с кошелька взимаются следующие комиссии:\n\n"
                "BTC - 0.00002625\n"
                "LTC - 0.0015\n"
                "XMR - 0.0032\n"
                "USDT - 2.5"
            )
            await message.answer(text, reply_markup=get_wallet_keyboard())
        elif message.text == "📈 Купить":
            await message.answer("Выберите валюту", reply_markup=get_buy_currency_keyboard())
        elif message.text == "📉 Продать":
            sell_username = os.getenv("SELL_USERNAME", "@S_btcltcbot")
            await message.answer(f"Заявки на продажу принимаются в ручном режиме {sell_username}", reply_markup=get_main_menu_keyboard())
        elif message.text in ["🔄 Купить BTC", "🔄 Купить LTC", "🔄 Купить XMR", "🔄 Купить USDT-TRC20"]:
            currency_map = {
                "🔄 Купить BTC": "BTC",
                "🔄 Купить LTC": "LTC",
                "🔄 Купить XMR": "XMR",
                "🔄 Купить USDT-TRC20": "USDT"
            }
            currency = currency_map.get(message.text)
            if currency:
                await state.update_data(exchange_currency=currency, from_buy=True)
                await state.set_state(CaptchaStates.waiting_for_exchange_amount)
                await message.answer(f"💰 Введи нужную сумму в {currency} или в RUB:\nНапример: 0.00041 или 1000", reply_markup=get_promo_cancel_keyboard())
        elif message.text == "⬅️ Назад":
            current_state = await state.get_state()
            if current_state is None:
                await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
            else:
                await state.clear()
                await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
        elif message.text == "⬆️ Вывод":
            await state.set_state(CaptchaStates.waiting_for_withdraw_currency)
            await message.answer("Выберите валюту:", reply_markup=get_calculator_currency_keyboard())
        elif message.text == "⬇️ Пополнить":
            await message.answer("Выберите способ пополнения кошелька:", reply_markup=get_deposit_method_keyboard())
        elif message.text == "⬇️ Депозит":
            await state.set_state(CaptchaStates.waiting_for_deposit_currency)
            await message.answer("Выберите валюту:", reply_markup=get_calculator_currency_keyboard())
        elif message.text == "📩 Пополнить через обменник":
            await state.set_state(CaptchaStates.waiting_for_exchange_currency)
            await message.answer("Выберите валюту", reply_markup=get_exchange_currency_keyboard())
        elif is_admin(user_id) and message.text == "⚙️ Управление методами оплаты":
            methods = get_all_payment_methods("ALL")
            await state.update_data(admin_methods_currency="ALL")
            await state.set_state(CaptchaStates.admin_manage_methods_action)
            if methods:
                text = "Методы оплаты (общие для всех валют):\n\n"
                for method_id, method_name, price_rub, is_active in methods:
                    status = "✅ Активен" if is_active else "❌ Неактивен"
                    text += f"{status} - {method_name}\n"
                await message.answer(text, reply_markup=get_admin_manage_methods_keyboard("ALL", methods))
            else:
                text = "Пока нет методов оплаты.\n\nДобавьте первый метод оплаты:"
                await message.answer(text, reply_markup=get_admin_manage_methods_keyboard("ALL", []))
        elif is_admin(user_id) and message.text == "💳 Управление адресами депозитов":
            await state.set_state(CaptchaStates.admin_deposit_address)
            await message.answer("Выберите валюту для управления адресом депозита:", reply_markup=get_calculator_currency_keyboard())
        elif is_admin(user_id) and message.text == "🔗 Ссылки":
            await state.set_state(CaptchaStates.admin_links)
            rates = os.getenv("BTC_RATE_RUB", "9000000")
            sell_btc = os.getenv("SELL_USERNAME", "")
            news_channel = os.getenv("CONTACT_NEWS", "")
            operator = os.getenv("CONTACT_SUPPORT", "")
            operator2 = os.getenv("CONTACT_BOSS", "")
            operator3 = os.getenv("CONTACT_REVIEWS", "")
            work_operator = os.getenv("WORK_OPERATOR", "")
            text = (
                "🔗 Редактирование ссылок\n\n"
                f"📊 rates (BTC_RATE_RUB): <code>{rates}</code>\n"
                f"💰 sell_btc (SELL_USERNAME): <code>{sell_btc}</code>\n"
                f"📢 news_channel (CONTACT_NEWS): <code>{news_channel}</code>\n"
                f"👨‍💻 operator (CONTACT_SUPPORT): <code>{operator}</code>\n"
                f"👨‍💻 operator2 (CONTACT_BOSS): <code>{operator2}</code>\n"
                f"📣 operator3 (CONTACT_REVIEWS): <code>{operator3}</code>\n"
                f"🏧 work_operator (WORK_OPERATOR): <code>{work_operator}</code>"
            )
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📊 rates")],
                    [KeyboardButton(text="💰 sell_btc")],
                    [KeyboardButton(text="📢 news_channel")],
                    [KeyboardButton(text="👨‍💻 operator")],
                    [KeyboardButton(text="👨‍💻 operator2")],
                    [KeyboardButton(text="📣 operator3")],
                    [KeyboardButton(text="🏧 work_operator")],
                    [KeyboardButton(text="❌ Отмена")]
                ],
                resize_keyboard=True
            )
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        elif message.text == "👨‍💻 Контакты":
            await message.answer("⬇️ Наши контакты", reply_markup=get_contacts_keyboard())
        elif message.text == "🏷️ Промокод":
            await state.set_state(CaptchaStates.waiting_for_promo)
            await message.answer("Введите промокод ниже:", reply_markup=get_promo_cancel_keyboard())
        elif message.text == "Вывести реф. счет":
            text = (
                "⛔️ Минимальная сумма вывода 1000 RUB\n\n"
                "💳 Ваш счет: 0 RUB"
            )
            await message.answer(text, reply_markup=get_cabinet_keyboard())
        elif message.text == "🎰 Испытай удачу":
            user_id = message.from_user.id
            current_time = datetime.now()
            
            last_used = get_luck_last_used(user_id)
            if last_used:
                time_diff = current_time - last_used
                
                if time_diff < timedelta(days=1):
                    await message.answer("⛔⏰ С момента последнего вращения не прошли сутки, попробуйте позже", reply_markup=get_cabinet_keyboard())
                    return
            
            set_luck_last_used(user_id, current_time)
            await bot.send_dice(message.chat.id, emoji='🎰')
            await message.answer("Вы испытали удачу 🤑! Теперь ваша скидка составляет 1 RUB", reply_markup=get_cabinet_keyboard())
        elif message.text == "💰 Баланс":
            text = (
                "BTC: <code>0</code> ~ 0 RUB\n"
                "LTC: <code>0</code> ~ 0 RUB\n"
                "XMR: <code>0</code> ~ 0 RUB\n"
                "USDT: <code>0</code> ~ 0 RUB"
            )
            await message.answer(text, reply_markup=get_wallet_keyboard(), parse_mode="HTML")
        elif message.text == "📜 История":
            await state.set_state(CaptchaStates.waiting_for_history_currency)
            await message.answer("Выберите валюту:", reply_markup=get_calculator_currency_keyboard())
        elif message.text == "🧮 Калькулятор":
            await state.set_state(CaptchaStates.waiting_for_calculator_currency)
            await message.answer("Выберите валюту", reply_markup=get_calculator_currency_keyboard())
        elif message.text == "❌ Отмена":
            current_state = await state.get_state()
            await state.clear()
            if current_state in [CaptchaStates.waiting_for_promo, CaptchaStates.waiting_for_calculator_currency, CaptchaStates.waiting_for_calculator_value, CaptchaStates.waiting_for_history_currency, CaptchaStates.waiting_for_history_category, CaptchaStates.waiting_for_withdraw_currency, CaptchaStates.waiting_for_withdraw_address, CaptchaStates.waiting_for_withdraw_amount, CaptchaStates.waiting_for_withdraw_confirm]:
                if current_state in [CaptchaStates.waiting_for_history_currency, CaptchaStates.waiting_for_history_category, CaptchaStates.waiting_for_withdraw_currency, CaptchaStates.waiting_for_withdraw_address, CaptchaStates.waiting_for_withdraw_amount, CaptchaStates.waiting_for_withdraw_confirm]:
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_cabinet_keyboard())
            else:
                await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
        elif message.text == "⬅️ Назад":
            current_state = await state.get_state()
            await state.clear()
            if current_state == CaptchaStates.waiting_for_deposit_currency:
                await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
            else:
                await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
        else:
            current_state = await state.get_state()
            if current_state == CaptchaStates.waiting_for_promo:
                await message.answer("⛔ Некорректный промокод, попробуйте еще раз", reply_markup=get_promo_cancel_keyboard())
            elif current_state == CaptchaStates.waiting_for_calculator_currency:
                if message.text in ["BTC", "LTC", "XMR", "USDT"]:
                    await state.update_data(calculator_currency=message.text)
                    await state.set_state(CaptchaStates.waiting_for_calculator_value)
                    await message.answer(f"Введите значение для {message.text} в РУБЛЯХ", reply_markup=get_promo_cancel_keyboard())
                else:
                    await message.answer("Выберите валюту", reply_markup=get_calculator_currency_keyboard())
            elif current_state == CaptchaStates.waiting_for_calculator_value:
                if message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_cabinet_keyboard())
                else:
                    data = await state.get_data()
                    currency = data.get("calculator_currency", "")
                    try:
                        value = float(message.text.replace(",", "."))
                        rates = await get_crypto_rates()
                        rate = rates.get(currency, 9000000)
                        
                        crypto_amount = value / rate
                        
                        if currency == 'BTC':
                            crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                        elif currency == 'LTC':
                            crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                        else:
                            crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                        
                        text = (
                            f"<code>{int(value) if value.is_integer() else value}</code> рублей\n"
                            f"это по курсу <code>{crypto_display}</code> {currency}"
                        )
                        
                        await state.clear()
                        await message.answer(text, reply_markup=get_cabinet_keyboard(), parse_mode="HTML")
                    except ValueError:
                        await message.answer(f"Введите корректное числовое значение для {currency} в РУБЛЯХ", reply_markup=get_promo_cancel_keyboard())
            elif current_state == CaptchaStates.waiting_for_history_currency:
                if message.text in ["BTC", "LTC", "XMR", "USDT"]:
                    await state.update_data(history_currency=message.text)
                    await state.set_state(CaptchaStates.waiting_for_history_category)
                    await message.answer("Выберите категорию:", reply_markup=get_history_category_keyboard())
                else:
                    await message.answer("Выберите валюту:", reply_markup=get_calculator_currency_keyboard())
            elif current_state == CaptchaStates.waiting_for_history_category:
                if message.text in ["Вывод", "Депозит"]:
                    await state.clear()
                    await message.answer("Транзакции отсутствуют", reply_markup=get_wallet_keyboard())
                else:
                    await message.answer("Выберите категорию:", reply_markup=get_history_category_keyboard())
            elif current_state == CaptchaStates.waiting_for_withdraw_currency:
                if message.text in ["BTC", "LTC", "XMR", "USDT"]:
                    await state.update_data(withdraw_currency=message.text)
                    await state.set_state(CaptchaStates.waiting_for_withdraw_address)
                    await message.answer("Введите адрес получателя:", reply_markup=get_promo_cancel_keyboard())
                else:
                    await message.answer("Выберите валюту:", reply_markup=get_calculator_currency_keyboard())
            elif current_state == CaptchaStates.waiting_for_withdraw_address:
                if message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    await state.update_data(withdraw_address=message.text)
                    data = await state.get_data()
                    currency = data.get("withdraw_currency", "")
                    await state.set_state(CaptchaStates.waiting_for_withdraw_amount)
                    await message.answer(f"Введите сумму вывода в {currency}:", reply_markup=get_withdraw_all_keyboard())
            elif current_state == CaptchaStates.waiting_for_withdraw_amount:
                if message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                elif message.text == "Вывести все":
                    data = await state.get_data()
                    currency = data.get("withdraw_currency", "")
                    user_balance = get_user_balance(user_id, currency)
                    
                    if user_balance <= 0:
                        await message.answer("⛔️ Недостаточно средств", reply_markup=get_withdraw_all_keyboard())
                        return
                    
                    commission = get_withdraw_commission(currency)
                    amount = user_balance - commission
                    min_withdraw = get_withdraw_min_amount(currency)
                    
                    if amount < min_withdraw:
                        min_str = format_crypto_amount(min_withdraw, currency)
                        await message.answer(f"⛔️ Минимальная сумма вывода: {min_str} {currency}\n\nНедостаточно средств для вывода с учетом комиссии.", reply_markup=get_withdraw_all_keyboard())
                        return
                    
                    total = amount + commission
                    address = data.get("withdraw_address", "")
                    
                    amount_str = format_crypto_amount(amount, currency)
                    total_str = format_crypto_amount(total, currency)
                    
                    text = (
                        f"🔺Внимание🔺\n\n"
                        f"Сумма вывода: <code>{amount_str}</code> <b>{currency}</b>\n"
                        f"Сумма вывода с комиссией: <code>{total_str}</code> <b>{currency}</b>\n"
                        f"Адрес получателя:\n<code>{address}</code>"
                    )
                    await state.update_data(withdraw_amount=amount)
                    await state.set_state(CaptchaStates.waiting_for_withdraw_confirm)
                    await message.answer(text, reply_markup=get_withdraw_confirm_keyboard(), parse_mode="HTML")
                else:
                    try:
                        amount = float(message.text.replace(",", "."))
                        data = await state.get_data()
                        currency = data.get("withdraw_currency", "")
                        
                        min_withdraw = get_withdraw_min_amount(currency)
                        if amount < min_withdraw:
                            min_str = format_crypto_amount(min_withdraw, currency)
                            await message.answer(f"⛔️ Минимальная сумма вывода: {min_str} {currency}", reply_markup=get_withdraw_all_keyboard())
                            return
                        
                        user_balance = get_user_balance(user_id, currency)
                        commission = get_withdraw_commission(currency)
                        total = amount + commission
                        
                        if user_balance < total:
                            await message.answer("⛔️ Недостаточно средств", reply_markup=get_withdraw_all_keyboard())
                            return
                        
                        address = data.get("withdraw_address", "")
                        
                        amount_str = format_crypto_amount(amount, currency)
                        total_str = format_crypto_amount(total, currency)
                        
                        text = (
                            f"🔺Внимание🔺\n\n"
                            f"Сумма вывода: <code>{amount_str}</code> <b>{currency}</b>\n"
                            f"Сумма вывода с комиссией: <code>{total_str}</code> <b>{currency}</b>\n"
                            f"Адрес получателя:\n<code>{address}</code>"
                        )
                        await state.update_data(withdraw_amount=amount)
                        await state.set_state(CaptchaStates.waiting_for_withdraw_confirm)
                        await message.answer(text, reply_markup=get_withdraw_confirm_keyboard(), parse_mode="HTML")
                    except ValueError:
                        data = await state.get_data()
                        currency = data.get("withdraw_currency", "")
                        await message.answer(f"Введите корректное числовое значение для {currency}", reply_markup=get_withdraw_all_keyboard())
            elif current_state == CaptchaStates.waiting_for_withdraw_confirm:
                await message.answer("Используйте кнопки под сообщением для подтверждения или отмены транзакции.")
            elif current_state == CaptchaStates.waiting_for_deposit_currency:
                if message.text in ["BTC", "LTC", "XMR", "USDT"]:
                    address = get_deposit_address(message.text)
                    min_amount = get_deposit_min_amount(message.text)
                    
                    if address:
                        text = (
                            f"<b>Сеть: {message.text}</b>\n"
                            f"Адрес: <code>{address}</code>\n"
                            f"<b>Мин. депозит: {min_amount} {message.text}</b>"
                        )
                        await state.update_data(deposit_currency=message.text)
                        await message.answer(text, reply_markup=get_deposit_info_keyboard(), parse_mode="HTML")
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                    else:
                        if is_admin(user_id):
                            await message.answer(f"Адрес для {message.text} не настроен. Обратитесь к администратору.", reply_markup=get_wallet_keyboard())
                        else:
                            await message.answer("Функция временно недоступна", reply_markup=get_wallet_keyboard())
                elif message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    await message.answer("Выберите валюту:", reply_markup=get_calculator_currency_keyboard())
            elif current_state == CaptchaStates.waiting_for_exchange_currency:
                currency_map = {
                    "🔄 Купить BTC": "BTC",
                    "🔄 Купить LTC": "LTC",
                    "🔄 Купить XMR": "XMR",
                    "🔄 Купить USDT-TRC20": "USDT"
                }
                currency = currency_map.get(message.text)
                if currency:
                    await state.update_data(exchange_currency=currency)
                    await state.set_state(CaptchaStates.waiting_for_exchange_amount)
                    await message.answer(f"💰 Введи нужную сумму в {currency} или в RUB:\nНапример: 0.00041 или 1000", reply_markup=get_promo_cancel_keyboard())
                elif message.text == "⬅️ Назад":
                    await state.clear()
                    await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    await message.answer("Выберите валюту", reply_markup=get_exchange_currency_keyboard())
            elif current_state == CaptchaStates.waiting_for_exchange_amount:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    from_buy = data.get("from_buy", False)
                    await state.clear()
                    if from_buy:
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
                    else:
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    try:
                        input_value = float(message.text.replace(",", "."))
                        data = await state.get_data()
                        currency = data.get("exchange_currency", "")
                        rates = await get_crypto_rates()
                        rate = rates.get(currency, 9000000)

                        if input_value < 1000:
                            crypto_amount = input_value
                            rub_amount = crypto_amount * rate
                            commission_multiplier = 1.0811
                            rub_amount_with_commission = rub_amount * commission_multiplier
                        else:
                            rub_amount = input_value
                            crypto_amount = rub_amount / rate
                            if rub_amount >= 1000:
                                if rub_amount <= 5000:
                                    commission_multiplier = 1.512 - math.log10(rub_amount / 1000) * 0.2187
                                else:
                                    commission_multiplier = 1.512 - math.log10(rub_amount / 1000) * 0.1736
                            else:
                                commission_multiplier = 1.512
                            rub_amount_with_commission = rub_amount * commission_multiplier
                            if rub_amount_with_commission < 1500:
                                await message.answer("⛔️ Минимальная сумма пополнения: 1500 рублей", reply_markup=get_promo_cancel_keyboard())
                                return
                        
                        discount = 250
                        amount_to_pay = int(rub_amount_with_commission - discount)
                        
                        if currency == 'BTC':
                            crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                        elif currency == 'LTC':
                            crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                        else:
                            crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                        
                        text = (
                            f"Получите: <code>{crypto_display}</code> <b>{currency}</b>\n"
                            f"Скидка: {discount} ₽\n"
                            f"К оплате: {amount_to_pay} ₽\n\n"
                            f"Выберите способ оплаты ⬇️"
                        )
                        
                        methods = get_exchange_payment_methods(currency)
                        if methods:
                            await state.update_data(exchange_amount=amount_to_pay, exchange_crypto_amount=crypto_amount)
                            await state.set_state(CaptchaStates.waiting_for_exchange_payment)
                            await message.answer(text, reply_markup=get_exchange_payment_keyboard(methods, amount_to_pay), parse_mode="HTML")
                            
                            deals_left = 6
                            progress = "🟢" + "⚪" * (deals_left - 1)
                            await message.answer(f"Сделок до бонусного обмена: {deals_left}\n{progress}")
                        else:
                            data = await state.get_data()
                            from_buy = data.get("from_buy", False)
                            if is_admin(user_id):
                                if from_buy:
                                    await message.answer("Настройте реквизиты перед тем как создать заявку", reply_markup=get_main_menu_keyboard())
                                else:
                                    await message.answer("Настройте реквизиты перед тем как создать заявку", reply_markup=get_wallet_keyboard())
                            else:
                                if from_buy:
                                    await message.answer("Функция временно недоступна", reply_markup=get_main_menu_keyboard())
                                else:
                                    await message.answer("Функция временно недоступна", reply_markup=get_wallet_keyboard())
                    except ValueError:
                        data = await state.get_data()
                        currency = data.get("exchange_currency", "")
                        await message.answer(f"💰 Введи нужную сумму в {currency} или в RUB:\nНапример: 0.00041 или 1000", reply_markup=get_promo_cancel_keyboard())
            elif current_state == CaptchaStates.waiting_for_exchange_payment:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    from_buy = data.get("from_buy", False)
                    await state.clear()
                    if from_buy:
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
                    else:
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    await message.answer("Используйте кнопки под сообщением для выбора способа оплаты.")
            elif current_state == CaptchaStates.waiting_for_wallet_address:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    from_buy = data.get("from_buy", False)
                    await state.clear()
                    if from_buy:
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())
                    else:
                        await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_wallet_keyboard())
                else:
                    wallet_address = message.text.strip()
                    data = await state.get_data()
                    currency = data.get("exchange_currency", "")
                    amount = data.get("exchange_amount", 0)
                    crypto_amount = data.get("exchange_crypto_amount", 0)
                    method_id = data.get("payment_method_id")
                    from_buy = data.get("from_buy", False)
                    
                    loading_msg = await message.answer("⌛ Идет подбор реквизитов")
                    await asyncio.sleep(6)
                    
                    requisites = get_exchange_requisites(method_id)
                    
                    if requisites:
                        method = get_payment_method_by_id(method_id)
                        method_price = method[3] if method else 0
                        total_amount = amount + method_price
                        
                        bank_name = ""
                        requisites_list = []
                        for req_type, req_value in requisites:
                            if req_type.lower() in ["банк", "bank"]:
                                bank_name = req_value
                            else:
                                requisites_list.append(req_value)
                        
                        if not bank_name and method:
                            bank_name = method[2]
                        
                        requisites_value = ", ".join(requisites_list) if requisites_list else ""
                        
                        if currency == 'BTC':
                            crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                        elif currency == 'LTC':
                            crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                        else:
                            crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                        
                        text_parts = []
                        text_parts.append(f"Банк получателя: <b>{bank_name}</b>")
                        text_parts.append(f"Реквизиты: <b>{requisites_value}</b>")
                        text_parts.append(f"Сумма к оплате: <b>{int(total_amount)} RUB</b>")
                        text_parts.append(f"К получению: <b>{crypto_display} {currency}</b>")
                        text_parts.append(f"На кошелек: <b>{wallet_address}</b>")
                        text_parts.append("")
                        text_parts.append("🔺 Внимание: Переводить точную сумму!")
                        text_parts.append("🔺 После оплаты нажмите")
                        text_parts.append("\"✅ Я оплатил\"")
                        text_parts.append("")
                        text_parts.append("⏱️ На оплату даётся 15 мин!")
                        
                        text = "\n".join(text_parts)
                        
                        await state.update_data(wallet_address=wallet_address, exchange_amount=total_amount)
                        await state.set_state(CaptchaStates.waiting_for_payment_confirmation)
                        
                        try:
                            await loading_msg.delete()
                        except Exception as e:
                            print(f'Exception caught: {e}')
                        
                        await message.answer(text, reply_markup=get_payment_confirmation_keyboard(), parse_mode="HTML")
                    else:
                        try:
                            await loading_msg.delete()
                        except Exception as e:
                            print(f'Exception caught: {e}')
                        await state.clear()
                        if from_buy:
                            await message.answer("Ошибка получения реквизитов", reply_markup=get_main_menu_keyboard())
                        else:
                            await message.answer("Ошибка получения реквизитов", reply_markup=get_wallet_keyboard())
            elif current_state == CaptchaStates.waiting_for_payment_confirmation:
                await message.answer("Используйте кнопки под сообщением для подтверждения оплаты или отмены заявки.")
            elif current_state == CaptchaStates.admin_deposit_address:
                if message.text in ["BTC", "LTC", "XMR", "USDT"]:
                    current_address = get_deposit_address(message.text)
                    if current_address:
                        await message.answer(f"Текущий адрес для {message.text}:\n<code>{current_address}</code>\n\nВведите новый адрес или отправьте тот же для сохранения:", reply_markup=get_promo_cancel_keyboard(), parse_mode="HTML")
                    else:
                        await message.answer(f"Адрес для {message.text} не настроен.\nВведите адрес:", reply_markup=get_promo_cancel_keyboard())
                    await state.update_data(admin_deposit_currency=message.text)
                elif message.text == "❌ Отмена":
                    await state.clear()
                    keyboard = ReplyKeyboardMarkup(
                        keyboard=[
                            [
                                KeyboardButton(text="⚙️ Управление методами оплаты")
                            ],
                            [
                                KeyboardButton(text="💳 Управление адресами депозитов")
                            ],
                            [
                                KeyboardButton(text="⬅️ Назад")
                            ]
                        ],
                        resize_keyboard=True
                    )
                    await message.answer("Админ-панель", reply_markup=keyboard)
                else:
                    data = await state.get_data()
                    currency = data.get("admin_deposit_currency", "")
                    if currency:
                        if message.text:
                            set_deposit_address(currency, message.text)
                            await state.clear()
                            await message.answer(f"✅ Адрес для {currency} успешно сохранен:\n<code>{message.text}</code>", reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")
                        else:
                            await message.answer("Введите адрес:", reply_markup=get_promo_cancel_keyboard())
                    else:
                        await message.answer("Выберите валюту для управления адресом:", reply_markup=get_calculator_currency_keyboard())
            elif current_state == CaptchaStates.admin_manage_methods_action:
                if message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
                elif message.text == "➕ Добавить метод оплаты":
                    await state.set_state(CaptchaStates.admin_add_method_name)
                    await message.answer("Введите название метода оплаты (например: СБП, Карта, ЮMoney):", reply_markup=get_promo_cancel_keyboard())
                elif message.text.startswith("✅ ") or message.text.startswith("❌ "):
                    data = await state.get_data()
                    currency = data.get("admin_methods_currency", "")
                    methods = get_all_payment_methods(currency)
                    method_id = None
                    for mid, mname, price, is_active in methods:
                        status = "✅" if is_active else "❌"
                        if message.text == f"{status} {mname}":
                            method_id = mid
                            break
                    
                    if method_id:
                        await state.update_data(admin_selected_method_id=method_id)
                        await state.set_state(CaptchaStates.admin_edit_method)
                        method = get_payment_method_by_id(method_id)
                        if method:
                            method_name = method[2]
                            method[3]
                            is_active = method[4]
                            status_text = "активен" if is_active else "неактивен"
                            text = (
                                f"Метод оплаты: {method_name}\n"
                                f"Статус: {status_text}\n\n"
                                f"Выберите действие:"
                            )
                            await message.answer(text, reply_markup=get_admin_method_actions_keyboard())
                        else:
                            await message.answer("Метод не найден", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                    else:
                        await message.answer("Выберите метод из списка", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                else:
                    data = await state.get_data()
                    currency = data.get("admin_methods_currency", "")
                    methods = get_all_payment_methods(currency)
                    await message.answer("Выберите метод оплаты или добавьте новый:", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
            elif current_state == CaptchaStates.admin_add_method_name:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    currency = data.get("admin_methods_currency", "")
                    methods = get_all_payment_methods(currency)
                    await state.set_state(CaptchaStates.admin_manage_methods_action)
                    await message.answer("Выберите метод оплаты или добавьте новый:", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                else:
                    data = await state.get_data()
                    currency = data.get("admin_methods_currency", "")
                    method_name = message.text
                    method_id = add_payment_method(currency, method_name, 0)
                    await state.update_data(admin_new_method_id=method_id, admin_new_method_name=method_name)
                    await state.set_state(CaptchaStates.admin_add_method_requisite)
                    await message.answer(f"Введите номер карты или телефона для метода '{method_name}':", reply_markup=get_promo_cancel_keyboard())
            elif current_state == CaptchaStates.admin_add_method_requisite:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    method_id = data.get("admin_edit_requisite_method_id")
                    if method_id:
                        await state.update_data(admin_requisites_method_id=method_id)
                        await state.set_state(CaptchaStates.admin_manage_requisites_method)
                        requisites = get_exchange_requisites_with_id(method_id)
                        if requisites:
                            text = "Реквизиты для метода оплаты:\n\n"
                            for req_id, req_type, req_value in requisites:
                                text += format_requisite_display(req_type, req_value) + "\n"
                            await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                        else:
                            await message.answer("Реквизитов нет. Добавьте первый реквизит:", reply_markup=get_admin_requisites_keyboard([]))
                    else:
                        currency = data.get("admin_methods_currency", "")
                        methods = get_all_payment_methods(currency)
                        await state.set_state(CaptchaStates.admin_manage_methods_action)
                        await message.answer("Выберите метод оплаты или добавьте новый:", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                else:
                    data = await state.get_data()
                    method_id = data.get("admin_new_method_id") or data.get("admin_edit_requisite_method_id")
                    method_name = data.get("admin_new_method_name", "")
                    if method_id:
                        add_requisite(method_id, "Карта", message.text)
                        if method_name:
                            currency = data.get("admin_methods_currency", "")
                            methods = get_all_payment_methods(currency)
                            await state.set_state(CaptchaStates.admin_manage_methods_action)
                            await message.answer(f"✅ Метод оплаты '{method_name}' с номером '{message.text}' успешно добавлен!", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                        else:
                            await state.update_data(admin_requisites_method_id=method_id)
                            await state.set_state(CaptchaStates.admin_manage_requisites_method)
                            requisites = get_exchange_requisites_with_id(method_id)
                            text = "✅ Реквизит добавлен!\n\nРеквизиты для метода оплаты:\n\n"
                            for req_id, req_type, req_value in requisites:
                                text += format_requisite_display(req_type, req_value) + "\n"
                            await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                    else:
                        await message.answer("Ошибка. Попробуйте снова.", reply_markup=get_admin_panel_keyboard())
                        await state.clear()
            elif current_state == CaptchaStates.admin_edit_method:
                if message.text == "✏️ Редактировать":
                    data = await state.get_data()
                    method_id = data.get("admin_selected_method_id")
                    if method_id:
                        requisites = get_exchange_requisites_with_id(method_id)
                        await state.update_data(admin_requisites_method_id=method_id)
                        await state.set_state(CaptchaStates.admin_manage_requisites_method)
                        if requisites:
                            text = "Реквизиты для метода оплаты:\n\n"
                            for req_id, req_type, req_value in requisites:
                                text += format_requisite_display(req_type, req_value) + "\n"
                            await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                        else:
                            await message.answer("Реквизитов пока нет. Добавьте первый реквизит:", reply_markup=get_admin_requisites_keyboard([]))
                    else:
                        await message.answer("Ошибка", reply_markup=get_admin_method_actions_keyboard())
                elif message.text == "🗑️ Удалить":
                    data = await state.get_data()
                    method_id = data.get("admin_selected_method_id")
                    currency = data.get("admin_methods_currency", "")
                    if method_id:
                        method = get_payment_method_by_id(method_id)
                        if method:
                            delete_payment_method(method_id)
                            methods = get_all_payment_methods(currency)
                            await state.set_state(CaptchaStates.admin_manage_methods_action)
                            await message.answer("✅ Метод оплаты удален!", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                        else:
                            await message.answer("Метод не найден", reply_markup=get_admin_method_actions_keyboard())
                    else:
                        await message.answer("Ошибка", reply_markup=get_admin_method_actions_keyboard())
                elif message.text == "✅ Активировать":
                    data = await state.get_data()
                    method_id = data.get("admin_selected_method_id")
                    currency = data.get("admin_methods_currency", "")
                    if method_id:
                        method = get_payment_method_by_id(method_id)
                        if method:
                            update_payment_method(method_id, method[2], method[3], 1)
                            methods = get_all_payment_methods(currency)
                            await state.set_state(CaptchaStates.admin_manage_methods_action)
                            await message.answer("✅ Метод оплаты активирован!", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                        else:
                            await message.answer("Метод не найден", reply_markup=get_admin_method_actions_keyboard())
                    else:
                        await message.answer("Ошибка", reply_markup=get_admin_method_actions_keyboard())
                elif message.text == "❌ Деактивировать":
                    data = await state.get_data()
                    method_id = data.get("admin_selected_method_id")
                    currency = data.get("admin_methods_currency", "")
                    if method_id:
                        method = get_payment_method_by_id(method_id)
                        if method:
                            update_payment_method(method_id, method[2], method[3], 0)
                            methods = get_all_payment_methods(currency)
                            await state.set_state(CaptchaStates.admin_manage_methods_action)
                            await message.answer("✅ Метод оплаты деактивирован!", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                        else:
                            await message.answer("Метод не найден", reply_markup=get_admin_method_actions_keyboard())
                    else:
                        await message.answer("Ошибка", reply_markup=get_admin_method_actions_keyboard())
                elif message.text == "📝 Управление реквизитами":
                    data = await state.get_data()
                    method_id = data.get("admin_selected_method_id")
                    if method_id:
                        requisites = get_exchange_requisites_with_id(method_id)
                        await state.update_data(admin_requisites_method_id=method_id)
                        await state.set_state(CaptchaStates.admin_manage_requisites_method)
                        if requisites:
                            text = "Реквизиты для метода оплаты:\n\n"
                            for req_id, req_type, req_value in requisites:
                                text += format_requisite_display(req_type, req_value) + "\n"
                            await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                        else:
                            await message.answer("Реквизитов пока нет. Добавьте первый реквизит:", reply_markup=get_admin_requisites_keyboard([]))
                    else:
                        await message.answer("Ошибка", reply_markup=get_admin_method_actions_keyboard())
                elif message.text == "⬅️ Назад":
                    data = await state.get_data()
                    currency = data.get("admin_methods_currency", "")
                    methods = get_all_payment_methods(currency)
                    await state.set_state(CaptchaStates.admin_manage_methods_action)
                    await message.answer("Выберите метод оплаты или добавьте новый:", reply_markup=get_admin_manage_methods_keyboard(currency, methods))
                else:
                    await message.answer("Выберите действие:", reply_markup=get_admin_method_actions_keyboard())
            elif current_state == CaptchaStates.admin_manage_requisites_method:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    method_id = data.get("admin_requisites_method_id")
                    if method_id:
                        await state.update_data(admin_selected_method_id=method_id)
                        await state.set_state(CaptchaStates.admin_edit_method)
                        method = get_payment_method_by_id(method_id)
                        if method:
                            method_name = method[2]
                            method[3]
                            is_active = method[4]
                            status_text = "активен" if is_active else "неактивен"
                            text = (
                                f"Метод оплаты: {method_name}\n"
                                f"Статус: {status_text}\n\n"
                                f"Выберите действие:"
                            )
                            await message.answer(text, reply_markup=get_admin_method_actions_keyboard())
                        else:
                            await state.clear()
                            await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
                    else:
                        await state.clear()
                        await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
                elif message.text == "➕ Добавить реквизит":
                    data = await state.get_data()
                    method_id = data.get("admin_requisites_method_id")
                    if method_id:
                        await state.update_data(admin_edit_requisite_method_id=method_id)
                        await state.set_state(CaptchaStates.admin_add_method_requisite)
                        await message.answer("Введите номер карты или телефона:", reply_markup=get_promo_cancel_keyboard())
                    else:
                        await message.answer("Ошибка", reply_markup=get_admin_requisites_keyboard([]))
                elif message.text.startswith("✏️ "):
                    data = await state.get_data()
                    method_id = data.get("admin_requisites_method_id")
                    if method_id:
                        requisites = get_exchange_requisites_with_id(method_id)
                        for req_id, req_type, req_value in requisites:
                            display_value = req_value[:30] + "..." if len(req_value) > 30 else req_value
                            req_type_clean = req_type.strip()
                            if req_type_clean and re.match(r'^[\d\s\-]+$', req_type_clean):
                                button_text = f"✏️ {display_value}"
                            else:
                                button_text = f"✏️ {req_type}: {display_value}"
                            if message.text == button_text:
                                await state.update_data(admin_edit_requisite_id=req_id, admin_edit_requisite_type=req_type)
                                await state.set_state(CaptchaStates.admin_edit_requisite_value)
                                await message.answer("Введите новый номер карты/телефона:", reply_markup=get_promo_cancel_keyboard())
                                break
                else:
                    data = await state.get_data()
                    currency = data.get("admin_requisites_currency", "")
                    methods = get_exchange_payment_methods(currency)
                    method_id = None
                    for mid, mname, price in methods:
                        if f"📝 {mname}" == message.text:
                            method_id = mid
                            break
                    
                    if method_id:
                        await state.update_data(admin_requisites_method_id=method_id)
                        requisites = get_exchange_requisites_with_id(method_id)
                        if requisites:
                            text = "Реквизиты для метода оплаты:\n\n"
                            for req_id, req_type, req_value in requisites:
                                text += format_requisite_display(req_type, req_value) + "\n"
                            await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                        else:
                            await message.answer("Реквизитов нет. Добавьте первый реквизит:", reply_markup=get_admin_requisites_keyboard([]))
                    else:
                        await message.answer("Выберите метод оплаты из списка:", reply_markup=get_admin_methods_keyboard(methods))
            elif current_state == CaptchaStates.admin_edit_requisite_value:
                if message.text == "❌ Отмена":
                    data = await state.get_data()
                    method_id = data.get("admin_requisites_method_id")
                    if method_id:
                        requisites = get_exchange_requisites_with_id(method_id)
                        await state.set_state(CaptchaStates.admin_manage_requisites_method)
                        if requisites:
                            text = "Реквизиты для метода оплаты:\n\n"
                            for req_id, req_type, req_value in requisites:
                                text += format_requisite_display(req_type, req_value) + "\n"
                            await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                        else:
                            await message.answer("Реквизитов нет. Добавьте первый реквизит:", reply_markup=get_admin_requisites_keyboard([]))
                    else:
                        await state.clear()
                        await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
                else:
                    data = await state.get_data()
                    requisite_id = data.get("admin_edit_requisite_id")
                    method_id = data.get("admin_requisites_method_id")
                    if requisite_id and method_id:
                        update_exchange_requisite(requisite_id, message.text)
                        requisites = get_exchange_requisites_with_id(method_id)
                        text = "✅ Реквизит обновлен!\n\nРеквизиты для метода оплаты:\n\n"
                        for req_id, req_type, req_value in requisites:
                            text += f"• {req_type}: <code>{req_value}</code>\n"
                        await state.set_state(CaptchaStates.admin_manage_requisites_method)
                        await message.answer(text, reply_markup=get_admin_requisites_keyboard(requisites), parse_mode="HTML")
                    else:
                        await message.answer("Ошибка. Попробуйте снова.", reply_markup=get_admin_panel_keyboard())
                        await state.clear()
            elif current_state == CaptchaStates.admin_links:
                link_fields = {
                    "📊 rates": ("BTC_RATE_RUB", "rates"),
                    "💰 sell_btc": ("SELL_USERNAME", "sell_btc"),
                    "📢 news_channel": ("CONTACT_NEWS", "news_channel"),
                    "👨‍💻 operator": ("CONTACT_SUPPORT", "operator"),
                    "👨‍💻 operator2": ("CONTACT_BOSS", "operator2"),
                    "📣 operator3": ("CONTACT_REVIEWS", "operator3"),
                    "🏧 work_operator": ("WORK_OPERATOR", "work_operator"),
                }
                if message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
                elif message.text in link_fields:
                    env_key, field_name = link_fields[message.text]
                    await state.update_data(admin_edit_link_key=env_key, admin_edit_link_field=field_name)
                    current_value = os.getenv(env_key, "")
                    await state.set_state(CaptchaStates.admin_edit_link)
                    await message.answer(f"Введите новое значение для {field_name}:\nТекущее: <code>{current_value}</code>", reply_markup=get_promo_cancel_keyboard(), parse_mode="HTML")
                else:
                    await message.answer("Выберите поле для редактирования:", reply_markup=get_admin_links_keyboard())
            elif current_state == CaptchaStates.admin_edit_link:
                if message.text == "❌ Отмена":
                    await state.clear()
                    await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
                else:
                    data = await state.get_data()
                    env_key = data.get("admin_edit_link_key")
                    if env_key and message.text:
                        update_env_var(env_key, message.text)
                        os.environ[env_key] = message.text
                        await state.clear()
                        await message.answer(f"✅ Значение '{env_key}' обновлено на: <code>{message.text}</code>", reply_markup=get_admin_panel_keyboard(), parse_mode="HTML")
                    else:
                        await state.clear()
                        await message.answer("Админ-панель", reply_markup=get_admin_panel_keyboard())
            elif current_state == CaptchaStates.waiting_for_receipt:
                if message.photo:
                    data = await state.get_data()
                    from_buy = data.get("from_buy", False)
                    await state.clear()
                    if from_buy:
                        await message.answer("✅ Чек получен. Заявка принята. Ожидайте обработки.", reply_markup=get_main_menu_keyboard())
                    else:
                        await message.answer("✅ Чек получен. Заявка принята. Ожидайте обработки.", reply_markup=get_wallet_keyboard())
                else:
                    await message.answer("Отправьте фото или скриншот чека об оплате, или используйте кнопки под сообщением.")
            else:
                await message.answer("⬇️ Выберите меню ниже:", reply_markup=get_main_menu_keyboard())


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

