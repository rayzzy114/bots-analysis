import asyncio
import logging
import aiosqlite
import random
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InlineQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os
import httpx

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

ADMIN_ID_STR = os.getenv("ADMIN_ID", "0")
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR and ADMIN_ID_STR != "" else 0

COMMISSION_PERCENT = float(os.getenv("COMMISSION_PERCENT", "20"))

# Telegram bot handles
REVIEWS_HANDLE = os.getenv("REVIEWS_HANDLE", "@my60sec_reviews")
EXCHANGE_HANDLE = os.getenv("EXCHANGE_HANDLE", "@obmen6O_bot")
HELP_HANDLE = os.getenv("HELP_HANDLE", "@help_obmen60")
NEWS_HANDLE = os.getenv("NEWS_HANDLE", "@my60sec")

COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
_RATES_TIMEOUT = httpx.Timeout(6.0, connect=2.0)
_RATES_FETCH_RETRIES = 3
_RATES_RETRY_DELAY = 0.8

CURRENCY_RATES: dict[str, float] = {}


async def fetch_crypto_rates() -> dict[str, float]:
    """Fetch crypto rates from CoinGecko API (RUB)."""
    params = {
        "ids": "bitcoin,litecoin,monero,tether",
        "vs_currencies": "rub",
    }
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=_RATES_TIMEOUT) as client:
        for attempt in range(1, _RATES_FETCH_RETRIES + 1):
            try:
                resp = await client.get(COINGECKO_API, params=params)
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
                await asyncio.sleep(_RATES_RETRY_DELAY * attempt)

    logger.warning(
        "Cannot fetch crypto rates from CoinGecko after %s attempts: %s",
        _RATES_FETCH_RETRIES,
        last_error,
    )
    return {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

DB_PATH = "bot.db"

user_selected_currency = {}
user_state = {}
user_exchange_amount = {}
user_wallet_address = {}
user_payment_method = {}
user_applications = {}
user_input_mode = {}


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS exchanges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                from_currency TEXT,
                to_currency TEXT,
                amount REAL,
                rate REAL,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promo_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                promo_code TEXT,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number INTEGER UNIQUE,
                user_id INTEGER,
                currency TEXT,
                amount REAL,
                final_amount REAL,
                crypto_amount REAL,
                wallet_address TEXT,
                payment_method TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payment_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_method TEXT UNIQUE,
                card_number TEXT,
                recipient_name TEXT,
                bank_name TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()


async def add_user(user_id: int, username: str = None, first_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        """, (user_id, username, first_name))
        await db.commit()


async def create_exchange(user_id: int, from_currency: str, to_currency: str, 
                          amount: float, rate: float, status: str = "pending"):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO exchanges (user_id, from_currency, to_currency, amount, rate, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, from_currency, to_currency, amount, rate, status))
        await db.commit()
        return cursor.lastrowid


async def create_order(user_id: int, currency: str, amount: float, final_amount: float,
                       crypto_amount: float, wallet_address: str, payment_method: str) -> int:
    import random
    from datetime import datetime, timedelta
    
    order_number = random.randint(80000, 99999)
    expires_at = datetime.now() + timedelta(minutes=30)
    
    async with aiosqlite.connect(DB_PATH) as db:
        while True:
            cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE order_number = ?", (order_number,))
            result = await cursor.fetchone()
            if result[0] == 0:
                break
            order_number = random.randint(80000, 99999)
        
        await db.execute("""
            INSERT INTO orders (order_number, user_id, currency, amount, final_amount, 
                              crypto_amount, wallet_address, payment_method, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_number, user_id, currency, amount, final_amount, 
              crypto_amount, wallet_address, payment_method, expires_at.strftime("%Y-%m-%d %H:%M:%S")))
        await db.commit()
        return order_number


async def check_promo_code(user_id: int, promo_code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT COUNT(*) FROM promo_codes 
            WHERE user_id = ? AND promo_code = ?
        """, (user_id, promo_code.upper()))
        result = await cursor.fetchone()
        return result[0] > 0


async def activate_promo_code(user_id: int, promo_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO promo_codes (user_id, promo_code)
            VALUES (?, ?)
        """, (user_id, promo_code.upper()))
        await db.commit()


async def get_payment_details(payment_method: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT card_number, recipient_name, bank_name 
            FROM payment_details 
            WHERE payment_method = ?
        """, (payment_method,))
        result = await cursor.fetchone()
        if result:
            return {
                'card_number': result[0],
                'recipient_name': result[1],
                'bank_name': result[2]
            }
        return None


async def set_payment_details(payment_method: str, card_number: str, recipient_name: str, bank_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO payment_details (payment_method, card_number, recipient_name, bank_name, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (payment_method, card_number, recipient_name, bank_name))
        await db.commit()


def get_start_keyboard() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Купить", callback_data="buy")],
        [
            InlineKeyboardButton(text="О сервисе", callback_data="about"),
            InlineKeyboardButton(text="Как совершить обмен?", callback_data="how_to_exchange")
        ],
        [
            InlineKeyboardButton(text="📄 Полезное", callback_data="useful"),
            InlineKeyboardButton(text="📖 Прочее", callback_data="other")
        ]
    ])
    return keyboard


def get_start_message() -> str:
    return f"""👋 Привет! Добро пожаловать в <u><b>60SEC</b></u> — быстрый и надёжный обменник криптовалют, где каждая сделка занимает не больше минуты.

Наш бот создан для того, чтобы ты мог обменивать крипту безопасно, удобно и без лишних действий. Здесь всё просто: выбираешь валюту, вводишь сумму, указываешь адрес кошелька — и уже через пару мгновений получаешь результат.

<b>💠 Почему <u>60SEC</u> — это удобно</b>

•⚡️ Скорость. Все операции проходят автоматически. Среднее время обмена — 60 секунд.
•💰 Выгодные курсы. Мы ежедневно обновляем котировки и подбираем для тебя лучшие предложения на рынке.
•🔒 Безопасность. Работаем через защищённые каналы, данные клиентов не сохраняются и не передаются третьим лицам.
• 🕓 Доступность 24/7. Бот работает круглосуточно — без выходных и задержек.
• 🤝 Поддержка. Если что-то пошло не так, наши специалисты всегда на связи и помогут решить любой вопрос.

<b>💎 Доступные к обмену варианты</b>

▫️ Bitcoin 
▫️ Litecoin 
▫️ USDT 
▫️ XMR

<b>✨ Всё максимально просто</b>

Выбираешь нужное направление — и бот шаг за шагом проведёт тебя через процесс обмена.
Без сложностей, без ожидания, без лишних кликов.

📩 После успешной транзакции ты моментально получаешь уведомление прямо в чате.
Если что-то пойдёт не так — система сразу подскажет, где ошибка и как её исправить.

⚖️ Курсы фиксируются на момент создания заявки — чтобы ты получил именно ту сумму, на которую рассчитывал.

💡 Минимальная сумма обмена — от 3000 рублей

⚡️ <u><b>60SEC</b></u> — это обмен без ожиданий.

<b>• Комментарии — {REVIEWS_HANDLE}
• Обмен за 60 сек — {EXCHANGE_HANDLE}
• Помощь — {HELP_HANDLE}
• Новости - {NEWS_HANDLE}</b>"""


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    await add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    await message.answer(
        get_start_message(),
        reply_markup=get_start_keyboard(),
        disable_web_page_preview=True
    )


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID and ADMIN_ID != 0:
        await message.answer("❌ У вас нет доступа к админ-панели.")
        return
    
    text = "🔧 Админ-панель\n\nВыберите действие:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Настроить реквизиты (Карты)", callback_data="admin_set_cards")],
        [InlineKeyboardButton(text="🏦 Настроить реквизиты (СБП)", callback_data="admin_set_sbp")],
        [InlineKeyboardButton(text="💱 Настроить реквизиты (Трансгран)", callback_data="admin_set_crossborder")],
        [InlineKeyboardButton(text="📋 Просмотреть реквизиты", callback_data="admin_view_details")]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@dp.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    query = inline_query.query.strip()
    user_id = inline_query.from_user.id
    
    if not query or query.startswith("rate_"):
        results = []
        currency = user_selected_currency.get(user_id, "BTC")
        rate_queries = [
            f"rate_{currency.lower()}_rub",
            f"rate_btc_rub",
            f"rate_ltc_rub",
            f"rate_xmr_rub"
        ]
        
        for rate_query in rate_queries:
            currency_name = rate_query.replace('rate_', '').replace('_rub', '').upper()
            results.append(
                InlineQueryResultArticle(
                    id=rate_query,
                    title=f"Курс {currency_name}/RUB",
                    description="Получить текущий курс",
                    input_message_content=InputTextMessageContent(
                        message_text=f"Курс {currency_name}/RUB: {CURRENCY_RATES.get(currency_name, 'N/A')} ₽"
                    )
                )
            )
        
        await inline_query.answer(results, cache_time=1)
        return
    
    try:
        import re
        numbers = re.findall(r'\d+\.?\d*', query.replace(',', '.'))
        if numbers:
            amount = float(numbers[0])
            currency = user_selected_currency.get(user_id, "BTC")
            rate = CURRENCY_RATES.get(currency, 1)
            
            if currency in ["BTC", "LTC", "XMR", "USDT"]:
                rub_amount = amount * rate
                markup_percent = COMMISSION_PERCENT / 100
                final_amount = rub_amount * (1 + markup_percent)
                result_text = f"💸 {amount} {currency} = <code>{final_amount:.2f}</code> <b>₽</b>"
            else:
                markup_percent = COMMISSION_PERCENT / 100
                amount_with_markup = amount * (1 + markup_percent)
                crypto_amount = amount_with_markup / rate
                result_text = f"💸 <code>{amount:.2f}</code> <b>₽</b> = {crypto_amount:.12f} {currency}"
            
            results = [
                InlineQueryResultArticle(
                    id="calc_result",
                    title=f"Результат расчёта",
                    description=result_text.replace('<code>', '').replace('</code>', '').replace('<b>', '').replace('</b>', ''),
                    input_message_content=InputTextMessageContent(
                        message_text=result_text,
                        parse_mode="HTML"
                    )
                )
            ]
            
            await inline_query.answer(results, cache_time=1)
    except:
        results = [
            InlineQueryResultArticle(
                id="help",
                title="Введите число для расчёта",
                description="Например: 0.01 или 1000",
                input_message_content=InputTextMessageContent(
                    message_text="Введите число для расчёта курса"
                )
            )
        ]
        await inline_query.answer(results, cache_time=1)


@dp.message()
async def handle_text_message(message: Message):
    text = message.text.strip()
    user_id = message.from_user.id
    
    if user_id in user_state and user_state[user_id].startswith("admin_setting_"):
        if user_id != ADMIN_ID and ADMIN_ID != 0:
            return
        
        lines = text.split('\n')
        if len(lines) >= 3:
            card_number = lines[0].strip()
            recipient_name = lines[1].strip()
            bank_name = lines[2].strip()
            method = user_state[user_id].replace("admin_setting_", "")
            await set_payment_details(method, card_number, recipient_name, bank_name)
            
            await message.answer(
                f"✅ Реквизиты для метода <b>{method}</b> успешно сохранены!\n\n"
                f"💳 Карта: {card_number}\n"
                f"👤 Получатель: {recipient_name}\n"
                f"🏦 Банк: {bank_name}"
            )
            del user_state[user_id]
        else:
            await message.answer("❌ Неверный формат. Отправьте данные в формате:\n1. Номер карты\n2. ФИО получателя\n3. Название банка")
        return
    
    if text.upper() == "60SEC":
        if await check_promo_code(user_id, "60SEC"):
            await message.answer("❌ Этот промокод уже активирован ❌")
        else:
            await activate_promo_code(user_id, "60SEC")
            await message.answer(
                "✅ Промокод <u><b>60SEC</b></u> успешно активирован!\n\n"
                "💰 Вы получили скидку 300 рублей на следующий обмен."
            )
        return
    
    if user_id in user_state and user_state[user_id] == "waiting_wallet":
        wallet_address = text
        currency = user_selected_currency.get(user_id, "")
        amount = user_exchange_amount.get(user_id, 0)
        user_wallet_address[user_id] = wallet_address
        payment_text = """💳 Доступные методы оплаты

Если в платёжных реквизитах отображаются иностранные банковские данные, возможны следующие причины:
1️⃣ Временная недоступность российских реквизитов (достигнут лимит).
2️⃣ Повышение минимальной суммы для выбранного метода.

📌 Рекомендуемые действия:
— 💰 Сформировать заявку на большую сумму;
— 🔄 Повторить попытку позднее (реквизиты обновляются в течение дня).

📊 Минимальные суммы (ориентиры):
• 💳 Карты — от 3 000 ₽ (в отдельных случаях 1 000–2 000 ₽)
• 🏦 СБП — от 3 000 ₽ (в отдельных случаях 1 000–2 000 ₽)
• 🌍 Трансграничные переводы (Армения, Абхазия) — от 1 000 ₽

ℹ️ При поддержке международных переводов со стороны вашего банка платёж, как правило, проходит оперативно.

⬇️ Выберите удобный метод оплаты"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Карты", callback_data="payment_cards")],
            [InlineKeyboardButton(text="🏦 СБП", callback_data="payment_sbp")],
            [InlineKeyboardButton(text="💱 Трансгран перевод", callback_data="payment_crossborder")],
            [
                InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
                InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
            ]
        ])
        
        await message.answer(payment_text, reply_markup=keyboard)
        user_state[user_id] = "waiting_payment_method"
        return
    
    if user_id in user_input_mode and user_input_mode[user_id] == "crypto_amount":
        try:
            crypto_amount = float(text.replace(',', '.').replace(' ', ''))
            
            if crypto_amount <= 0:
                await message.answer("❌ Количество криптовалюты должно быть больше нуля.")
                return
            
            currency = user_selected_currency.get(user_id, "BTC")
            rate = CURRENCY_RATES.get(currency, 1)
            amount_rub = crypto_amount * rate
            markup_percent = COMMISSION_PERCENT / 100
            amount_with_markup = amount_rub * (1 + markup_percent)
            has_promo = await check_promo_code(user_id, "60SEC")
            promo_discount = 300 if has_promo else 0
            final_amount = amount_with_markup + promo_discount
            user_exchange_amount[user_id] = amount_rub
            currency_names = {
                "BTC": "BTC",
                "LTC": "LTC",
                "XMR": "XMR",
                "USDT": "USDT"
            }
            currency_symbol = currency_names.get(currency, currency)
            message_text = f"💸 На ваш счёт поступит <code>{crypto_amount:.12f}</code> <b>{currency_symbol}</b>\n"
            message_text += f"📊 По текущему курсу это <code>{final_amount:.0f}</code> <b>₽</b>\n"
            
            if has_promo:
                message_text += f"🎁 Применён промокод <u><b>60SEC</b></u> (300₽)\n"
            
            message_text += f"\n➡️ Чтобы продолжить, введите свой кошелёк ниже:\n"
            message_text += f"🪙 <b>Введите адрес</b> ⬇️"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
                    InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
                ]
            ])
            
            await message.answer(message_text, reply_markup=keyboard)
            user_state[user_id] = "waiting_wallet"
            del user_input_mode[user_id]
            return
        except ValueError:
            await message.answer("❌ Неверный формат. Введите число, например: 0.01 или 0,01")
            return
    
    if user_id in user_selected_currency:
        try:
            amount = float(text.replace(',', '.').replace(' ', ''))
            
            if amount < 3000:
                await message.answer("❌ К сожалению, минимальная сумма платежа не может быть меньше 3000 рублей.")
            else:
                currency = user_selected_currency[user_id]
                rate = CURRENCY_RATES.get(currency, 1)
                markup_percent = COMMISSION_PERCENT / 100
                amount_with_markup = amount * (1 + markup_percent)
                has_promo = await check_promo_code(user_id, "60SEC")
                promo_discount = 300 if has_promo else 0
                final_amount = amount_with_markup + promo_discount
                crypto_amount = final_amount / rate
                currency_names = {
                    "BTC": "BTC",
                    "LTC": "LTC",
                    "XMR": "XMR",
                    "USDT": "USDT"
                }
                currency_symbol = currency_names.get(currency, currency)
                message_text = f"💸 На ваш счёт поступит <code>{crypto_amount:.12f}</code> <b>{currency_symbol}</b>\n"
                message_text += f"📊 По текущему курсу это <code>{final_amount:.0f}</code> <b>₽</b>\n"
                
                if has_promo:
                    message_text += f"🎁 Применён промокод <u><b>60SEC</b></u> (300₽)\n"
                
                message_text += f"\n➡️ Чтобы продолжить, введите свой кошелёк ниже:\n"
                message_text += f"🪙 <b>Введите адрес</b> ⬇️"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
                        InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
                    ]
                ])
                
                await message.answer(message_text, reply_markup=keyboard)
                user_state[user_id] = "waiting_wallet"
                user_exchange_amount[user_id] = amount
        except ValueError:
            pass


@dp.callback_query(F.data == "buy")
async def callback_buy(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in user_selected_currency:
        del user_selected_currency[user_id]
    if user_id in user_state:
        del user_state[user_id]
    if user_id in user_exchange_amount:
        del user_exchange_amount[user_id]
    if user_id in user_wallet_address:
        del user_wallet_address[user_id]
    if user_id in user_payment_method:
        del user_payment_method[user_id]
    if user_id in user_applications:
        del user_applications[user_id]
    if user_id in user_input_mode:
        del user_input_mode[user_id]
    text = "🌍Какую крипту хотите приобрести?"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Bitcoin (BTC)", callback_data="currency_btc")],
        [InlineKeyboardButton(text="🔶 Monero (XMR)", callback_data="currency_xmr")],
        [InlineKeyboardButton(text="🪙 Litecoin (LTC)", callback_data="currency_ltc")],
        [
            InlineKeyboardButton(text="🎟️ Промокоды", callback_data="promo_codes"),
            InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "about")
async def callback_about(callback: CallbackQuery):
    await callback.answer()
    text = """<b>💠 <u>60SEC</u> — обмен, который работает со скоростью доверия</b>

Мы создаём не просто обменник, а пространство, где каждая сделка проходит легко, быстро и с чувством уверенности.
Наш принцип прост: минимум ожиданий — максимум надёжности.

<b>⚡️ Наши преимущества</b>

🔵 Обмен за 60 секунд
Мгновенные операции без задержек — от создания заявки до поступления средств.

❤️ Низкая комиссия
Мы удерживаем комиссии на минимальном уровне, чтобы ты получал больше при каждом обмене.

🛡 Безопасность и анонимность
Никаких лишних данных. Никаких утечек. Все операции проходят через защищённые каналы с полной конфиденциальностью.

⚙️ Поддержка 24/7
Живые операторы всегда на связи — отвечаем быстро, решаем чётко, без шаблонов.

💬 Реальные отзывы
Мы ценим доверие пользователей — у нас только настоящие истории клиентов, подтверждённые фактами и временем.

🟢 Новостной канал
Держим в курсе актуальных курсов, изменений рынка и технических обновлений — всё, что помогает тебе быть на шаг впереди.

<b>🤝 Мы всегда на связи</b>

<b>❤️ Обрабатываем 100% обращений — без исключений.</b>
<b>💝 Рассматриваем ошибки и спорные ситуации в течение 48 часов после совершения обмена.</b>
<b>🔍 Контролируем каждый этап сделки — от запроса до финального подтверждения транзакции.</b>

<b>💎 О нас</b>

<u><b>60SEC</b></u> — это сервис безопасного и продуманного обмена криптоактивов.
Мы объединяем скорость технологий и человеческое внимание к деталям, чтобы каждый пользователь ощущал не просто удобство, а уверенность в каждой секунде сделки.

<b>Наша цель — сделать криптообмен настолько простым, что доверять станет естественно.</b>

🚀 <b><u>60SEC</u> — быстро. честно. безопасно.</b>"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "how_to_exchange")
async def callback_how_to_exchange(callback: CallbackQuery):
    await callback.answer()
    text = """Как сделать обмен в <u>60SEC</u>

<b>🚀 Покупка криптовалюты</b>

1️⃣ В открывшемся меню нажмите «Купить».
2️⃣ Выберите нужную валюту: BTC, LTC, XMR — и нажмите на соответствующую кнопку.
3️⃣ В новом окне выберите способ оплаты — «КАРТОЙ/СБП».
4️⃣ После этого появится окно с текущим курсом. Проверьте его перед покупкой.
5️⃣ Введите нужное количество монет или рублей.
6️⃣ Бот попросит указать адрес получения — введите реквизиты своего кошелька.
7️⃣ После этого появится окно для оплаты. Совершите платёж и нажмите кнопку «ОПЛАТИЛ», прикрепите «PDF-чек».
8️⃣ Ожидайте зачисления средств на указанный вами кошелёк.

💡 Обычно перевод занимает от 5 до 40 минут, в зависимости от загруженности блокчейна

<b>⚙️ Продажа криптовалюты</b>

1️⃣ Нажмите «Продать».
2️⃣ Выберите валюту и сумму, которую хотите продать.
3️⃣ Укажите реквизиты карты или счёта для получения средств.
4️⃣ Подтвердите и отправьте транзакцию.

⏰ Зачисление средств занимает от 5 минут до 2 часов, в зависимости от выбранного банка и сети.

✨ Всё максимально просто, безопасно и прозрачно.

Бот <u>60SEC</u> сам проведёт вас через каждый шаг, уведомит о статусе и сообщит, когда средства будут зачислены.

🔒 <u>60SEC</u> — обмен без ожиданий."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "useful")
async def callback_useful(callback: CallbackQuery):
    await callback.answer()
    text = f"""💬 Вопрос–Ответ: как безопасно купить криптовалюту с <u>60SEC</u>

❓ Как проходит покупка криптовалюты?

Вы переводите деньги на карту, которую выдаёт обменник <u>60SEC</u> в рамках вашей сделки. После подтверждения оплаты бот автоматически отправит криптовалюту на ваш кошелёк.

💡 Просто следуйте пошаговым инструкциям — система всё подскажет.

❓ Это безопасно?

Да. Мы используем только проверенные реквизиты и надёжные каналы связи.
⚠️ Будьте внимательны: в сети могут встречаться поддельные сайты и фейковые аккаунты, которые копируют имена и интерфейсы. Всегда проверяйте, что вы находитесь в официальном боте <u>60SEC</u> {EXCHANGE_HANDLE}.

❓ Куда переводить деньги?

Только на карту, которую бот или оператор выдал для текущей сделки.

🚫 Не используйте реквизиты из старых обменов или полученные от сторонних контактов.

❓ Можно ли вернуть деньги, если ошибся с переводом?

Если платёж уже отправлен, банк не сможет отменить операцию.
Пожалуйста, всегда проверяйте реквизиты дважды перед подтверждением перевода.
🕐 Внимательность — ваша лучшая защита.

<b>💡 Советы от <u>60SEC</u></b>

✅ Проверяйте реквизиты перед каждой оплатой.
🚫 Не отправляйте средства, если реквизиты пришли не от нашего бота.
🔒 Никогда не сообщайте пароли, коды и данные карт.
📸 Сохраняйте подтверждение перевода до завершения обмена.
🕐 Не торопитесь — проверьте всё ещё раз перед нажатием «Отправить».
💬 При любых сомнениях сразу пишите в поддержку — мы поможем.

<b>🛡 Базовые правила безопасности в криптовалюте</b>

❌ Не передавайте никому свои seed-фразы, приватные ключи или пароли.
🔍 Всегда сверяйте адрес кошелька — иногда злоумышленники подменяют его.
💳 Переводите деньги только на реквизиты от <u>60SEC</u> {EXCHANGE_HANDLE}.
📲 Используйте официальные кошельки и приложения для хранения криптовалюты.
🧾 Храните скриншоты и чеки до полного завершения сделки.

💠 <u>60SEC</u> — быстро, безопасно, надёжно.
Мы всегда рядом, чтобы ваш обмен проходил спокойно и уверенно 💙"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "other")
async def callback_other(callback: CallbackQuery):
    await callback.answer()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📞 Связь с оператором", callback_data="contact_operator"),
            InlineKeyboardButton(text="🎟️ Промокоды", callback_data="promo_codes")
        ],
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)


@dp.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in user_selected_currency:
        del user_selected_currency[user_id]
    if user_id in user_state:
        del user_state[user_id]
    if user_id in user_exchange_amount:
        del user_exchange_amount[user_id]
    if user_id in user_wallet_address:
        del user_wallet_address[user_id]
    if user_id in user_payment_method:
        del user_payment_method[user_id]
    if user_id in user_applications:
        del user_applications[user_id]
    if user_id in user_input_mode:
        del user_input_mode[user_id]
    await callback.message.edit_text(
        get_start_message(),
        reply_markup=get_start_keyboard()
    )


@dp.callback_query(F.data.startswith("currency_"))
async def callback_currency(callback: CallbackQuery):
    await callback.answer()
    currency = callback.data.split("_")[1].upper()
    user_id = callback.from_user.id
    user_selected_currency[user_id] = currency
    currency_button_text = {
        "BTC": "В BTC",
        "LTC": "В LTC",
        "XMR": "В XMR",
        "USDT": "В USDT"
    }
    currency_text = currency_button_text.get(currency, f"В {currency}")
    
    text = "💸Введите желаемую сумму в рублях"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Калькулятор", switch_inline_query_current_chat="rate_"),
            InlineKeyboardButton(text=currency_text, callback_data=f"convert_{currency.lower()}")
        ],
        [
            InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
            InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("convert_"))
async def callback_convert_currency(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    currency = callback.data.split("_")[1].upper()
    user_selected_currency[user_id] = currency
    user_input_mode[user_id] = "crypto_amount"
    currency_names = {
        "BTC": "ВТС",
        "LTC": "LTC",
        "XMR": "XMR",
        "USDT": "USDT"
    }
    currency_display = currency_names.get(currency, currency)
    
    text = f"""💸 Введите желаемое количество {currency_display}
⚡ Пример: 0.01 или 0,01"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Калькулятор", switch_inline_query_current_chat="rate_"),
            InlineKeyboardButton(text="В рублях", callback_data=f"currency_{currency.lower()}")
        ],
        [
            InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
            InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("payment_"))
async def callback_payment_method(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    payment_methods = {
        "payment_cards": "Карты",
        "payment_sbp": "СБП",
        "payment_crossborder": "Трансгран перевод"
    }
    payment_method = payment_methods.get(callback.data, "Карты")
    currency = user_selected_currency.get(user_id, "BTC")
    amount = user_exchange_amount.get(user_id, 0)
    wallet_address = user_wallet_address.get(user_id, "")
    markup_percent = COMMISSION_PERCENT / 100
    amount_with_markup = amount * (1 + markup_percent)
    has_promo = await check_promo_code(user_id, "60SEC")
    promo_discount = 300 if has_promo else 0
    final_amount = amount_with_markup + promo_discount
    rate = CURRENCY_RATES.get(currency, 1)
    crypto_amount = final_amount / rate
    currency_names = {
        "BTC": "BTC",
        "LTC": "LTC",
        "XMR": "XMR",
        "USDT": "USDT"
    }
    currency_symbol = currency_names.get(currency, currency)
    payment_method_emoji = {
        "Карты": "💳",
        "СБП": "🏦",
        "Трансгран перевод": "💱"
    }
    method_emoji = payment_method_emoji.get(payment_method, "")
    text = f"""💼 Детали вашей сделки

💰 Сумма: <u><code>{final_amount:.0f}</code></u> <b>Р</b>
🪙 Метод оплаты: {method_emoji} {payment_method}
📥 Адрес для зачисления: {wallet_address}
💰 Сумма зачисления: <code>{crypto_amount:.12f}</code> <b>{currency_symbol}</b>

⏳ Реквизиты будут отправлены в течение 10 минут
⚡ После оплаты перевод будет отправлен в течение 5 минут"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать обмен", callback_data="start_exchange")],
        [
            InlineKeyboardButton(text="🔙 Вернуться", callback_data="buy"),
            InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")
        ]
    ])
    user_payment_method[user_id] = payment_method
    await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "start_exchange")
async def callback_start_exchange(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    currency = user_selected_currency.get(user_id, "BTC")
    amount = user_exchange_amount.get(user_id, 0)
    wallet_address = user_wallet_address.get(user_id, "")
    payment_method = user_payment_method.get(user_id, "Карты")
    markup_percent = COMMISSION_PERCENT / 100
    amount_with_markup = amount * (1 + markup_percent)
    has_promo = await check_promo_code(user_id, "60SEC")
    promo_discount = 300 if has_promo else 0
    final_amount = amount_with_markup + promo_discount
    rate = CURRENCY_RATES.get(currency, 1)
    crypto_amount = final_amount / rate
    currency_names = {
        "BTC": "BTC",
        "LTC": "LTC",
        "XMR": "XMR",
        "USDT": "USDT"
    }
    currency_symbol = currency_names.get(currency, currency)
    application_number = random.randint(10000, 99999)
    valid_until = datetime.now() + timedelta(minutes=30)
    valid_until_str = valid_until.strftime("%H:%M %d.%m")
    application_text = f"""📄 Ваша заявка №{application_number}

⏰ Действительна до {valid_until_str} (30 мин)

💰 Сумма к оплате: <u><code>{final_amount:.0f}</code> <b>Р</b></u>
Получаете: <code>{crypto_amount:.12f}</code> <b>{currency_symbol}</b>

💼 Адрес зачисления: {wallet_address}

⏳🤖 Реквизиты формируются — это займёт немного времени. Как только они будут готовы, бот пришлёт уведомление автоматически.

💎 Если нужна помощь — напишите оператору: {HELP_HANDLE}"""
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_application_{application_number}")]
    ])
    await callback.message.answer(application_text, reply_markup=cancel_keyboard, disable_web_page_preview=True)
    instructions_text = """⚠️ <b>Перед оплатой внимательно ознакомьтесь</b>

🔶 Оплачивайте строго тем способом, который был выбран при создании заявки.
Переводы другими методами не обрабатываются системой и не могут быть засчитаны.

🔶 Система работает автоматически.
Если указать неверную сумму, реквизиты или банк — платёж не будет определён и средства не смогут зачислиться.

💡 Пожалуйста, проверяйте все данные перед отправкой перевода — это поможет избежать задержек и ошибок."""
    await callback.message.answer(instructions_text)
    user_applications[user_id] = {
        'number': application_number,
        'amount': final_amount,
        'currency': currency,
        'crypto_amount': crypto_amount,
        'wallet': wallet_address,
        'payment_method': payment_method,
        'valid_until': valid_until
    }
    asyncio.create_task(send_payment_details_after_delay(user_id, application_number, final_amount, payment_method))


async def send_payment_details_after_delay(user_id: int, application_number: int, final_amount: float, payment_method: str):
    await asyncio.sleep(10)
    payment_details = await get_payment_details(payment_method)
    if not payment_details:
        await bot.send_message(
            user_id,
            f"❌ Реквизиты для оплаты ещё не настроены администратором. Обратитесь в поддержку: {HELP_HANDLE}",
            disable_web_page_preview=True
        )
        return
    payment_text = f"""<b>💳 Реквизиты для оплаты заявки №{application_number}</b>

⏰ <b>ОБЯЗАТЕЛЬНО ОПЛАТИТЕ ЗАЯВКУ В ТЕЧЕНИЕ 10 МИНУТ!</b>
<b>ЕСЛИ НЕ УСПЕВАЕТЕ ОПЛАТИТЬ, ТО СОЗДАЙТЕ НОВУЮ ЗАЯВКУ /start</b>

⚡️ Важно:
• Отправьте <u>точную сумму</u> — это нужно, чтобы система автоматически распознала перевод.
• После оплаты ничего нажимать не нужно — бот сам обработает платёж.
• Проверка и зачисление могут занять до 10 минут.

──────────────────────
💳 Карта: <code>{payment_details['card_number']}</code>
👤 Получатель: <code>{payment_details['recipient_name']}</code>
🏦 Банк: <code>{payment_details['bank_name']}</code>
💰 Сумма: <u>{final_amount:.2f} ₽</u>

──────────────────────"""
    
    await bot.send_message(user_id, payment_text)


@dp.callback_query(F.data.startswith("cancel_application_"))
async def callback_cancel_application(callback: CallbackQuery):
    await callback.answer("Заявка отменена", show_alert=True)
    user_id = callback.from_user.id
    if user_id in user_applications:
        del user_applications[user_id]
    if user_id in user_selected_currency:
        del user_selected_currency[user_id]
    if user_id in user_state:
        del user_state[user_id]
    if user_id in user_exchange_amount:
        del user_exchange_amount[user_id]
    if user_id in user_wallet_address:
        del user_wallet_address[user_id]
    if user_id in user_payment_method:
        del user_payment_method[user_id]
    if user_id in user_input_mode:
        del user_input_mode[user_id]
    await callback.message.edit_text(
        get_start_message(),
        reply_markup=get_start_keyboard()
    )


@dp.callback_query(F.data.startswith("admin_"))
async def callback_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != ADMIN_ID and ADMIN_ID != 0:
        await callback.answer("❌ У вас нет доступа", show_alert=True)
        return
    
    await callback.answer()
    if callback.data == "admin_view_details":
        methods = ["Карты", "СБП", "Трансгран перевод"]
        details_text = "📋 Текущие реквизиты:\n\n"
        
        for method in methods:
            details = await get_payment_details(method)
            if details:
                details_text += f"<b>{method}:</b>\n"
                details_text += f"💳 Карта: {details['card_number']}\n"
                details_text += f"👤 Получатель: {details['recipient_name']}\n"
                details_text += f"🏦 Банк: {details['bank_name']}\n\n"
            else:
                details_text += f"<b>{method}:</b> не настроено\n\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        await callback.message.edit_text(details_text, reply_markup=keyboard)
    elif callback.data.startswith("admin_set_"):
        method_map = {
            "admin_set_cards": "Карты",
            "admin_set_sbp": "СБП",
            "admin_set_crossborder": "Трансгран перевод"
        }
        method = method_map.get(callback.data, "Карты")
        
        text = f"⚙️ Настройка реквизитов для метода: <b>{method}</b>\n\n"
        text += "Отправьте данные в следующем формате (каждое значение с новой строки):\n"
        text += "1. Номер карты\n"
        text += "2. ФИО получателя\n"
        text += "3. Название банка\n\n"
        text += "Пример:\n"
        text += "2200700730760997\n"
        text += "Рамазанов Шахбаз Романович\n"
        text += "Т-Банк (Тинькофф)"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        user_state[user_id] = f"admin_setting_{method}"
    elif callback.data == "admin_back":
        text = "🔧 Админ-панель\n\nВыберите действие:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Настроить реквизиты (Карты)", callback_data="admin_set_cards")],
            [InlineKeyboardButton(text="🏦 Настроить реквизиты (СБП)", callback_data="admin_set_sbp")],
            [InlineKeyboardButton(text="💱 Настроить реквизиты (Трансгран)", callback_data="admin_set_crossborder")],
            [InlineKeyboardButton(text="📋 Просмотреть реквизиты", callback_data="admin_view_details")]
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)


@dp.callback_query(F.data == "contact_operator")
async def callback_contact_operator(callback: CallbackQuery):
    await callback.answer()
    text = f"""📞 Связь с оператором

Для связи с оператором обращайтесь в поддержку:
• Помощь — {HELP_HANDLE}

Наши специалисты всегда на связи и помогут решить любой вопрос."""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)


@dp.callback_query(F.data == "promo_codes")
async def callback_promo_codes(callback: CallbackQuery):
    await callback.answer()
    text = """✨ Ваши активные промокоды ✨

💌 <u><b>60SEC</b></u> — скидка 300Р

🚀 Чтобы применить новый промокод, просто отправьте его в чат и получите бонус мгновенно!"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)


async def main():
    global CURRENCY_RATES
    await init_db()
    logger.info("База данных инициализирована")

    # Fetch crypto rates from CoinGecko
    CURRENCY_RATES = await fetch_crypto_rates()
    if CURRENCY_RATES:
        logger.info("Курсы криптовалют загружены: BTC=%.2f, LTC=%.2f, XMR=%.2f, USDT=%.2f",
                    CURRENCY_RATES.get("BTC", 0), CURRENCY_RATES.get("LTC", 0),
                    CURRENCY_RATES.get("XMR", 0), CURRENCY_RATES.get("USDT", 0))
    else:
        logger.warning("Не удалось загрузить курсы криптовалют, используются значения по умолчанию")

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

