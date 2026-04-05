import os
import sqlite3
import logging
import asyncio
import random
import re
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest, Forbidden
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
from datetime import datetime, date
from collections import OrderedDict

import httpx

load_dotenv()

_AMOUNT_RE = re.compile(r"[-+]?\d[\d\s]*(?:[.,]\d+)?")
_AMOUNT_CRYPTO_MARKERS = ("btc", "ltc", "xmr")
_AMOUNT_RUB_MARKERS = ("руб", "rub", "₽")


async def send_message_ignore_forbidden(bot, chat_id, **kwargs):
    try:
        return await bot.send_message(chat_id=chat_id, **kwargs)
    except Forbidden:
        logging.warning("Skipping blocked chat_id=%s", chat_id)
        return None

API_URL = "https://api.coingecko.com/api/v3/simple/price"
_RATES_HTTP_TIMEOUT = httpx.Timeout(6.0, connect=2.0)
_RATES_FETCH_RETRIES = 3
_RATES_RETRY_DELAY_SEC = 0.8


async def get_btc_rates() -> dict[str, float]:
    """
    Fetches crypto exchange rates from CoinGecko API.
    Returns dict with BTC, LTC, XMR, USDT rates in RUB.
    """
    params = {
        "ids": "bitcoin,litecoin,monero,tether",
        "vs_currencies": "rub",
    }
    last_error = None
    async with httpx.AsyncClient(timeout=_RATES_HTTP_TIMEOUT) as client:
        for attempt in range(1, _RATES_FETCH_RETRIES + 1):
            try:
                resp = await client.get(API_URL, params=params)
                resp.raise_for_status()
                payload = resp.json()
                return {
                    "BTC": float(payload["bitcoin"]["rub"]),
                    "LTC": float(payload["litecoin"]["rub"]),
                    "XMR": float(payload["monero"]["rub"]),
                    "USDT": float(payload["tether"]["rub"]),
                }
            except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt >= _RATES_FETCH_RETRIES:
                    break

    print(f"[RATES] Cannot fetch crypto rates from CoinGecko after {_RATES_FETCH_RETRIES} attempts: {last_error}")
    return {}


async def update_exchange_rates():
    """
    Updates global EXCHANGE_RATES and CRYPTO_RATES from CoinGecko.
    Should be called on startup and periodically.
    """
    global EXCHANGE_RATES, CRYPTO_RATES

    rates = await get_btc_rates()
    if rates:
        EXCHANGE_RATES['BTC'] = rates['BTC']
        EXCHANGE_RATES['LTC'] = rates['LTC']
        EXCHANGE_RATES['XMR'] = rates['XMR']
        EXCHANGE_RATES['USDT'] = rates['USDT']

        CRYPTO_RATES["BTC"]["rub"] = EXCHANGE_RATES['BTC']
        CRYPTO_RATES["XMR"]["rub"] = EXCHANGE_RATES['XMR']
        CRYPTO_RATES["LTC"]["rub"] = EXCHANGE_RATES['LTC']

        print(f"[RATES] Updated from CoinGecko: BTC={EXCHANGE_RATES['BTC']}, LTC={EXCHANGE_RATES['LTC']}, XMR={EXCHANGE_RATES['XMR']}, USDT={EXCHANGE_RATES['USDT']}")
    else:
        print("[RATES] Using fallback hardcoded rates - CoinGecko unavailable")

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv('BOT_TOKEN')                  # токен должен быть в .env
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')       # админ-чат тоже в .env

# Ссылки и контакты
SUPPORT_CHANNEL    = os.getenv('SUPPORT_CHANNEL',    '@hustletrade')
REFERRAL_LINK      = os.getenv('REFERRAL_LINK',      'https://t.me/hustletradebot?start=ref')
HASLER_USERNAME    = os.getenv('HASLER_USERNAME',    '@huctleexchangesuport_bot')
RULES_LINK         = os.getenv('RULES_LINK',         'https://telegra.ph/Polzovatelskoe-soglashenie-02-02-4')
SUPPORT_LINK       = os.getenv('SUPPORT_LINK',       'https://t.me/hustletrade_support')
CHANNEL_LINK       = os.getenv('CHANNEL_LINK',       'https://t.me/hustletrade')
REFERRALS_LINK     = os.getenv('REFERRALS_LINK',     'https://t.me/hustletrade_ref')
REVIEWS_LINK       = os.getenv('REVIEWS_LINK',       'https://t.me/hustletrade_reviews')
PROMOCODE_LINK     = os.getenv('PROMOCODE_LINK',     'https://t.me/hustletrade_promo')
DIRECT_CONTACT     = os.getenv('DIRECT_CONTACT',     '@huctleexchangesuport_bot')

# Реквизиты
BANK_NAME         = "ЯНДЕКС БАНК"
SBP_WALLET        = "+79168013083"
CARD_WALLET       = "2201960478579688"       # если СБП и телефон разные — укажи отдельно
RECIPIENT_NAME    = "Лещина Богдан Андреевич"
OPERATOR_USERNAME = os.getenv('OPERATOR_USERNAME', '@huctleexchangesuport_bot')
WALLETS = {
    'SBP': SBP_WALLET,
    'BTC': os.getenv('BTC_WALLET', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'),
    'XMR': os.getenv('XMR_WALLET', ''),
    'LTC': os.getenv('LTC_WALLET', '')
}
CRYPTO_EXAMPLES = {
    "BTC": "0.01 или 0,01 или 5000",
    "XMR": "0.5 или 0,5 или 15000",
    "LTC": "0.5 или 0,5 или 3000"
}
EXCHANGE_RATES = {
    'BTC': 5750462.0,
    'LTC': 4600.0,
    'XMR': 27074.0,
    'USDT': 80.0,
}
CRYPTO_RATES = {
    "BTC": {"usd": float(os.getenv('BTC_RATE_USD', '90000')), "rub": EXCHANGE_RATES['BTC']},
    "XMR": {"usd": float(os.getenv('XMR_RATE_USD', '200')), "rub": EXCHANGE_RATES['XMR']},
    "LTC": {"usd": float(os.getenv('LTC_RATE_USD', '60')), "rub": EXCHANGE_RATES['LTC']}
}
COMMISSION_PERCENT = float(os.getenv("COMMISSION_PERCENT", "20"))
MINIMUM_EXCHANGE_AMOUNT_RUB = float(os.getenv('MIN_AMOUNT', '1500'))
MINIMUM_CRYPTO_AMOUNTS = {
    "BTC": 0.00017,
    "XMR": 0.095,
    "LTC": 0.19
}
BTC_MIN = 0.00019
BTC_MAX = 0.012
user_data = {}
captcha_data = {}
stats = {
    "total_starts": 0,
    "unique_users": set(),
    "total_orders": 0,
    "starts_by_date": {},
    "orders_by_date": {},
    "last_updated": "—"
}
ADMIN_IDS = {int(ADMIN_CHAT_ID)} if ADMIN_CHAT_ID else set()
admin_state = {}

# ────────────────────────────────────────────────
#          Настройки — сохранение и загрузка
# ────────────────────────────────────────────────

import os
import json

SETTINGS_FILE = "settings.json"

DEFAULT_SETTINGS = {
    "BANK_NAME": "ЯНДЕКС БАНК",
    "SBP_WALLET": "+79168013083",
    "CARD_WALLET": "2201960478579688",
    "RECIPIENT_NAME": "Лещина Богдан Андреевич",
    "OPERATOR_USERNAME": os.getenv('OPERATOR_USERNAME', '@huctleexchangesuport_bot'),
    "COMMISSION_PERCENT": 20,
    "MINIMUM_EXCHANGE_AMOUNT_RUB": 1500.0,
    "RATE_BTC": 5750462.0,
    "RATE_LTC": 4600.0,
    "RATE_XMR": 27074.0,
    "RATE_USDT": 80.0,
}

def load_settings():
    """
    Загружает настройки из settings.json при запуске бота.
    Если файла нет или ошибка — использует значения по умолчанию.
    """
    global BANK_NAME, SBP_WALLET, CARD_WALLET, RECIPIENT_NAME, OPERATOR_USERNAME, COMMISSION_PERCENT, MINIMUM_EXCHANGE_AMOUNT_RUB
    global EXCHANGE_RATES, CRYPTO_RATES

    full_path = os.path.abspath(SETTINGS_FILE)
    print(f"[SETTINGS] Загрузка настроек из: {full_path}")

    if not os.path.isfile(SETTINGS_FILE):
        print("[SETTINGS] Файл settings.json НЕ найден → берём значения по умолчанию")
    else:
        print("[SETTINGS] Файл найден, пытаемся прочитать...")

    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print("[SETTINGS] Успешно загружено из JSON:", data)

        BANK_NAME                   = data.get("BANK_NAME",                   DEFAULT_SETTINGS["BANK_NAME"])
        SBP_WALLET                  = data.get("SBP_WALLET",                  DEFAULT_SETTINGS["SBP_WALLET"])
        CARD_WALLET                 = data.get("CARD_WALLET",                 DEFAULT_SETTINGS["CARD_WALLET"])
        RECIPIENT_NAME              = data.get("RECIPIENT_NAME",              DEFAULT_SETTINGS["RECIPIENT_NAME"])
        OPERATOR_USERNAME           = data.get("OPERATOR_USERNAME",           DEFAULT_SETTINGS["OPERATOR_USERNAME"])
        COMMISSION_PERCENT          = data.get("COMMISSION_PERCENT",          DEFAULT_SETTINGS["COMMISSION_PERCENT"])
        MINIMUM_EXCHANGE_AMOUNT_RUB = data.get("MINIMUM_EXCHANGE_AMOUNT_RUB", DEFAULT_SETTINGS["MINIMUM_EXCHANGE_AMOUNT_RUB"])

        EXCHANGE_RATES['BTC'] = float(data.get("RATE_BTC", DEFAULT_SETTINGS["RATE_BTC"]))
        EXCHANGE_RATES['LTC'] = float(data.get("RATE_LTC", DEFAULT_SETTINGS["RATE_LTC"]))
        EXCHANGE_RATES['XMR'] = float(data.get("RATE_XMR", DEFAULT_SETTINGS["RATE_XMR"]))
        EXCHANGE_RATES['USDT'] = float(data.get("RATE_USDT", DEFAULT_SETTINGS["RATE_USDT"]))

        CRYPTO_RATES["BTC"]["rub"] = EXCHANGE_RATES['BTC']
        CRYPTO_RATES["XMR"]["rub"] = EXCHANGE_RATES['XMR']
        CRYPTO_RATES["LTC"]["rub"] = EXCHANGE_RATES['LTC']

    except Exception as e:
        print(f"[SETTINGS] Ошибка чтения JSON → используем значения по умолчанию: {e}")
        BANK_NAME                   = DEFAULT_SETTINGS["BANK_NAME"]
        SBP_WALLET                  = DEFAULT_SETTINGS["SBP_WALLET"]
        CARD_WALLET                 = DEFAULT_SETTINGS["CARD_WALLET"]
        RECIPIENT_NAME              = DEFAULT_SETTINGS["RECIPIENT_NAME"]
        OPERATOR_USERNAME           = DEFAULT_SETTINGS["OPERATOR_USERNAME"]
        COMMISSION_PERCENT          = DEFAULT_SETTINGS["COMMISSION_PERCENT"]
        MINIMUM_EXCHANGE_AMOUNT_RUB = DEFAULT_SETTINGS["MINIMUM_EXCHANGE_AMOUNT_RUB"]

        EXCHANGE_RATES['BTC'] = DEFAULT_SETTINGS["RATE_BTC"]
        EXCHANGE_RATES['LTC'] = DEFAULT_SETTINGS["RATE_LTC"]
        EXCHANGE_RATES['XMR'] = DEFAULT_SETTINGS["RATE_XMR"]
        EXCHANGE_RATES['USDT'] = DEFAULT_SETTINGS["RATE_USDT"]

        CRYPTO_RATES["BTC"]["rub"] = EXCHANGE_RATES['BTC']
        CRYPTO_RATES["XMR"]["rub"] = EXCHANGE_RATES['XMR']
        CRYPTO_RATES["LTC"]["rub"] = EXCHANGE_RATES['LTC']


def save_settings():
    """
    Сохраняет текущие глобальные настройки в settings.json
    Вызывается после каждого изменения в админке
    """
    data = {
        "BANK_NAME": BANK_NAME,
        "SBP_WALLET": SBP_WALLET,
        "CARD_WALLET": CARD_WALLET,
        "RECIPIENT_NAME": RECIPIENT_NAME,
        "OPERATOR_USERNAME": OPERATOR_USERNAME,
        "COMMISSION_PERCENT": COMMISSION_PERCENT,
        "MINIMUM_EXCHANGE_AMOUNT_RUB": MINIMUM_EXCHANGE_AMOUNT_RUB,
        "RATE_BTC": EXCHANGE_RATES['BTC'],
        "RATE_LTC": EXCHANGE_RATES['LTC'],
        "RATE_XMR": EXCHANGE_RATES['XMR'],
        "RATE_USDT": EXCHANGE_RATES['USDT'],
    }

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[SETTINGS] Успешно сохранено в: {os.path.abspath(SETTINGS_FILE)}")
        print("[SETTINGS] Сохранённые данные:", data)
    except Exception as e:
        print(f"[SETTINGS] Ошибка при сохранении JSON: {e}")

# Глобальные переменные для админки
admin_state = {}          # состояния админа
banned_users = set()      # кэш забаненных (будем загружать из БД)

def is_banned(user_id: int) -> bool:
    return user_id in banned_users
def generate_random_background(width, height):
    mode = random.choice(['solid', 'gradient', 'noise', 'texture'])

    if mode == 'solid':
        # Однотонный цвет
        color = tuple(random.randint(10, 80) for _ in range(3))
        return Image.new('RGB', (width, height), color)

    elif mode == 'gradient':
        # Вертикальный градиент
        base = Image.new('RGB', (width, height))
        for y in range(height):
            r = int(30 + (y / height) * 100)
            g = int(20 + (y / height) * 80)
            b = int(50 + (y / height) * 60)
            for x in range(width):
                base.putpixel((x, y), (r, g, b))
        return base

    elif mode == 'noise':
        # Шумовой фон
        base = Image.new('RGB', (width, height))
        for x in range(width):
            for y in range(height):
                base.putpixel((x, y), tuple(random.randint(0, 100) for _ in range(3)))
        return base.filter(ImageFilter.GaussianBlur(radius=1.5))

    elif mode == 'texture':
        # Имитация текстуры (например, бетон)
        base = Image.new('RGB', (width, height), (40, 40, 40))
        draw = ImageDraw.Draw(base)
        for _ in range(300):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(10, 40)
            draw.ellipse((x, y, x + r, y + r), fill=(60, 60, 60))
        return base.filter(ImageFilter.GaussianBlur(radius=2))


def generate_captcha():
    print(">>> Кастомная капча: случайный фон, углы, шум, ухудшение качества <<<")

    #  Генерация текста
    captcha_text = ''.join(random.choices('0123456789', k=random.randint(5, 7)))

    #  Случайный фон
    width, height = 420, 140
    image = generate_random_background(width, height)
    draw = ImageDraw.Draw(image)

    #  Шрифт
    try:
        font = ImageFont.truetype("fonts/DejaVuSans.ttf", 110)
    except Exception as e:
        print("Ошибка загрузки шрифта:", e)
        font = ImageFont.load_default()
    #  Центровка
    spacing = 60
    total_width = len(captcha_text) * spacing
    x_start = (width - total_width) // 2

    #  Цвета символов
    symbol_colors = [(255, 0, 0), (255, 255, 0), (255, 128, 0)]  # красный, жёлтый, оранжевый

    #  Рисуем символы
    for i, char in enumerate(captcha_text):
        layer = Image.new('RGBA', (110, 110), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)

        color = random.choice(symbol_colors)
        bbox = d.textbbox((0, 0), char, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = (110 - tw) // 2
        ty = (110 - th) // 2

        d.text((tx, ty), char, font=font, fill=color)

        angle = random.uniform(-20, 20)
        rotated = layer.rotate(angle, expand=True, resample=Image.BICUBIC)

        px = x_start + i * spacing + random.randint(-10, 10)
        py = 20 + random.randint(-10, 10)
        image.paste(rotated, (px, py), rotated)

    #  Линии
    for _ in range(random.randint(5, 7)):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill=(255, 255, 255), width=2)

    #  Шум
    for _ in range(150):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(255, 255, 255))

    #  Ухудшение качества
    image = image.filter(ImageFilter.GaussianBlur(radius=1.5))
    image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=50))
    image = image.convert("RGB")

    #  Сохраняем
    buf = io.BytesIO()
    image.save(buf, format='JPEG', quality=30)
    buf.seek(0)

    return captcha_text, buf


def generate_order_id():
    return ''.join(random.choices(string.digits, k=6))

def init_database():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            btc_balance REAL DEFAULT 0,
            xmr_balance REAL DEFAULT 0,
            ltc_balance REAL DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            captcha_passed BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            user_id INTEGER,
            crypto_type TEXT,
            amount REAL,
            rub_amount REAL,
            wallet_address TEXT,
            payment_method TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT
        )
    ''')

    conn.commit()
    conn.close()

    # Загружаем список забаненных в память при старте
    global banned_users
    banned_users = load_banned_users()

def load_banned_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM bans')
    users = {row[0] for row in cursor.fetchall()}
    conn.close()
    return users


def ban_user(user_id: int, reason: str = "Админ забанил"):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO bans (user_id, reason) VALUES (?, ?)', (user_id, reason))
    conn.commit()
    conn.close()
    banned_users.add(user_id)


def unban_user(user_id: int):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    banned_users.discard(user_id)


def is_banned(user_id: int) -> bool:
    return user_id in banned_users

def check_captcha_passed(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('PRAGMA table_info(users)')
    columns = [column[1] for column in cursor.fetchall()]

    if 'captcha_passed' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN captcha_passed BOOLEAN DEFAULT FALSE')
        conn.commit()

    cursor.execute('SELECT captcha_passed FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()

    return result and result[0]

def set_captcha_passed(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('PRAGMA table_info(users)')
    columns = [column[1] for column in cursor.fetchall()]

    if 'captcha_passed' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN captcha_passed BOOLEAN DEFAULT FALSE')

    cursor.execute('INSERT OR REPLACE INTO users (user_id, captcha_passed) VALUES (?, TRUE)', (user_id,))
    conn.commit()
    conn.close()

def get_user_stats(user_id, username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username)
        VALUES (?, ?)
    ''', (user_id, username))

    cursor.execute('''
        SELECT btc_balance, xmr_balance, ltc_balance, total_orders
        FROM users WHERE user_id = ?
    ''', (user_id,))

    result = cursor.fetchone()
    conn.commit()
    conn.close()

    if result:
        return {
            'btc_balance': result[0] or 0,
            'xmr_balance': result[1] or 0,
            'ltc_balance': result[2] or 0,
            'total_orders': result[3] or 0
        }
    else:
        return {
            'btc_balance': 0,
            'xmr_balance': 0,
            'ltc_balance': 0,
            'total_orders': 0
        }

def update_user_balance(user_id, crypto_type, amount):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('SELECT btc_balance, xmr_balance, ltc_balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if not result:
        cursor.execute('INSERT INTO users (user_id, btc_balance, xmr_balance, ltc_balance, total_orders) VALUES (?, 0, 0, 0, 0)', (user_id,))

    if crypto_type == 'BTC':
        cursor.execute('UPDATE users SET btc_balance = btc_balance + ?, total_orders = total_orders + 1 WHERE user_id = ?', (amount, user_id))
    elif crypto_type == 'XMR':
        cursor.execute('UPDATE users SET xmr_balance = xmr_balance + ?, total_orders = total_orders + 1 WHERE user_id = ?', (amount, user_id))
    elif crypto_type == 'LTC':
        cursor.execute('UPDATE users SET ltc_balance = ltc_balance + ?, total_orders = total_orders + 1 WHERE user_id = ?', (amount, user_id))

    conn.commit()
    conn.close()

def create_order(user_id, crypto_type, amount, rub_amount, wallet_address, payment_method):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    order_number = generate_order_id()

    cursor.execute('''
        INSERT INTO orders (order_number, user_id, crypto_type, amount, rub_amount, wallet_address, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (order_number, user_id, crypto_type, amount, rub_amount, wallet_address, payment_method))

    order_id = cursor.lastrowid
    global stats
    today = date.today().isoformat()
    stats["total_orders"] += 1
    stats["orders_by_date"][today] = stats["orders_by_date"].get(today, 0) + 1
    stats["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.commit()
    conn.close()
    return order_id, order_number

def update_order_status(order_id, status):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))

    conn.commit()
    conn.close()

def get_pending_orders():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT o.order_id, o.order_number, o.user_id, u.username, o.crypto_type, o.amount, o.rub_amount, o.wallet_address, o.payment_method
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.status = 'pending'
    ''')

    orders = cursor.fetchall()
    conn.close()
    return orders

def get_order_by_number(order_number):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT o.order_id, o.order_number, o.user_id, u.username, o.crypto_type, o.amount, o.rub_amount, o.wallet_address, o.payment_method, o.status
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.order_number = ?
    ''', (order_number,))

    order = cursor.fetchone()
    conn.close()
    return order

def get_user_orders(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT order_number, crypto_type, amount, rub_amount, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
    ''', (user_id,))

    orders = cursor.fetchall()
    conn.close()
    return orders

async def safe_edit_message(query, text, reply_markup=None, parse_mode='HTML', disable_web_page_preview=True):
    try:
        await query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        elif "There is no text in the message to edit" in str(e):
            await query.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        else:
            raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Получаем user_id надёжно (из сообщения или колбэка)
    if update.message:
        user_id = update.message.from_user.id
    elif update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        return  # редкий случай, но на всякий

    # Проверка бана — сразу в начале, до капчи и всего остального
    if is_banned(user_id):
        await update.message.reply_text(
            "🚫 Вы заблокированы в боте.\n"
            "Если считаете, что это ошибка — напишите в поддержку."
        )
        return

    # Дальше обычная логика
    if not check_captcha_passed(user_id):
        await send_captcha(update, context, user_id)
        return

    global stats
    stats["total_starts"] += 1
    stats["unique_users"].add(user_id)
    today = date.today().isoformat()
    stats["starts_by_date"][today] = stats["starts_by_date"].get(today, 0) + 1
    stats["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    keyboard = [
        [InlineKeyboardButton("Купить", callback_data="buy")],
        [InlineKeyboardButton("Промокод", callback_data="promo")],
        [InlineKeyboardButton("Личный кабинет", callback_data="profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    start_text = (
        "♻️ HUSTLE TRADE — это обменник электронных валют.\n\n"
        "⚡️ Если впервые пользуешься нашим сервисом, советуем ознакомиться с <a href='{}'>пользовательским соглашением</a>.\n\n"
        "🔰 Хочешь обменять крипту? Предлагаем актуальнейшие курсы на обмен — жми кнопку: «КУПИТЬ».\n\n"
        "♻️ Мы — лучшие на рынке крипто-обмена."
    ).format(RULES_LINK)

    try:
        with open('photo1.jpg', 'rb') as photo:
            if update.message:
                await update.message.reply_photo(
                    photo=photo,
                    caption=start_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                try:
                    await update.callback_query.message.reply_photo(
                        photo=photo,
                        caption=start_text,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                    await update.callback_query.message.delete()
                except:
                    await safe_edit_message(update.callback_query, start_text, reply_markup)
    except FileNotFoundError:
        if update.message:
            await update.message.reply_text(start_text, reply_markup=reply_markup, parse_mode='HTML', disable_web_page_preview=True)
        else:
            await safe_edit_message(update.callback_query, start_text, reply_markup)

async def send_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    captcha_text, captcha_image = generate_captcha()
    captcha_data[user_id] = captcha_text

    if update.message:
        await update.message.reply_photo(
            photo=captcha_image,
            caption="<b>🔐 Введите цифры с картинки для продолжения:</b>",
            parse_mode='HTML'
        )
    else:
        await update.callback_query.message.reply_photo(
            photo=captcha_image,
            caption="<b>🔐 Введите цифры с картинки для продолжения:</b>",
            parse_mode='HTML'
        )

async def verify_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text

    if user_id in captcha_data and user_input == captcha_data[user_id]:
        set_captcha_passed(user_id)
        del captcha_data[user_id]
        await update.message.reply_text("✅ Капча пройдена успешно!")
        await start(update, context)
    else:
        captcha_text, captcha_image = generate_captcha()
        captcha_data[user_id] = captcha_text
        await update.message.reply_photo(
            photo=captcha_image,
            caption="❌ Неверная капча! Попробуйте еще раз:",
            parse_mode='HTML'
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if not check_captcha_passed(user_id):
        await send_captcha(update, context, user_id)
        return

    data = query.data

    if data == "buy":
        await show_crypto_selection(query)
    elif data == "promo":
        await show_promo_menu(query)
    elif data == "profile":
        await show_profile(query, user_id)
    elif data == "back_main":
        await main_menu(query)
    elif data in ["BTC", "XMR", "LTC"]:
        if user_id not in user_data:
            user_data[user_id] = {}
        user_data[user_id]['crypto'] = data
        user_data[user_id].pop('waiting_for_amount_detailed', None)
        user_data[user_id].pop('payment', None)
        user_data[user_id].pop('amount', None)
        user_data[user_id].pop('rub_amount', None)
        await ask_amount_detailed(query, user_id, data)
    elif data in ["sbp", "card"]:
        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]['payment'] = data

        await ask_wallet_address_before_confirmation(query, user_id)
    elif data == "back_crypto":
        await show_crypto_selection(query)
    elif data == "back_payment":
        await show_payment_methods(query)
    elif data == "agree":

        await show_payment_details(query, user_id)
    elif data == "paid":
        await confirm_payment(query, user_id, context)
    elif data == "cancel":
        await cancel_operation(query, user_id)
    elif data == "my_orders":
        await show_user_orders(query, user_id)
    elif data.startswith("confirm_"):
        order_id = int(data.split("_")[1])
        await confirm_crypto_sent(query, order_id, context)
    elif data.startswith("check_status_"):
        order_number = data.split("_")[2]
        await check_order_status(query, order_number, user_id)

async def ask_wallet_address_before_confirmation(query, user_id):
    try:
        with open('photo3.jpg', 'rb') as photo:
            keyboard = [
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await query.message.delete()
            except:
                pass

            await query.message.reply_photo(
                photo=photo,
                caption="<b>Введи адрес своего кошелька, куда нужно перевести криптовалюту:</b>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

    except FileNotFoundError:
        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.message.delete()
        except:
            pass

        await query.message.reply_text("<b>Введи адрес своего кошелька, куда нужно перевести криптовалюту:</b>", reply_markup=reply_markup, parse_mode='HTML')

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['waiting_for_wallet_before_confirm'] = True

async def ask_amount_detailed(query, user_id, crypto_type):
    if crypto_type not in CRYPTO_EXAMPLES:
        examples = "0.01 или 0,01 или 1000"
    else:
        examples = CRYPTO_EXAMPLES.get(crypto_type, "0.01 или 0,01 или 1000")

    text = (
        f"<b>Покупка {crypto_type}</b>\n\n"
        f"Укажите сумму в {crypto_type} или RUB:\n\n"
        f"Пример: <code>{examples}</code>\n\n"
        f"<b>Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB:.0f} руб.</b>"
    )

    keyboard = [
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.delete()
    except:
        pass

    await query.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['waiting_for_amount_detailed'] = True
    user_data[user_id].pop('amount', None)
    user_data[user_id].pop('rub_amount', None)

async def check_order_status(query, order_number, user_id):
    order = get_order_by_number(order_number)

    if not order:
        await safe_edit_message(query, "❌ Заказ не найден")
        return

    order_id, order_number, order_user_id, username, crypto_type, amount, rub_amount, wallet_address, payment_method, status = order

    if order_user_id != user_id:
        await safe_edit_message(query, "❌ У вас нет доступа к этому заказу")
        return

    status_text = {
        'pending': 'платеж проверяется...',
        'completed': 'Выполнен',
        'cancelled': 'отменен'
    }.get(status, 'неизвестен')

    formatted_amount = f"{amount:.8f}".rstrip('0').rstrip('.') if '.' in f"{amount:.8f}" else f"{amount:.0f}"

    keyboard = [
        [InlineKeyboardButton("🔍 Проверить статус заново", callback_data=f"check_status_{order_number}")],
        [InlineKeyboardButton("⬅️ НАЗАД", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    status_message = (
        f"<b>♻️Статус: {status_text}</b>...<i>Это происходит автоматически - не стоит обращаться в бота обратной связи для ускорения проверки.</i>\n\n🧑‍💻Отправьте чек оператору: {OPERATOR_USERNAME}"
    )

    await safe_edit_message(query, status_message, reply_markup)

async def confirm_crypto_sent(query, order_id, context):
    order_info = None
    pending_orders = get_pending_orders()

    for order in pending_orders:
        if order[0] == order_id:
            order_info = order
            break

    if order_info:
        user_id = order_info[2]
        crypto_type = order_info[4]
        amount = order_info[5]
        order_number = order_info[1]

        update_user_balance(user_id, crypto_type, amount)
        update_order_status(order_id, 'completed')

        formatted_amount = f"{amount:.8f}".rstrip('0').rstrip('.') if '.' in f"{amount:.8f}" else f"{amount:.0f}"

        await safe_edit_message(query, f"<b>✅ Выдача криптовалюты подтверждена!</b>\n\n💎 {formatted_amount} {crypto_type} зачислено на счет пользователя\n📦 ID заказа: {order_number}")

        await send_message_ignore_forbidden(
            context.bot,
            user_id,
            text=(
                f"<b>🎉 Твоя криптовалюта зачислена!</b>\n\n"
                f"💎 Ты получил: {formatted_amount} {crypto_type}\n"
                f"📦 ID заказа: {order_number}\n\n"
                "✅ Спасибо за использование HUSTLE TRADE!"
            ),
            parse_mode='HTML',
        )
    else:
        await safe_edit_message(query, "❌ Заказ не найден")

async def cancel_operation(query, user_id):
    if user_id in user_data:
        user_data[user_id].clear()
        del user_data[user_id]
    await main_menu(query)

async def main_menu(query):
    keyboard = [
        [InlineKeyboardButton("Купить", callback_data="buy")],
        [InlineKeyboardButton("Промокод", callback_data="promo")],
        [InlineKeyboardButton("Личный кабинет", callback_data="profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    start_text = (
        "♻️ HUSTLE TRADE — это обменник электронных валют.\n\n"
        "⚡️ Если впервые пользуешься нашим сервисом, советуем ознакомиться с <a href='{}'>пользовательским соглашением</a>.\n\n"
        "🔰 Хочешь обменять крипту? Предлагаем актуальнейшие курсы на обмен — жми кнопку: «КУПИТЬ».\n\n"
        "♻️ Мы — лучшие на рынке крипто-обмена."
    ).format(RULES_LINK)

    try:
        with open('photo1.jpg', 'rb') as photo:
            try:
                await query.message.reply_photo(
                    photo=photo,
                    caption=start_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                await query.message.delete()
            except:
                await safe_edit_message(query, start_text, reply_markup)
    except FileNotFoundError:
        await safe_edit_message(query, start_text, reply_markup)

async def show_crypto_selection(query):
    keyboard = [
        [InlineKeyboardButton("XMR", callback_data="XMR"), InlineKeyboardButton("LTC", callback_data="LTC")],
        [InlineKeyboardButton("BTC", callback_data="BTC")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.delete()
    except:
        pass

    await query.message.reply_text("<b>Выбирай какую крипту желаешь купить:</b>", reply_markup=reply_markup, parse_mode='HTML')

async def show_payment_methods(query):
    contact_username = DIRECT_CONTACT.replace('@', '')
    keyboard = [
        [InlineKeyboardButton("👨🏻‍💻 Напрямую", url=f"https://t.me/{contact_username}")],
        [InlineKeyboardButton("📱 Перевод по СБП", callback_data="sbp")],
        [InlineKeyboardButton("💳 Перевод на карту", callback_data="card")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_crypto")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.delete()
    except:
        pass

    await query.message.reply_text("<b>Выбирай, куда собираешься оплачивать:</b>", reply_markup=reply_markup, parse_mode='HTML')

def _parse_amount_text(raw_amount: str) -> float | None:
    match = _AMOUNT_RE.search((raw_amount or "").replace("\u00a0", " "))
    if not match:
        return None
    normalized = match.group(0).replace(" ", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _detect_amount_kind(raw_amount: str) -> str | None:
    normalized = (raw_amount or "").replace("\u00a0", " ").strip().lower()
    has_crypto_markers = any(marker in normalized for marker in _AMOUNT_CRYPTO_MARKERS)
    has_rub_markers = any(marker in normalized for marker in _AMOUNT_RUB_MARKERS)

    if has_crypto_markers and has_rub_markers:
        return None
    if has_crypto_markers:
        return "crypto"
    if has_rub_markers:
        return "rub"
    if "." in normalized or "," in normalized:
        return "crypto"
    return "rub"

async def handle_amount_detailed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_data or not user_data[user_id].get('waiting_for_amount_detailed'):
        return

    amount = update.message.text
    crypto_type = user_data[user_id]['crypto']

    parsed_amount = _parse_amount_text(amount)
    if parsed_amount is None:
        await update.message.reply_text("❌ Неверный формат суммы. Пожалуйста, укажите число.")
        return

    amount_kind = _detect_amount_kind(amount)
    if amount_kind is None:
        await update.message.reply_text("❌ Смешанный формат суммы. Укажите либо крипту, либо RUB.")
        return

    rates = CRYPTO_RATES.get(crypto_type)

    try:
        logging.info(
            "Amount input user=%s raw=%r parsed=%s kind=%s crypto=%s",
            user_id,
            amount,
            parsed_amount,
            amount_kind,
            crypto_type,
        )

        if amount_kind == "crypto":
            crypto_amount = parsed_amount
            amount_rub = crypto_amount * rates["rub"]

            min_crypto = MINIMUM_CRYPTO_AMOUNTS.get(crypto_type, 0)
            if crypto_amount < min_crypto:
                await update.message.reply_text(f"❌ Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB:.0f} руб. ({min_crypto:.6f} {crypto_type})")
                return
        else:
            amount_rub = parsed_amount
            crypto_amount = amount_rub / rates["rub"]

            if amount_rub < MINIMUM_EXCHANGE_AMOUNT_RUB:
                min_crypto = MINIMUM_CRYPTO_AMOUNTS.get(crypto_type, 0)
                await update.message.reply_text(f"❌ Минимальная сумма обмена: {MINIMUM_EXCHANGE_AMOUNT_RUB:.0f} руб. ({min_crypto:.6f} {crypto_type})")
                return

        total_to_pay = round(amount_rub * (1 + COMMISSION_PERCENT / 100))

        formatted_crypto = "{:.8f}".format(crypto_amount).rstrip('0').rstrip('.')
        formatted_rub = "{:,.0f}".format(total_to_pay).replace(',', ' ')

        user_data[user_id]['amount'] = crypto_amount
        user_data[user_id]['rub_amount'] = total_to_pay
        user_data[user_id]['waiting_for_amount_detailed'] = False

        text = (
            f"Средний рыночный курс {crypto_type}: {rates['rub']:,.2f} руб.\n\n"
            f"💎Вы получите: {formatted_crypto} {crypto_type}\n"
            f"💵Ваш внутренний баланс кошелька: <b>0 руб.</b>\n\n"
            f"🚀Для продолжения выберите <b>Способ оплаты:</b>\n\n"
        )

        keyboard = [
            [InlineKeyboardButton("👨🏻‍💻 Напрямую", url=f"https://t.me/{DIRECT_CONTACT.replace('@', '')}")],
            [InlineKeyboardButton(f"📱 Перевод по СБП ({formatted_rub} руб.)", callback_data=f"sbp")],
            [InlineKeyboardButton(f"💳 Перевод на карту ({formatted_rub} руб.)", callback_data=f"card")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='HTML')

    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        await update.message.reply_text("❌ Произошла ошибка при расчете. Пожалуйста, попробуйте еще раз.")

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_data:
        return

    waiting_for_wallet = user_data[user_id].get('waiting_for_wallet')
    waiting_for_wallet_before_confirm = user_data[user_id].get('waiting_for_wallet_before_confirm')

    if not (waiting_for_wallet or waiting_for_wallet_before_confirm):
        return

    wallet_address = update.message.text
    user_data[user_id]['wallet_address'] = wallet_address

    user_data[user_id].pop('waiting_for_wallet', None)
    user_data[user_id].pop('waiting_for_wallet_before_confirm', None)

    user_info = user_data[user_id]
    crypto = user_info['crypto']
    amount = user_info['amount']
    rub_amount = user_info['rub_amount']

    formatted_crypto_amount = "{:.8f}".format(amount).rstrip('0').rstrip('.')
    formatted_rub_amount = "{:,.0f}".format(rub_amount).replace(',', ' ')

    keyboard = [
        [InlineKeyboardButton("✅ СОГЛАСЕН", callback_data="agree")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)


    confirmation_text = (
        f"💎 К получению будет: {formatted_crypto_amount} {crypto}.\n\n"
        f"🔫 Необходимо оплатить: {formatted_rub_amount} RUB.\n\n"
        f"✅ Нажми \"СОГЛАСЕН\" для получения реквизитов."
    )

    try:
        with open('photo1.jpg', 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=confirmation_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    except FileNotFoundError:
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup, parse_mode='HTML')

async def show_payment_details(query, user_id):
    """Показываем реквизиты для оплаты после нажатия СОГЛАСЕН"""
    user_info = user_data[user_id]
    crypto = user_info['crypto']
    amount = user_info['amount']
    rub_amount = user_info['rub_amount']
    wallet_address = user_info.get('wallet_address', 'Не указан')
    payment_method = user_info.get('payment', 'sbp')

    formatted_rub_amount = f"{rub_amount:.0f}"

    message = await query.message.reply_text("⏱️ Уно моменто, выдаем реквизиты...\n\nВремя ожидания от 5 секунд до 5 минут.")

    await asyncio.sleep(3)

    order_id, order_number = create_order(user_id, crypto, amount, rub_amount, wallet_address, payment_method)

    keyboard = [
        [InlineKeyboardButton("✅ Оплачено", callback_data="paid")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if payment_method == "card":
        реквизиты = f"<code>{BANK_NAME} | {CARD_WALLET}</code>"
        метод_текст = "на карту"
    else:  # sbp или любой другой
        реквизиты = f"<code>{BANK_NAME} | {SBP_WALLET}</code>"
        метод_текст = "по СБП"

    await message.edit_text(
        f"💎 ID: {order_number}\n\n"
        f"❗️Переводи ровно ту же сумму, что указана в заявке. Рубль в рубль .\n"
        f"❗️Средства отправленные не на указанный в заявке банк возврату *НЕ* подлежат .\n"
        f"❗️Менять кэш — только с личных карт. Мы не работаем с мошенниками .\n\n"
        f"⌛️У Вас 15 минут на оплату: {formatted_rub_amount} RUB ⬇️\n\n"
        f"{реквизиты}\n\n"
        f"✅ После оплаты необходимо сообщить боту об этом, нажав: \"ОПЛАЧЕНО\"\n\n",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

async def confirm_payment(query, user_id, context):
    user_info = user_data[user_id]
    crypto = user_info['crypto']
    amount = user_info['amount']
    rub_amount = user_info['rub_amount']
    wallet_address = user_info.get('wallet_address', 'Не указан')
    payment_method = user_info.get('payment', 'sbp')

    order_id, order_number = create_order(user_id, crypto, amount, rub_amount, wallet_address, payment_method)

    formatted_amount = f"{amount:.8f}".rstrip('0').rstrip('.') if '.' in f"{amount:.8f}" else f"{amount:.0f}"

    keyboard = [
        [InlineKeyboardButton("🔍 Проверить статус заявки", callback_data=f"check_status_{order_number}")],
        [InlineKeyboardButton("⬅️ НАЗАД", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await safe_edit_message(
        query,
        f"⚡️ <b>Проверяем перевод по сделке №{order_number}</b>!\n\n"
        f"⏰<b>Если все верно, в срок до 5-20 мин. ты автоматически получишь ссылку для отслеживания транзакции.</b>\n\n"
        f"🧾Отправьте чек оператору: {OPERATOR_USERNAME}",
        reply_markup
    )

    if ADMIN_CHAT_ID:
        payment_method_text = {
            'direct': 'Напрямую',
            'sbp': 'СБП',
            'card': 'Перевод на карту'
        }.get(payment_method, 'Неизвестно')

        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить выдачу", callback_data=f"confirm_{order_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        admin_message = (
            f"🆕 Новый заказ!\n\n"
            f"📦 ID заказа: {order_number}\n"
            f"👤 ID: {user_id}\n"
            f"📛 Username: @{query.from_user.username or 'N/A'}\n"
            f"👛 Кошелек: {wallet_address}\n\n"
            f"💎 Крипта: {formatted_amount} {crypto}\n"
            f"💰 Сумма: {rub_amount:.0f} RUB\n"
            f"💳 Способ оплаты: {payment_method_text}\n\n"
        )
        await send_message_ignore_forbidden(
            context.bot,
            ADMIN_CHAT_ID,
            text=admin_message,
            reply_markup=reply_markup,
        )

    if user_id in user_data:
        user_data[user_id].clear()
        del user_data[user_id]

async def show_promo_menu(query):
    keyboard = [
        [InlineKeyboardButton("Тех.Поддержка", url=SUPPORT_LINK)],
        [
            InlineKeyboardButton("Канал", url=CHANNEL_LINK),
            InlineKeyboardButton("Отзывы", url=REVIEWS_LINK)
        ],
        [
            InlineKeyboardButton("Заработать", url=REFERRALS_LINK),
            InlineKeyboardButton("Промокод", callback_data="promo")
        ],
        [InlineKeyboardButton("⬅️ НАЗАД", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.delete()
    except:
        pass

    await query.message.reply_text("<b>В настоящее время ты не используешь промокод</b>\n\nОтправь боту промокод, чтобы активировать его❗️", reply_markup=reply_markup, parse_mode='HTML')

async def show_profile(query, user_id):
    user_stats = get_user_stats(user_id, query.from_user.username)
    user_orders = get_user_orders(user_id)

    orders_text = ""
    if user_orders:
        for order in user_orders[:5]:
            order_number, crypto_type, amount, rub_amount, status, created_at = order
            status_emoji = "✅" if status == 'completed' else "⏳" if status == 'pending' else "❌"
            formatted_amount = f"{amount:.8f}".rstrip('0').rstrip('.') if '.' in f"{amount:.8f}" else f"{amount:.0f}"
            orders_text += f"{status_emoji} {order_number}: {formatted_amount} {crypto_type} - {rub_amount:.0f} RUB\n"
    else:
        orders_text = "📭 Нет заказов"

    try:
        with open('photo1.jpg', 'rb') as photo:
            profile_text = (
                f"<b>🆔Твой ID:</b> {user_id}\n\n"
                f"<b>👤Твой username:</b> {query.from_user.username or 'N/A'}\n\n"
                f"<b>📊Куплено крипты за все время:</b>\n"
                f"XMR: {user_stats['xmr_balance']:.8f}\n"
                f"LTC: {user_stats['ltc_balance']:.8f}\n"
                f"BTC: {user_stats['btc_balance']:.8f}\n\n"
                f"<b>🏷Персональная скидка:</b> 0 %\n\n"
                f"<b>💰Баланс:</b> 0 руб.\n\n"
                f"<b>👥Всего рефералов:</b> 0\n\n"
                f"<a href='{RULES_LINK}'>📜 Наши правила</a>\n\n"
            )

            keyboard = [
                [InlineKeyboardButton("ТехПоддержка", url=SUPPORT_LINK)],
                [
                    InlineKeyboardButton("Канал", url=CHANNEL_LINK),
                    InlineKeyboardButton("Отзывы", url=REVIEWS_LINK)
                ],
                [
                    InlineKeyboardButton("Рефералка", url=REFERRALS_LINK),
                    InlineKeyboardButton("Промокод", callback_data="promo")
                ],
                [InlineKeyboardButton("⬅️ НАЗАД", callback_data="back_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await query.message.delete()
            except:
                pass

            await query.message.reply_photo(photo=photo, caption=profile_text, reply_markup=reply_markup, parse_mode='HTML')

    except FileNotFoundError:
        profile_text = (
            f"<b>👤 Личный кабинет</b>\n\n"
            f"<b>🆔 Твой ID:</b> {user_id}\n\n"
            f"<b>👤 Твой username:</b> {query.from_user.username or 'N/A'}\n\n"
            f"<b>💎 Куплено крипты за все время:</b>\n"
            f"XMR: {user_stats['xmr_balance']:.8f}\n"
            f"LTC: {user_stats['ltc_balance']:.8f}\n"
            f"BTC: {user_stats['btc_balance']:.8f}\n\n"
            f"<b>🎯 Персональная скидка:</b> 0 %\n\n"
            f"<b>💰 Баланс:</b> 0 руб.\n\n"
            f"<b>👥 Всего рефералов:</b> 0\n\n"
            f"<b>📦 Всего заказов:</b> {user_stats['total_orders']}\n\n"
            f"<b>📋 Последние заказы:</b>\n{orders_text}\n\n"
            f"<a href='{RULES_LINK}'>📜 Наши правила</a>\n\n"
        )

        keyboard = [
            [InlineKeyboardButton("Обратная свзяь", url=SUPPORT_LINK)],
            [
                InlineKeyboardButton("Канал", url=CHANNEL_LINK),
                InlineKeyboardButton("Отзывы", url=REVIEWS_LINK)
            ],
            [
                InlineKeyboardButton("Заработать", url=REFERRALS_LINK),
                InlineKeyboardButton("Промокод", callback_data="promo")
            ],
            [InlineKeyboardButton("⬅️ НАЗАД", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await safe_edit_message(query, profile_text, reply_markup)

async def show_user_orders(query, user_id):
    user_orders = get_user_orders(user_id)

    if not user_orders:
        await safe_edit_message(query, "<b>📭 У тебя пока нет заказов</b>")
        return

    orders_text = "<b>📋 Твои заказы:</b>\n\n"
    for order in user_orders:
        order_number, crypto_type, amount, rub_amount, status, created_at = order
        status_emoji = "✅" if status == 'completed' else "⏳" if status == 'pending' else "❌"
        status_text = "Завершен" if status == 'completed' else "В обработке" if status == 'pending' else "Отменен"
        formatted_amount = f"{amount:.8f}".rstrip('0').rstrip('.') if '.' in f"{amount:.8f}" else f"{amount:.0f}"
        orders_text += f"{status_emoji} <b>ID:</b> {order_number}\n"
        orders_text += f"💎 <b>Крипта:</b> {formatted_amount} {crypto_type}\n"
        orders_text += f"💰 <b>Сумма:</b> {rub_amount:.0f} RUB\n"
        orders_text += f"📊 <b>Статус:</b> {status_text}\n"
        orders_text += f"➖➖➖➖➖➖➖➖➖➖\n"

    keyboard = [
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await safe_edit_message(query, orders_text, reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if admin_state.get(user_id):
        await admin_text(update, context)
        return

    if user_id in captcha_data:
        await verify_captcha(update, context)
    elif user_data.get(user_id, {}).get('waiting_for_amount_detailed'):
        await handle_amount_detailed(update, context)
    elif user_data.get(user_id, {}).get('waiting_for_wallet'):
        await handle_wallet_address(update, context)
    elif user_data.get(user_id, {}).get('waiting_for_wallet_before_confirm'):
        await handle_wallet_address(update, context)
    else:
        await start(update, context)

# ------------------ Админ-панель ------------------



async def cmd_admin(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await show_admin_main(update.message)


async def show_admin_main(msg_or_query):
    text = (
        "<b>🧑‍💼 Админ-панель HUSTLE TRADE</b>\n\n"
        f"🏦 Банк:            <code>{BANK_NAME}</code>\n"
        f"💳 Карта:           <code>{CARD_WALLET}</code>\n"
        f"🏧 СБП:             <code>{SBP_WALLET}</code>\n"
        f"👨‍💻 Оператор:       <code>{OPERATOR_USERNAME}</code>\n"
        f"💸 Комиссия:        <code>{COMMISSION_PERCENT}%</code>\n"
        f"₽ Мин. сумма:       <code>{MINIMUM_EXCHANGE_AMOUNT_RUB:,.0f} ₽</code>\n\n"
        f"<b>Курсы (RUB):</b>\n"
        f"• BTC: <code>{EXCHANGE_RATES['BTC']:,.0f}</code>\n"
        f"• LTC: <code>{EXCHANGE_RATES['LTC']:,.0f}</code>\n"
        f"• XMR: <code>{EXCHANGE_RATES['XMR']:,.0f}</code>\n"
        f"• USDT:<code>{EXCHANGE_RATES['USDT']:,.0f}</code>\n\n"
        f"🚫 Забанено:        <code>{len(banned_users)} чел.</code>\n\n"
        "Выберите действие:"
    )

    keyboard = [
        [InlineKeyboardButton("📊 Статистика",           callback_data="admin_stats")],
        [InlineKeyboardButton("📦 Ожидающие заказы",     callback_data="admin_orders")],
        [InlineKeyboardButton("💹 Изменить курсы",       callback_data="admin_edit_rates")],
        [InlineKeyboardButton("🏦 Изменить Банк",        callback_data="admin_edit_bank")],
        [InlineKeyboardButton("💳 Изменить Карту",       callback_data="admin_edit_card")],
        [InlineKeyboardButton("🏧 Изменить СБП",         callback_data="admin_edit_sbp")],
        [InlineKeyboardButton("👨‍💻 Изменить оператора",  callback_data="admin_edit_op")],
        [InlineKeyboardButton("💸 Комиссия %",           callback_data="admin_set_commission")],
        [InlineKeyboardButton("₽ Мин. сумма ₽",          callback_data="admin_set_min_rub")],
        [InlineKeyboardButton("🚫 Баны",                 callback_data="admin_bans")],
        [InlineKeyboardButton("✉️ Рассылка",             callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔄 Обновить курсы из CoinGecko", callback_data="admin_refresh_rates")],
        [InlineKeyboardButton("❌ Закрыть",               callback_data="admin_close")],
    ]
    rm = InlineKeyboardMarkup(keyboard)

    if hasattr(msg_or_query, "reply_text"):
        await msg_or_query.reply_text(text, reply_markup=rm, parse_mode="HTML")
    else:
        await msg_or_query.message.edit_text(text, reply_markup=rm, parse_mode="HTML")


async def admin_cb_handler(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if uid not in ADMIN_IDS:
        return

    print(f"[ADMIN] {query.data} от {uid}")

    data = query.data

    if data == "admin_close":
        try:
            await query.message.delete()
        except:
            await query.message.edit_text("Закрыто.")
        return

    if data == "admin_back":
        await show_admin_main(query)
        return

    # Refresh rates from CoinGecko
    if data == "admin_refresh_rates":
        await update_exchange_rates()
        await query.message.edit_text(
            f"✅ Курсы обновлены из CoinGecko:\n"
            f"• BTC: {EXCHANGE_RATES['BTC']:,.0f} ₽\n"
            f"• LTC: {EXCHANGE_RATES['LTC']:,.0f} ₽\n"
            f"• XMR: {EXCHANGE_RATES['XMR']:,.0f} ₽\n"
            f"• USDT: {EXCHANGE_RATES['USDT']:,.0f} ₽\n\n"
            "Нажмите 'Назад' для возврата в админ-панель.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]),
            parse_mode="HTML"
        )
        return

    # Статистика
    if data == "admin_stats":
        unique_count = len(stats["unique_users"])
        text = (
            "<b>📊 Статистика</b>\n\n"
            f"Запусков /start: <b>{stats['total_starts']}</b>\n"
            f"Уникальных: <b>{unique_count}</b>\n"
            f"Заказов всего: <b>{stats['total_orders']}</b>\n\n"
            "<b>По дням (последние 7):</b>\n"
        )
        dates = sorted(stats["starts_by_date"].keys(), reverse=True)[:7]
        for d in dates:
            s = stats["starts_by_date"].get(d, 0)
            o = stats["orders_by_date"].get(d, 0)
            text += f"{d}: {s} запусков, {o} заказов\n"
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # Ожидающие заказы
    if data == "admin_orders":
        orders = get_pending_orders()
        if not orders:
            text = "Нет ожидающих заказов."
        else:
            text = "<b>Ожидающие заказы:</b>\n\n"
            for o in orders[:20]:
                oid, num, uid, uname, crypto, amt, rub, wallet, method = o
                text += f"#{num} | @{uname or 'нет'} | {amt:.8f} {crypto} → {rub:.0f}₽\n"
                text += f"   wallet: <code>{wallet}</code> | метод: {method}\n\n"
        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    # Рассылка
    if data == "admin_broadcast":
        admin_state[uid] = "wait_broadcast"
        await query.message.edit_text(
            "✉️ Введите текст рассылки (поддерживается HTML):\n\n"
            "Для отмены нажмите /admin",
            parse_mode="HTML"
        )
        return

    # Баны
    if data == "admin_bans":
        if not banned_users:
            text = "Нет забаненных пользователей."
        else:
            text = "<b>Забаненные пользователи:</b>\n\n"
            for uid in list(banned_users)[:20]:
                text += f"ID: <code>{uid}</code>\n"
        keyboard = [
            [InlineKeyboardButton("🚫 Забанить", callback_data="admin_ban_user")],
            [InlineKeyboardButton("✅ Разбанить", callback_data="admin_unban_user")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")],
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if data == "admin_ban_user":
        admin_state[uid] = "wait_ban_id"
        await query.message.edit_text("Введите ID пользователя для бана:")
        return

    if data == "admin_unban_user":
        admin_state[uid] = "wait_unban_id"
        await query.message.edit_text("Введите ID пользователя для разбана:")
        return

    if data == "admin_edit_rates":
        keyboard = [
            [InlineKeyboardButton("BTC", callback_data="admin_rate_BTC")],
            [InlineKeyboardButton("LTC", callback_data="admin_rate_LTC")],
            [InlineKeyboardButton("XMR", callback_data="admin_rate_XMR")],
            [InlineKeyboardButton("USDT", callback_data="admin_rate_USDT")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="admin_back")],
        ]
        await query.message.edit_text(
            "<b>Выберите валюту для изменения курса:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    if data.startswith("admin_rate_"):
        crypto = data.split("_")[2]  # BTC, LTC, XMR, USDT
        if crypto not in EXCHANGE_RATES:
            await query.message.edit_text("Ошибка: неизвестная валюта")
            return

        admin_state[uid] = f"wait_rate_{crypto}"
        current = EXCHANGE_RATES[crypto]
        await query.message.edit_text(
            f"<b>Текущий курс {crypto}:</b> <code>{current:,.0f} ₽</code>\n\n"
            f"Введите новый курс в рублях (число):",
            parse_mode="HTML"
        )
        return

    # Изменение реквизитов и настроек
    states = {
        "admin_edit_bank": ("wait_bank", "Введите новое название банка:"),
        "admin_edit_card": ("wait_card", "Введите новый номер карты:"),
        "admin_edit_sbp":  ("wait_sbp", "Введите новый номер СБП:"),
        "admin_edit_op":   ("wait_operator", "Введите username оператора (@...):"),
        "admin_set_commission": ("wait_commission", "Новая комиссия (%):"),
        "admin_set_min_rub": ("wait_min_rub", "Новая минимальная сумма (₽):"),
    }
    if data in states:
        state, prompt = states[data]
        admin_state[uid] = state
        await query.message.edit_text(prompt, parse_mode="HTML")
        return


async def admin_text(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return

    state = admin_state.get(uid)
    if not state:
        return

    text = update.message.text.strip()
    global BANK_NAME, CARD_WALLET, SBP_WALLET, OPERATOR_USERNAME, COMMISSION_PERCENT, MINIMUM_EXCHANGE_AMOUNT_RUB

    msg = ""

    if state == "wait_bank":
        BANK_NAME = text
        msg = f"Банк → {BANK_NAME}"
        save_settings()
    elif state == "wait_card":
        CARD_WALLET = text
        msg = f"Карта → {CARD_WALLET}"
        save_settings()
    elif state == "wait_sbp":
        SBP_WALLET = text
        msg = f"СБП → {SBP_WALLET}"
        save_settings()
    elif state == "wait_operator":
        clean = text.lstrip("@")
        OPERATOR_USERNAME = f"@{clean}" if clean else "—"
        msg = f"Оператор → {OPERATOR_USERNAME}"
        save_settings()
    elif state == "wait_commission":
        try:
            COMMISSION_PERCENT = int(text)
            msg = f"Комиссия → {COMMISSION_PERCENT}%"
            save_settings()
        except:
            await update.message.reply_text("Ожидалось целое число")
            return
    elif state == "wait_min_rub":
        try:
            MINIMUM_EXCHANGE_AMOUNT_RUB = float(text)
            msg = f"Мин. сумма → {MINIMUM_EXCHANGE_AMOUNT_RUB} ₽"
            save_settings()
        except:
            await update.message.reply_text("Ожидалось число")
            return
    elif state == "wait_ban_id":
        try:
            target = int(text)
            ban_user(target)
            msg = f"Пользователь {target} забанен"
        except:
            await update.message.reply_text("Неверный ID")
            return
    elif state == "wait_unban_id":
        try:
            target = int(text)
            unban_user(target)
            msg = f"Пользователь {target} разбанен"
        except:
            await update.message.reply_text("Неверный ID")
            return
    elif state.startswith("wait_rate_"):
        crypto = state.split("_")[2]
        try:
            new_rate = float(text.replace(" ", "").replace(",", "."))
            if new_rate <= 0:
                raise ValueError("Курс должен быть положительным")

            old_rate = EXCHANGE_RATES[crypto]
            EXCHANGE_RATES[crypto] = new_rate

            # Обновляем CRYPTO_RATES
            if crypto in CRYPTO_RATES:
                CRYPTO_RATES[crypto]["rub"] = new_rate

            save_settings()

            msg = f"Курс {crypto} изменён: {old_rate:,.0f} → {new_rate:,.0f} ₽"
        except:
            await update.message.reply_text("❌ Введите корректное положительное число")
            return
    elif state == "wait_broadcast":
        # Рассылка всем пользователям (кто есть в базе)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = [row[0] for row in cursor.fetchall()]
        conn.close()

        sent = 0
        for user_id in users:
            result = await send_message_ignore_forbidden(context.bot, user_id, text=text, parse_mode="HTML")
            if result is not None:
                sent += 1

        msg = f"Рассылка отправлена {sent} из {len(users)} пользователям"
    else:
        return

    admin_state.pop(uid, None)
    await update.message.reply_text(f"✅ {msg}")
    await show_admin_main(update.message)

def main():
    if not BOT_TOKEN:
        print("Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return
    load_settings()
    init_database()

    # Update exchange rates from CoinGecko on startup
    asyncio.run(update_exchange_rates())

    application = Application.builder().token(BOT_TOKEN).build()

    # Специфический обработчик АДМИН-КОЛБЭКОВ
    application.add_handler(
        CallbackQueryHandler(
            admin_cb_handler,
            pattern="^admin_",
        )
    )

    # Основные обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", cmd_admin))

    # Общий обработчик колбэков
    application.add_handler(CallbackQueryHandler(button_handler))

    # Общий обработчик сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    asyncio.set_event_loop(asyncio.new_event_loop())
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
