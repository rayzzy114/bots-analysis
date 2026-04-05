import asyncio
import os
import time
import json
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv
from utils.env_writer import update_env_var, read_env_var
from config import reload_env
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CONTACT_24_7_URL = os.getenv("CONTACT_24_7_URL", "").strip()
CHANNEL_INFO_URL = os.getenv("CHANNEL_INFO_URL", "").strip()
ADMIN_CHAT_URL = os.getenv("ADMIN_CHAT_URL", "").strip()
FRESH_REVIEWS_URL = os.getenv("FRESH_REVIEWS_URL", "").strip()
NEW_REVIEWS_URL = os.getenv("NEW_REVIEWS_URL", "").strip()
ROULETTE_URL = os.getenv("ROULETTE_URL", "").strip()
OPERATOR_URL = os.getenv("OPERATOR_URL", "").strip()
PARTNERSHIP_URL = os.getenv("PARTNERSHIP_URL", "").strip()
WEEKLY_ROULETTE_URL = os.getenv("WEEKLY_ROULETTE_URL", "").strip()
BTC_RATE = float(os.getenv("BTC_RATE", "8286200"))
LTC_RATE = float(os.getenv("LTC_RATE", "8286"))
USDT_RATE = float(os.getenv("USDT_RATE", "100"))
XMR_RATE = float(os.getenv("XMR_RATE", "165720"))
BTC_RATE_SELL = float(os.getenv("BTC_RATE_SELL", "8286200"))
LTC_RATE_SELL = float(os.getenv("LTC_RATE_SELL", "8286"))
USDT_RATE_SELL = float(os.getenv("USDT_RATE_SELL", "100"))
XMR_RATE_SELL = float(os.getenv("XMR_RATE_SELL", "165720"))
BTC_RATE_USD = float(os.getenv("BTC_RATE_USD", "45000.0"))
BTC_RATE_RUB = float(os.getenv("BTC_RATE_RUB", "4500000.0"))
COMMISSION_PERCENT = int(os.getenv("COMMISSION_PERCENT", "30"))
OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "BULBA_BTC_2").strip()
ADMIN_ID_STR = os.getenv("ADMIN_ID", "")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_ID_STR.split(",") if admin_id.strip().isdigit()] if ADMIN_ID_STR else []


async def get_cbr_usd_rate() -> float:
    """Fetch USD/RUB rate from Central Bank of Russia."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = json.loads(await response.text())
                    return float(data["Valute"]["USD"]["Value"])
    except Exception as e:
        logger.error(f"CBR error: {e}")
    return 90.0


async def get_btc_rates() -> tuple:
    """Fetch BTC rates from Binance, fallback to CoinGecko, then to env defaults."""
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
        logger.error(f"Binance BTC error: {e}")
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
        logger.error(f"CoinGecko BTC error: {e}")
    return (BTC_RATE_USD, BTC_RATE_RUB)


async def get_ltc_rate_coingecko() -> tuple:
    """Fetch LTC rates from CoinGecko API. Returns (usd_price, rub_price)."""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd,rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    ltc = data.get("litecoin", {})
                    usd = float(ltc.get("usd", 0))
                    rub = float(ltc.get("rub", 0))
                    if usd > 0 and rub > 0:
                        logger.info(f"CoinGecko LTC: ${usd}, ₽{rub:.0f}")
                        return (usd, rub)
    except Exception as e:
        logger.error(f"CoinGecko LTC error: {e}")
    # Fallback to .env values
    return (LTC_RATE, LTC_RATE * 90)


async def get_xmr_rate_coingecko() -> tuple:
    """Fetch XMR rate from CoinGecko API. Returns (usd_price, rub_price)."""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd,rub"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    xmr = data.get("monero", {})
                    usd = float(xmr.get("usd", 0))
                    rub = float(xmr.get("rub", 0))
                    if usd > 0 and rub > 0:
                        logger.info(f"CoinGecko XMR: ${usd}, ₽{rub:.0f}")
                        return (usd, rub)
    except Exception as e:
        logger.error(f"CoinGecko XMR error: {e}")
    # Fallback to .env values
    return (XMR_RATE, XMR_RATE * 90)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
PAYMENT_DETAILS_FILE = "payment_details.json"
def load_payment_details():
    if os.path.exists(PAYMENT_DETAILS_FILE):
        try:
            with open(PAYMENT_DETAILS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}
def save_payment_details(data):
    with open(PAYMENT_DETAILS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def get_payment_details(crypto: str, country: str = "russia"):
    details = load_payment_details()
    crypto_data = details.get(crypto, {})
    if country == "belarus":
        return {
            "bank": crypto_data.get("bank_bel", "Альфа-Банк 2200 1536 1378 7010"),
            "sbp_phone": crypto_data.get("sbp_phone_bel", ""),
            "wallet_address": crypto_data.get("wallet_address", "bc1qnv29qqq46vazssl4vlm4drp3scyay96qxnfakx")
        }
    else:
        return {
            "bank": crypto_data.get("bank", "Альфа-Банк 2200 1536 1378 7010"),
            "sbp_phone": crypto_data.get("sbp_phone", ""),
            "wallet_address": crypto_data.get("wallet_address", "bc1qnv29qqq46vazssl4vlm4drp3scyay96qxnfakx")
        }
class AdminState(StatesGroup):
    waiting_crypto = State()
    waiting_type = State()
    waiting_country = State()
    waiting_bank_name = State()
    waiting_bank = State()
    waiting_sbp_phone = State()
    waiting_crypto_wallet = State()
    waiting_commission = State()
    waiting_links_field = State()
    waiting_link_value = State()
user_selected_currency = {}
user_transaction_data = {}
user_order_data = {}
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
async def get_bot_username():
    bot_info = await bot.get_me()
    return bot_info.username
class UserPanelCallback(CallbackData, prefix="user_panel"):
    action: str

class LinksCallback(CallbackData, prefix="links"):
    action: str
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Купить"), KeyboardButton(text="⚡ Продать")],
            [KeyboardButton(text="👾 Контакты"), KeyboardButton(text="🎲 Бонусы")],
            [KeyboardButton(text="⚙️ Панель пользователя")]
        ],
        resize_keyboard=True
    )
def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="BTC", callback_data=UserPanelCallback(action="admin_set_BTC").pack())],
        [InlineKeyboardButton(text="LTC", callback_data=UserPanelCallback(action="admin_set_LTC").pack())],
        [InlineKeyboardButton(text="USDT", callback_data=UserPanelCallback(action="admin_set_USDT").pack())],
        [InlineKeyboardButton(text="XMR", callback_data=UserPanelCallback(action="admin_set_XMR").pack())],
        [InlineKeyboardButton(text="💰 Commission %", callback_data=UserPanelCallback(action="admin_set_commission").pack())],
        [InlineKeyboardButton(text="🔗 Ссылки", callback_data=UserPanelCallback(action="admin_links").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back").pack())]
    ])
    return keyboard
def get_admin_type_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Настроить реквизиты карты", callback_data=UserPanelCallback(action="admin_type_card").pack())],
        [InlineKeyboardButton(text="₿ Настроить адрес криптокошелька", callback_data=UserPanelCallback(action="admin_type_crypto").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_crypto").pack())]
    ])
    return keyboard
def get_admin_country_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data=UserPanelCallback(action="admin_country_russia").pack())],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data=UserPanelCallback(action="admin_country_belarus").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_type").pack())]
    ])
    return keyboard

def get_admin_links_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Rates (BTC,LTC,USDT,XMR)", callback_data=LinksCallback(action="edit_rates").pack())],
        [InlineKeyboardButton(text="💵 Sell BTC", callback_data=LinksCallback(action="edit_sell_btc").pack())],
        [InlineKeyboardButton(text="📢 News Channel", callback_data=LinksCallback(action="edit_news_channel").pack())],
        [InlineKeyboardButton(text="👷 Operator", callback_data=LinksCallback(action="edit_operator").pack())],
        [InlineKeyboardButton(text="👷 Operator2", callback_data=LinksCallback(action="edit_operator2").pack())],
        [InlineKeyboardButton(text="👷 Operator3", callback_data=LinksCallback(action="edit_operator3").pack())],
        [InlineKeyboardButton(text="📱 Work Operator", callback_data=LinksCallback(action="edit_work_operator").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=LinksCallback(action="back").pack())]
    ])
    return keyboard
@dp.message(Command("admin"))
async def admin_command(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
 
    await state.set_state(AdminState.waiting_crypto)
    sent_message = await message.answer("Выберите криптовалюту для настройки реквизитов:", reply_markup=get_admin_keyboard())
    await state.update_data(admin_message_id=sent_message.message_id)
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = """BULBA_BTC_BOT — криптообмен 24/7
BTC / USDT / ETH / LTC / TRX
RUB 🇷🇺 и BYN 🇧🇾 — поддержка
— Автоматический обмен без задержек
— Курс без скрытых комиссий
— Продажа и покупка напрямую на вашу карту
— Поддержка операторов в ручном режиме
— Программа лояльности для постоянных клиентов
— Реферальная система"""
    photo = FSInputFile("start.png")
    menu_text = """🚜Добро пожаловать в сервис BULBA_BTC_BOT
После каждой операции у вас есть шанс получить бонус 🎁
🔒 Сервис не поддерживает подозрительные или незаконные транзакции.
🔞 Только для пользователей старше 18 лет.
✅ Выберите нужную функцию в меню ниже, чтобы начать работу."""
    try:
        await message.answer_photo(photo, caption=welcome_text)
        await asyncio.sleep(0.5)
        await message.answer(menu_text, reply_markup=get_main_keyboard())
    except TelegramForbiddenError:
        logger.warning("Skipping /start for blocked user_id=%s", message.from_user.id if message.from_user else None)
        return
@dp.callback_query(UserPanelCallback.filter())
async def user_panel_handler(callback: types.CallbackQuery, callback_data: UserPanelCallback, state: FSMContext):
    if callback_data.action == "panel":
        text = "Ваш кабинет."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 История операций", callback_data=UserPanelCallback(action="history").pack())],
            [InlineKeyboardButton(text="🏆 Реферальная программа", callback_data=UserPanelCallback(action="referral").pack())],
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
        ])
        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    elif callback_data.action == "back":
        user_id = callback.from_user.id
     
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            operation_type = transaction.get("operation_type", "")
            country = transaction.get("country", "")
            current_step = transaction.get("current_step", "")
         
            if current_step == "payment_method_selected":
                if "crypto_amount_str" in transaction and "rub_amount" in transaction:
                    currency = transaction["currency"]
                    crypto_amount_str = transaction.get("crypto_amount_str", "")
                    rub_amount = transaction["rub_amount"]
                    country = transaction.get("country", "russia")
                 
                    if country == "belarus":
                        amount_display = round(rub_amount * 0.036)
                        currency_display = "бел.рублей"
                    else:
                        amount_display = rub_amount
                        currency_display = "₽"
                 
                    if operation_type == "sell":
                        text = f"""- Вам будет зачислено: **{amount_display} {currency_display}**
- Вам необходимо отправить: **{crypto_amount_str} {currency['symbol']}**
🎫 У вас используется промокод: **NEWUSER30**, скидка в размере 25% !"""
                    else:
                        text = f"""- Вам будет зачислено: **{crypto_amount_str} {currency['symbol']}**
- Вам необходимо оплатить: **{amount_display} {currency_display}**
🎫 У вас используется промокод: **NEWUSER30**, скидка в размере 25% !"""
                 
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Использовать промокод", callback_data=UserPanelCallback(action="payment_next").pack())],
                        [InlineKeyboardButton(text="Не использовать промокод", callback_data=UserPanelCallback(action="payment_next").pack())],
                        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
                    ])
                    try:
                        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
                    except:
                        await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
                    transaction["current_step"] = "amount_entered"
                    await callback.answer()
                    return
            elif current_step == "crypto_selected" or current_step == "amount_entered":
                if operation_type == "buy":
                    text = "🧩Какую криптовалюту хотите приобрести?"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Bitcoin - BTC", callback_data=UserPanelCallback(action="buy_btc").pack())],
                        [InlineKeyboardButton(text="Litecoin - LTC", callback_data=UserPanelCallback(action="buy_ltc").pack())],
                        [InlineKeyboardButton(text="USDT - TRC20", callback_data=UserPanelCallback(action="buy_usdt").pack())],
                        [InlineKeyboardButton(text="Monero - XMR", callback_data=UserPanelCallback(action="buy_xmr").pack())],
                        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back_to_country").pack())]
                    ])
                else:
                    text = "🧩Какую криптовалюту хотите продать?"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Bitcoin - BTC", callback_data=UserPanelCallback(action="sell_btc").pack())],
                        [InlineKeyboardButton(text="Litecoin - LTC", callback_data=UserPanelCallback(action="sell_ltc").pack())],
                        [InlineKeyboardButton(text="USDT - TRC20", callback_data=UserPanelCallback(action="sell_usdt").pack())],
                        [InlineKeyboardButton(text="Monero - XMR", callback_data=UserPanelCallback(action="sell_xmr").pack())],
                        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back_to_country").pack())]
                    ])
                try:
                    await callback.message.edit_text(text, reply_markup=keyboard)
                except:
                    await callback.message.answer(text, reply_markup=keyboard)
                transaction["current_step"] = "country_selected"
                await callback.answer()
                return
     
        menu_text = """🚜Добро пожаловать в сервис BULBA_BTC_BOT
После каждой операции у вас есть шанс получить бонус 🎁
🔒 Сервис не поддерживает подозрительные или незаконные транзакции.
🔞 Только для пользователей старше 18 лет.
✅ Выберите нужную функцию в меню ниже, чтобы начать работу."""
        await callback.message.answer(menu_text, reply_markup=get_main_keyboard())
        await callback.answer()
    elif callback_data.action == "back_to_country":
        user_id = callback.from_user.id
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            operation_type = transaction.get("operation_type", "buy")
         
            text = "Выберите свою страну."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🇷🇺 Россия", callback_data=UserPanelCallback(action="buy_russia" if operation_type == "buy" else "sell_russia").pack())],
                [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data=UserPanelCallback(action="buy_belarus" if operation_type == "buy" else "sell_belarus").pack())],
                [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
            ])
            try:
                await callback.message.edit_text(text, reply_markup=keyboard)
            except:
                await callback.message.answer(text, reply_markup=keyboard)
            await callback.answer()
    elif callback_data.action == "history":
        await callback.answer("Вы не совершили ни одной сделки.")
    elif callback_data.action == "referral":
        bot_username = await get_bot_username()
        user_id = callback.from_user.id
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        referral_text = f"""🤑Реферальная программа.
Приглашайте друзей и получайте процент от каждой сделки Вашего друга.
✅Данные средства Вы можете потратить как скидку во время обмена или же вывести удобным Вам способом.
🔗Ваша реферальная ссылка:
{referral_link}
💰Ваш текущий баланс: 0₽ ~ 0 бел.рублей
👥Количество рефералов: 0, активных 0
🤝Всего получено от рефералов: 0
🎲Количество проведенных сделок:0
Ваш ранг: 👶
Ваша скидка: 0.0%"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пригласить друга", switch_inline_query=referral_link)],
            [InlineKeyboardButton(text="Вывод средств", callback_data=UserPanelCallback(action="withdraw").pack())],
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="panel").pack())]
        ])
        await callback.message.answer(referral_text, reply_markup=keyboard)
        await callback.answer()
    elif callback_data.action == "withdraw":
        await callback.message.answer("Минимальная сумма для вывода средств равна 500₽")
        await callback.answer()
    elif callback_data.action == "buy_russia" or callback_data.action == "buy_belarus":
        country = "russia" if callback_data.action == "buy_russia" else "belarus"
        user_id = callback.from_user.id
        if user_id not in user_transaction_data:
            user_transaction_data[user_id] = {}
        user_transaction_data[user_id]["country"] = country
        user_transaction_data[user_id]["operation_type"] = "buy"
        user_transaction_data[user_id]["current_step"] = "country_selected"
        text = "🧩Какую криптовалюту хотите приобрести?"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bitcoin - BTC", callback_data=UserPanelCallback(action="buy_btc").pack())],
            [InlineKeyboardButton(text="Litecoin - LTC", callback_data=UserPanelCallback(action="buy_ltc").pack())],
            [InlineKeyboardButton(text="USDT - TRC20", callback_data=UserPanelCallback(action="buy_usdt").pack())],
            [InlineKeyboardButton(text="Monero - XMR", callback_data=UserPanelCallback(action="buy_xmr").pack())],
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back_to_country").pack())]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    elif callback_data.action == "sell_russia" or callback_data.action == "sell_belarus":
        country = "russia" if callback_data.action == "sell_russia" else "belarus"
        user_id = callback.from_user.id
        if user_id not in user_transaction_data:
            user_transaction_data[user_id] = {}
        user_transaction_data[user_id]["country"] = country
        user_transaction_data[user_id]["operation_type"] = "sell"
        user_transaction_data[user_id]["current_step"] = "country_selected"
        text = "🧩Какую криптовалюту хотите продать?"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bitcoin - BTC", callback_data=UserPanelCallback(action="sell_btc").pack())],
            [InlineKeyboardButton(text="Litecoin - LTC", callback_data=UserPanelCallback(action="sell_ltc").pack())],
            [InlineKeyboardButton(text="USDT - TRC20", callback_data=UserPanelCallback(action="sell_usdt").pack())],
            [InlineKeyboardButton(text="Monero - XMR", callback_data=UserPanelCallback(action="sell_xmr").pack())],
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back_to_country").pack())]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    elif callback_data.action == "payment_next":
        user_id = callback.from_user.id
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            operation_type = transaction.get("operation_type", "buy")
            transaction["current_step"] = "payment_method_selected"
         
            if operation_type == "sell":
                payment_text = "Выберите способ получения средств."
                payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 СБП—ПО НОМЕРУ ТЕЛЕФОНА", callback_data=UserPanelCallback(action="payment_sbp_phone").pack())],
                    [InlineKeyboardButton(text="💳 ПО НОМЕРУ КАРТЫ (+1.75%)", callback_data=UserPanelCallback(action="payment_card_sell").pack())],
                    [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
                ])
            else:
                payment_text = "Выберите банк, на который удобно сделать оплату."
                payment_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 НОМЕР КАРТЫ (СКИДКА 15%)", callback_data=UserPanelCallback(action="payment_card").pack())],
                    [InlineKeyboardButton(text="⬛ СБП - ТРАНСГРАН (СКИДКА 15%)", callback_data=UserPanelCallback(action="payment_sbp_transgran").pack())],
                    [InlineKeyboardButton(text="📱 СБП", callback_data=UserPanelCallback(action="payment_sbp").pack())],
                    [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
                ])
            try:
                await callback.message.edit_text(payment_text, reply_markup=payment_keyboard)
            except:
                await callback.message.answer(payment_text, reply_markup=payment_keyboard)
        await callback.answer()
    elif callback_data.action in ["payment_card", "payment_sbp_transgran", "payment_sbp"]:
        user_id = callback.from_user.id
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            crypto_amount = transaction["crypto_amount"]
            currency_symbol = transaction["currency"]["symbol"].lower()
         
            if crypto_amount < 0.01:
                crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_amount < 1:
                crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
         
            text = f"🔫 **Отправьте боту кошелек, на который должны поступить {crypto_amount_str} {currency_symbol}**"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
            ])
            wallet_request_msg_id = None
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
                wallet_request_msg_id = callback.message.message_id
            except:
                sent_msg = await callback.message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
                wallet_request_msg_id = sent_msg.message_id
            user_transaction_data[user_id]["waiting_wallet"] = True
            user_transaction_data[user_id]["wallet_request_msg_id"] = wallet_request_msg_id
        await callback.answer()
    elif callback_data.action in ["payment_sbp_phone", "payment_card_sell"]:
        user_id = callback.from_user.id
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            rub_amount = transaction["rub_amount"]
            country = transaction.get("country", "russia")
            if country == "belarus":
                amount_display = round(rub_amount * 0.036)
                currency = "бел.рублей"
            else:
                amount_display = rub_amount
                currency = "₽"
            if callback_data.action == "payment_sbp_phone":
                text = f"Введите 💳 СБП—ПО НОМЕРУ ТЕЛЕФОНА реквизиты, куда вы хотите получить {amount_display} {currency}."
            else:
                text = f"Введите 💳 ПО НОМЕРУ КАРТЫ (+1.75%) реквизиты, куда вы хотите получить {amount_display} {currency}."
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
            ])
            try:
                await callback.message.edit_text(text, reply_markup=keyboard)
            except:
                await callback.message.answer(text, reply_markup=keyboard)
            user_transaction_data[user_id]["waiting_payment_details"] = True
            user_transaction_data[user_id]["payment_method"] = callback_data.action
        await callback.answer()
    elif callback_data.action == "delivery_vip":
        await callback.answer()
        try:
            await callback.message.edit_text("⌛Получение реквизитов. Может занимать от 1 до 5 минут.")
        except:
            await callback.message.answer("⌛Получение реквизитов. Может занимать от 1 до 5 минут.")
        await asyncio.sleep(8)
     
        user_id = callback.from_user.id
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            crypto_amount = transaction["crypto_amount"]
            rub_amount = transaction["rub_amount"]
            currency = transaction["currency"]
         
            order_id = f"{user_id}{int(time.time())}"
            country = transaction.get("country", "russia")
            payment_details = get_payment_details(currency['symbol'], country)
            wallet_address = transaction.get("wallet_address") or payment_details.get("wallet_address", "bc1qnv29qqq46vazssl4vlm4drp3scyay96qxnfakx")
            bank_info = payment_details.get("bank", "Альфа-Банк 2200 1536 1378 7010")
         
            if crypto_amount < 0.01:
                crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_amount < 1:
                crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
         
            if country == "belarus":
                amount_display = round(rub_amount * 0.036)
                currency_display = "бел.рублей"
            else:
                amount_display = rub_amount
                currency_display = "₽"
         
            text = f"""☑️Заявка №<code>{order_id}</code> успешно создана!

📎 Адрес зачисления:

<code>{wallet_address}</code>

<b>📎 Вы получаете:</b> <u><b>{crypto_amount_str} {currency['symbol'].upper()}</b></u>

📎 Реквизиты для оплаты:

<code>{bank_info}</code>

<b>💳 Сумма к оплате:</b> <u><b>{amount_display} {currency_display}</b></u>

✅ На оплату 15 минут, после оплаты необходимо нажать на кнопку "ОПЛАТИЛ" """
         
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатил", callback_data=UserPanelCallback(action="payment_done").pack())],
                [InlineKeyboardButton(text="Отменить заявку", callback_data=UserPanelCallback(action="cancel_order").pack())]
            ])
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
         
            user_order_data[user_id] = {
                "order_id": order_id,
                "crypto_amount": crypto_amount,
                "rub_amount": rub_amount,
                "currency": currency,
                "wallet_address": wallet_address,
                "bank_info": bank_info
            }
            del user_transaction_data[user_id]
    elif callback_data.action == "delivery_normal":
        await callback.answer()
        user_id = callback.from_user.id
        if user_id in user_transaction_data:
            transaction = user_transaction_data[user_id]
            crypto_amount = transaction["crypto_amount"]
            rub_amount = transaction["rub_amount"]
            currency = transaction["currency"]
            country = transaction.get("country", "russia")
         
            order_id = f"{user_id}{int(time.time())}"
            country = transaction.get("country", "russia")
            payment_details = get_payment_details(currency["symbol"], country)
            wallet_address = payment_details.get("wallet_address", "bc1qnv29qqq46vazssl4vlm4drp3scyay96qxnfakx")
            bank_info = payment_details.get("bank", "Альфа-Банк 2200 1536 1378 7010")
         
            if crypto_amount < 0.01:
                crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_amount < 1:
                crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
         
            if country == "belarus":
                amount_display = round(rub_amount * 0.036)
                currency_display = "бел.рублей"
            else:
                amount_display = rub_amount
                currency_display = "₽"
         
            text = f"""☑️Заявка №<code>{order_id}</code> успешно создана!

📎 Адрес зачисления:

<code>{wallet_address}</code>

<b>📎 Вы получаете:</b> <u><b>{crypto_amount_str} {currency['symbol'].upper()}</b></u>

📎 Реквизиты для оплаты:

<code>{bank_info}</code>

<b>💳 Сумма к оплате:</b> <u><b>{amount_display} {currency_display}</b></u>

✅ На оплату 15 минут, после оплаты необходимо нажать на кнопку "ОПЛАТИЛ" """
         
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатил", callback_data=UserPanelCallback(action="payment_done").pack())],
                [InlineKeyboardButton(text="Отменить заявку", callback_data=UserPanelCallback(action="cancel_order").pack())]
            ])
            try:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            except:
                await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
         
            user_order_data[user_id] = {
                "order_id": order_id,
                "crypto_amount": crypto_amount,
                "rub_amount": rub_amount,
                "currency": currency,
                "wallet_address": wallet_address,
                "bank_info": bank_info
            }
            del user_transaction_data[user_id]
    elif callback_data.action == "payment_done":
        await callback.answer()
        receipt_text = "Отправьте скрин перевода, либо чек оплаты."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
        ])
        await callback.message.answer(receipt_text, reply_markup=keyboard)
    elif callback_data.action == "main_menu":
        await callback.answer()
        menu_text = """🚜Добро пожаловать в сервис BULBA_BTC_BOT
После каждой операции у вас есть шанс получить бонус 🎁
🔒 Сервис не поддерживает подозрительные или незаконные транзакции.
🔞 Только для пользователей старше 18 лет.
✅ Выберите нужную функцию в меню ниже, чтобы начать работу."""
        try:
            await callback.message.edit_text(menu_text, reply_markup=get_main_keyboard())
        except:
            await callback.message.answer(menu_text, reply_markup=get_main_keyboard())
    elif callback_data.action == "cancel_order":
        await callback.answer("Заявка отменена")
    elif callback_data.action == "admin_set_commission":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_commission)
        await state.update_data(admin_message_id=callback.message.message_id)
        await callback.message.edit_text(f"Текущая комиссия: {COMMISSION_PERCENT}%\n\nВведите новое значение комиссии (%):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_crypto").pack())]]))
    elif callback_data.action.startswith("admin_set_"):
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        crypto = callback_data.action.split("_")[2]
        await state.update_data(crypto=crypto, admin_message_id=callback.message.message_id)
        await state.set_state(AdminState.waiting_type)
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        await callback.message.edit_text(f"Настройка реквизитов для {crypto_names.get(crypto, crypto)}\n\nВыберите, что хотите настроить:", reply_markup=get_admin_type_keyboard())
    elif callback_data.action == "admin_type_card":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        crypto = data.get("crypto")
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        await state.update_data(admin_message_id=callback.message.message_id)
        await state.set_state(AdminState.waiting_country)
        await callback.message.edit_text(f"Настройка реквизитов для {crypto_names.get(crypto, crypto)}\n\nВыберите страну:", reply_markup=get_admin_country_keyboard())
    elif callback_data.action == "admin_country_russia":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        await state.update_data(country="russia", admin_message_id=callback.message.message_id)
        await state.set_state(AdminState.waiting_bank_name)
        await callback.message.edit_text("Введите название банка для России (например: Яндекс Банк):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]]))
    elif callback_data.action == "admin_country_belarus":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        await state.update_data(country="belarus", admin_message_id=callback.message.message_id)
        await state.set_state(AdminState.waiting_bank_name)
        await callback.message.edit_text("Введите название банка для Беларуси (например: Альфа-Банк):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]]))
    elif callback_data.action == "admin_back_to_country":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        crypto = data.get("crypto")
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        await state.set_state(AdminState.waiting_country)
        await callback.message.edit_text(f"Настройка реквизитов для {crypto_names.get(crypto, crypto)}\n\nВыберите страну:", reply_markup=get_admin_country_keyboard())
    elif callback_data.action == "admin_back_to_bank_name":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        country = data.get("country", "russia")
        await state.set_state(AdminState.waiting_bank_name)
        if country == "belarus":
            await callback.message.edit_text("Введите название банка для Беларуси (например: Альфа-Банк):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]]))
        else:
            await callback.message.edit_text("Введите название банка для России (например: Яндекс Банк):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]]))
    elif callback_data.action == "admin_back_to_sbp_phone":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        country = data.get("country", "russia")
        await state.set_state(AdminState.waiting_bank)
        if country == "belarus":
            await callback.message.edit_text("Введите номер карты для Беларуси (например: 2204 3206 0905 0531):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_bank_name").pack())]]))
        else:
            await callback.message.edit_text("Введите номер карты для России (например: 2204 3206 0905 0531):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_bank_name").pack())]]))
    elif callback_data.action == "admin_type_crypto":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        crypto = data.get("crypto")
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        crypto_symbols = {"BTC": "BTC", "LTC": "LTC", "USDT": "USDT", "XMR": "XMR"}
        await state.update_data(admin_message_id=callback.message.message_id)
        await state.set_state(AdminState.waiting_crypto_wallet)
        await callback.message.edit_text(f"Настройка адреса криптокошелька для {crypto_names.get(crypto, crypto)}\n\nВведите адрес кошелька {crypto_symbols.get(crypto, crypto)} (например: bc1qtssazvfvm8hzksmjfa0eta9qf3kctyk0zsyr8u):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_type").pack())]]))
    elif callback_data.action == "admin_back_to_type":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        data = await state.get_data()
        crypto = data.get("crypto")
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        await state.set_state(AdminState.waiting_type)
        await callback.message.edit_text(f"Настройка реквизитов для {crypto_names.get(crypto, crypto)}\n\nВыберите, что хотите настроить:", reply_markup=get_admin_type_keyboard())
    elif callback_data.action == "admin_links":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_links_field)
        await callback.message.edit_text("🔗 Настройка ссылок\n\nВыберите поле для редактирования:", reply_markup=get_admin_links_keyboard())
    elif callback_data.action == "admin_back":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        await callback.message.delete()
    elif callback_data.action == "admin_back_to_crypto":
        if not is_admin(callback.from_user.id):
            await callback.answer("Доступ запрещен", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_crypto)
        await callback.message.edit_text("Выберите криптовалюту для настройки реквизитов:", reply_markup=get_admin_keyboard())
    elif callback_data.action in ["buy_btc", "buy_ltc", "buy_usdt", "buy_xmr"]:
        user_id = callback.from_user.id
        currency_map = {
            "buy_btc": {"name": "Bitcoin - BTC", "symbol": "BTC", "rate": BTC_RATE, "type": "buy"},
            "buy_ltc": {"name": "Litecoin - LTC", "symbol": "LTC", "rate": LTC_RATE, "type": "buy"},
            "buy_usdt": {"name": "USDT - TRC20", "symbol": "USDT", "rate": USDT_RATE, "type": "buy"},
            "buy_xmr": {"name": "Monero - XMR", "symbol": "XMR", "rate": XMR_RATE, "type": "buy"}
        }
        user_selected_currency[user_id] = currency_map[callback_data.action]
        if user_id not in user_transaction_data:
            user_transaction_data[user_id] = {}
        user_transaction_data[user_id]["current_step"] = "crypto_selected"
        logger.info(f"Added currency for user {user_id}: {currency_map[callback_data.action]}")
        text = f"""✅ Введите нужную сумму в {currency_map[callback_data.action]['symbol']} или рублях.
🤖 Оплата будет проверена автоматически."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    elif callback_data.action in ["sell_btc", "sell_ltc", "sell_usdt", "sell_xmr"]:
        user_id = callback.from_user.id
        currency_map = {
            "sell_btc": {"name": "Bitcoin - BTC", "symbol": "BTC", "rate": BTC_RATE_SELL, "type": "sell"},
            "sell_ltc": {"name": "Litecoin - LTC", "symbol": "LTC", "rate": LTC_RATE_SELL, "type": "sell"},
            "sell_usdt": {"name": "USDT - TRC20", "symbol": "USDT", "rate": USDT_RATE_SELL, "type": "sell"},
            "sell_xmr": {"name": "Monero - XMR", "symbol": "XMR", "rate": XMR_RATE_SELL, "type": "sell"}
        }
        user_selected_currency[user_id] = currency_map[callback_data.action]
        if user_id not in user_transaction_data:
            user_transaction_data[user_id] = {}
        user_transaction_data[user_id]["current_step"] = "crypto_selected"
        logger.info(f"Added currency for user {user_id}: {currency_map[callback_data.action]}")
        text = f"""✅ Введите нужную сумму в {currency_map[callback_data.action]['symbol']} или рублях.
🤖 Оплата будет проверена автоматически."""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
        ])
        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
@dp.message(lambda message: message.text == "🚀 Купить")
async def handle_buy(message: types.Message):
    text = "Выберите свою страну."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data=UserPanelCallback(action="buy_russia").pack())],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data=UserPanelCallback(action="buy_belarus").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
    ])
    await message.answer(text, reply_markup=keyboard)
@dp.message(lambda message: message.text == "⚡ Продать")
async def handle_sell(message: types.Message):
    text = "Выберите свою страну."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data=UserPanelCallback(action="sell_russia").pack())],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data=UserPanelCallback(action="sell_belarus").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
    ])
    await message.answer(text, reply_markup=keyboard)
@dp.message(lambda message: message.text == "👾 Контакты")
async def handle_contacts(message: types.Message):
    text = """⚡️ АКТУАЛЬНЫЕ КОНТАКТЫ.
 
✅ СВЯЗЬ 24/7👋🏻"""
    keyboard_buttons = []
 
    if CHANNEL_INFO_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="🌿 Канал-Инфо 🔞", url=CHANNEL_INFO_URL)])
    if ADMIN_CHAT_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="👨‍💻 АДМИН ЧАТА", url=ADMIN_CHAT_URL)])
    if FRESH_REVIEWS_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="💦 Свежие Отзывы", url=FRESH_REVIEWS_URL)])
    if NEW_REVIEWS_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="NEW отзывы", url=NEW_REVIEWS_URL)])
    if ROULETTE_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="💰 КУРИЛКА-РУЛЕТКИ", url=ROULETTE_URL)])
    if OPERATOR_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="👷 Оператор", url=OPERATOR_URL)])
    if PARTNERSHIP_URL:
        keyboard_buttons.append([InlineKeyboardButton(text="🤝 Обсудить партнёрство", url=PARTNERSHIP_URL)])
 
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await message.answer(text, reply_markup=keyboard)
@dp.message(lambda message: message.text == "🎲 Бонусы")
async def handle_bonuses(message: types.Message):
    text = "Розыгрыши от обменника 🥳"
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎲 Лотерея"), KeyboardButton(text="🎳 Еженедельная рулетка")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer(text, reply_markup=keyboard)
@dp.message(lambda message: message.text == "🎲 Лотерея")
async def handle_lottery(message: types.Message):
    await message.answer("У тебя нету попыток на игру в лотерею!Чтобы получить попытку соверши сделку👉🏻")
@dp.message(lambda message: message.text == "🎳 Еженедельная рулетка")
async def handle_weekly_roulette(message: types.Message):
    photo = FSInputFile("ruletka.png")
    text = f"💎✨ PREMIUM NEW YEAR EVENT от BULBA_BTC ✨💎\n\n{WEEKLY_ROULETTE_URL}"
    try:
        await message.answer_photo(photo, caption=text)
    except TelegramForbiddenError:
        logger.warning("Skipping weekly roulette for blocked user_id=%s", message.from_user.id if message.from_user else None)
@dp.message(lambda message: message.text == "⚙️ Панель пользователя")
async def handle_panel(message: types.Message):
    text = "Ваш кабинет."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 История операций", callback_data=UserPanelCallback(action="history").pack())],
        [InlineKeyboardButton(text="🏆 Реферальная программа", callback_data=UserPanelCallback(action="referral").pack())],
        [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
    ])
    await message.answer(text, reply_markup=keyboard)
@dp.message(lambda message: message.text == "◀️ Назад")
async def handle_back(message: types.Message):
    menu_text = """🚜Добро пожаловать в сервис BULBA_BTC_BOT
После каждой операции у вас есть шанс получить бонус 🎁
🔒 Сервис не поддерживает подозрительные или незаконные транзакции.
🔞 Только для пользователей старше 18 лет.
✅ Выберите нужную функцию в меню ниже, чтобы начать работу."""
    await message.answer(menu_text, reply_markup=get_main_keyboard())
@dp.message(lambda message: message.text == "Главное меню")
async def handle_main_menu(message: types.Message):
    menu_text = """🚜Добро пожаловать в сервис BULBA_BTC_BOT
После каждой операции у вас есть шанс получить бонус 🎁
🔒 Сервис не поддерживает подозрительные или незаконные транзакции.
🔞 Только для пользователей старше 18 лет.
✅ Выберите нужную функцию в меню ниже, чтобы начать работу."""
    await message.answer(menu_text, reply_markup=get_main_keyboard())
@dp.callback_query(LinksCallback.filter())
async def links_admin_handler(callback: types.CallbackQuery, callback_data: LinksCallback, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    action = callback_data.action

    if action == "back":
        await callback.answer()
        await state.set_state(AdminState.waiting_crypto)
        await callback.message.edit_text("Выберите криптовалюту для настройки реквизитов:", reply_markup=get_admin_keyboard())
        return

    # Map actions to env var names and display names
    field_map = {
        "edit_rates": ("RATES", "📊 Rates (BTC,LTC,USDT,XMR)"),
        "edit_sell_btc": ("BTC_RATE_SELL", "💵 Sell BTC"),
        "edit_news_channel": ("CHANNEL_INFO_URL", "📢 News Channel"),
        "edit_operator": ("OPERATOR_URL", "👷 Operator"),
        "edit_operator2": ("OPERATOR2", "👷 Operator2"),
        "edit_operator3": ("OPERATOR3", "👷 Operator3"),
        "edit_work_operator": ("WORK_OPERATOR", "📱 Work Operator"),
    }

    if action in field_map:
        env_key, display_name = field_map[action]
        current_value = read_env_var(env_key, "")
        await state.update_data(links_field=env_key, links_field_name=display_name, admin_message_id=callback.message.message_id)
        await state.set_state(AdminState.waiting_link_value)
        await callback.message.edit_text(
            f"🔗 {display_name}\n\nТекущее значение: {current_value if current_value else '(пусто)'}\n\nВведите новое значение:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=LinksCallback(action="back").pack())]])
        )
        await callback.answer()
@dp.message(AdminState.waiting_bank_name)
async def admin_set_bank_name(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
 
    bank_name = message.text
    await state.update_data(bank_name=bank_name)
    await state.set_state(AdminState.waiting_bank)
    data = await state.get_data()
    country = data.get("country", "russia")
    admin_message_id = data.get("admin_message_id")
    if country == "belarus":
        country_text = "Беларуси"
    else:
        country_text = "России"
    if admin_message_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=admin_message_id,
                text=f"Введите номер карты для {country_text} (например: 2204 3206 0905 0531):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]])
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админа: {e}")
            await message.answer(f"Введите номер карты для {country_text} (например: 2204 3206 0905 0531):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]]))
    else:
        await message.answer(f"Введите номер карты для {country_text} (например: 2204 3206 0905 0531):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_country").pack())]]))
    try:
        await message.delete()
    except Exception as e:
        print(f'Exception caught: {e}')
@dp.message(AdminState.waiting_bank)
async def admin_set_bank(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
 
    bank_card = message.text
    await state.update_data(bank_card=bank_card)
    await state.set_state(AdminState.waiting_sbp_phone)
    data = await state.get_data()
    country = data.get("country", "russia")
    admin_message_id = data.get("admin_message_id")
    if country == "belarus":
        country_text = "Беларуси"
    else:
        country_text = "России"
    if admin_message_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=admin_message_id,
                text=f"Введите номер телефона для СБП {country_text} (например: +796538483254):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_sbp_phone").pack())]])
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админа: {e}")
            await message.answer(f"Введите номер телефона для СБП {country_text} (например: +796538483254):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_sbp_phone").pack())]]))
    else:
        await message.answer(f"Введите номер телефона для СБП {country_text} (например: +796538483254):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="admin_back_to_sbp_phone").pack())]]))
    try:
        await message.delete()
    except Exception as e:
        print(f'Exception caught: {e}')
@dp.message(AdminState.waiting_sbp_phone)
async def admin_set_sbp_phone(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
 
    try:
        sbp_phone = message.text
        data = await state.get_data()
        crypto = data.get("crypto")
        country = data.get("country", "russia")
        bank_name = data.get("bank_name", "")
        bank_card = data.get("bank_card", "")
        bank = f"{bank_name} | {bank_card}" if bank_name and bank_card else bank_card
     
        payment_details = load_payment_details()
        if crypto not in payment_details:
            payment_details[crypto] = {}
     
        if country == "belarus":
            payment_details[crypto]["bank_bel"] = bank
            payment_details[crypto]["sbp_phone_bel"] = sbp_phone
            country_name = "Беларуси"
        else:
            payment_details[crypto]["bank"] = bank
            payment_details[crypto]["sbp_phone"] = sbp_phone
            country_name = "России"
     
        save_payment_details(payment_details)
     
        admin_message_id = data.get("admin_message_id")
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад в меню", callback_data=UserPanelCallback(action="admin_back_to_crypto").pack())]
        ])
        if admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=admin_message_id,
                    text=f"✅ Реквизиты для {country_name} ({crypto_names.get(crypto, crypto)}) успешно сохранены!\n\nБанк: {bank}\nНомер телефона СБП: {sbp_phone}",
                    reply_markup=keyboard
                )
            except:
                await message.answer(f"✅ Реквизиты для {country_name} ({crypto_names.get(crypto, crypto)}) успешно сохранены!\n\nБанк: {bank}\nНомер телефона СБП: {sbp_phone}", reply_markup=keyboard)
        else:
            await message.answer(f"✅ Реквизиты для {country_name} ({crypto_names.get(crypto, crypto)}) успешно сохранены!\n\nБанк: {bank}\nНомер телефона СБП: {sbp_phone}", reply_markup=keyboard)
        await message.delete()
        await state.clear()
        await state.update_data({})
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        await state.update_data({})
@dp.message(AdminState.waiting_crypto_wallet)
async def admin_set_crypto_wallet(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
 
    try:
        wallet_address = message.text.strip()
        data = await state.get_data()
        crypto = data.get("crypto")
        crypto_names = {"BTC": "Bitcoin", "LTC": "Litecoin", "USDT": "USDT", "XMR": "Monero"}
        crypto_symbols = {"BTC": "BTC", "LTC": "LTC", "USDT": "USDT", "XMR": "XMR"}
     
        payment_details = load_payment_details()
        if crypto not in payment_details:
            payment_details[crypto] = {}
        payment_details[crypto]["wallet_address"] = wallet_address
        save_payment_details(payment_details)
     
        admin_message_id = data.get("admin_message_id")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад в меню", callback_data=UserPanelCallback(action="admin_back_to_crypto").pack())]
        ])
        if admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=admin_message_id,
                    text=f"✅ Адрес кошелька {crypto_symbols.get(crypto, crypto)} для {crypto_names.get(crypto, crypto)} успешно сохранен!\n\nАдрес: {wallet_address}",
                    reply_markup=keyboard
                )
            except:
                await message.answer(f"✅ Адрес кошелька {crypto_symbols.get(crypto, crypto)} для {crypto_names.get(crypto, crypto)} успешно сохранен!\n\nАдрес: {wallet_address}", reply_markup=keyboard)
        else:
            await message.answer(f"✅ Адрес кошелька {crypto_symbols.get(crypto, crypto)} для {crypto_names.get(crypto, crypto)} успешно сохранен!\n\nАдрес: {wallet_address}", reply_markup=keyboard)
        await message.delete()
        await state.clear()
        await state.update_data({})
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        await state.update_data({})
@dp.message(AdminState.waiting_link_value)
async def admin_set_link_value(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        value = message.text.strip()
        data = await state.get_data()
        env_key = data.get("links_field")
        field_name = data.get("links_field_name", env_key)
        admin_message_id = data.get("admin_message_id")

        if not env_key:
            await message.answer("Ошибка: не найдено поле для обновления")
            await state.clear()
            return

        update_env_var(env_key, value)
        reload_env()

        # Reload global variables
        global_vars = {
            "CHANNEL_INFO_URL": "CHANNEL_INFO_URL",
            "ADMIN_CHAT_URL": "ADMIN_CHAT_URL",
            "FRESH_REVIEWS_URL": "FRESH_REVIEWS_URL",
            "NEW_REVIEWS_URL": "NEW_REVIEWS_URL",
            "ROULETTE_URL": "ROULETTE_URL",
            "OPERATOR_URL": "OPERATOR_URL",
            "PARTNERSHIP_URL": "PARTNERSHIP_URL",
            "WEEKLY_ROULETTE_URL": "WEEKLY_ROULETTE_URL",
            "OPERATOR_USERNAME": "OPERATOR_USERNAME",
            "BTC_RATE_SELL": "BTC_RATE_SELL",
            "LTC_RATE_SELL": "LTC_RATE_SELL",
            "USDT_RATE_SELL": "USDT_RATE_SELL",
            "XMR_RATE_SELL": "XMR_RATE_SELL",
            "BTC_RATE": "BTC_RATE",
            "LTC_RATE": "LTC_RATE",
            "USDT_RATE": "USDT_RATE",
            "XMR_RATE": "XMR_RATE",
            "RATES": "RATES",
            "OPERATOR2": "OPERATOR2",
            "OPERATOR3": "OPERATOR3",
            "WORK_OPERATOR": "WORK_OPERATOR",
        }

        if env_key in global_vars:
            globals()[env_key] = value

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Назад к ссылкам", callback_data=LinksCallback(action="back").pack())]
        ])

        if admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=admin_message_id,
                    text=f"✅ Значение '{field_name}' успешно обновлено!\n\nНовое значение: {value}",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await message.answer(f"✅ Значение '{field_name}' успешно обновлено!\n\nНовое значение: {value}", reply_markup=keyboard)
        else:
            await message.answer(f"✅ Значение '{field_name}' успешно обновлено!\n\nНовое значение: {value}", reply_markup=keyboard)

        await message.delete()
        await state.clear()
        await state.update_data({})
    except Exception as e:
        logger.error(f"Error in admin_set_link_value: {e}")
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        await state.update_data({})
@dp.message(AdminState.waiting_commission)
async def admin_set_commission(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        commission_value = int(message.text.strip())
        if commission_value < 0 or commission_value > 100:
            await message.answer("Комиссия должна быть от 0 до 100%")
            return
        global COMMISSION_PERCENT
        COMMISSION_PERCENT = commission_value
        # Update .env file
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        load_dotenv(env_path)
        # Write updated value to .env
        with open(env_path, 'r') as f:
            lines = f.readlines()
        found = False
        new_lines = []
        for line in lines:
            if line.startswith('COMMISSION_PERCENT='):
                new_lines.append(f'COMMISSION_PERCENT={commission_value}\n')
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f'COMMISSION_PERCENT={commission_value}\n')
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        data = await state.get_data()
        admin_message_id = data.get("admin_message_id")
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад в меню", callback_data=UserPanelCallback(action="admin_back_to_crypto").pack())]
        ])
        if admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=admin_message_id,
                    text=f"✅ Комиссия успешно изменена на {commission_value}%",
                    reply_markup=keyboard
                )
            except:
                await message.answer(f"✅ Комиссия успешно изменена на {commission_value}%", reply_markup=keyboard)
        else:
            await message.answer(f"✅ Комиссия успешно изменена на {commission_value}%", reply_markup=keyboard)
        await message.delete()
        await state.clear()
        await state.update_data({})
    except ValueError:
        await message.answer("Пожалуйста, введите целое число.")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()
        await state.update_data({})
@dp.message(F.photo)
async def photo_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_order_data and ADMIN_IDS:
        try:
            order_data = user_order_data[user_id]
            user_info = f"Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: {user_id})\nЗаявка №{order_data['order_id']}\n\nВалюта: {order_data['currency']['name']}\nСумма: {order_data['crypto_amount']:.6f} {order_data['currency']['symbol']}\nК оплате: {order_data['rub_amount']} ₽\nКошелек: {order_data.get('wallet_address', 'N/A')}"
            for admin_id in ADMIN_IDS:
                await bot.send_photo(admin_id, message.photo[-1].file_id, caption=user_info)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Главное меню", callback_data=UserPanelCallback(action="main_menu").pack())]
            ])
            await message.answer("✅ Чек принят, ожидайте зачисление в течении 20 минут!", reply_markup=keyboard)
            del user_order_data[user_id]
        except Exception as e:
            logger.error(f"Ошибка отправки фото админу: {e}")
@dp.message(F.document)
async def document_handler(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_order_data and ADMIN_IDS:
        try:
            order_data = user_order_data[user_id]
            user_info = f"Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: {user_id})\nЗаявка №{order_data['order_id']}\n\nВалюта: {order_data['currency']['name']}\nСумма: {order_data['crypto_amount']:.6f} {order_data['currency']['symbol']}\nК оплате: {order_data['rub_amount']} ₽\nКошелек: {order_data.get('wallet_address', 'N/A')}"
            for admin_id in ADMIN_IDS:
                await bot.send_document(admin_id, message.document.file_id, caption=user_info)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Главное меню", callback_data=UserPanelCallback(action="main_menu").pack())]
            ])
            await message.answer("✅ Чек принят, ожидайте зачисление в течении 20 минут!", reply_markup=keyboard)
            del user_order_data[user_id]
        except Exception as e:
            logger.error(f"Ошибка отправки документа админу: {e}")
@dp.message()
async def handle_amount(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        return
 
    if not message.text:
        return
 
    user_id = message.from_user.id
 
    if user_id in user_order_data:
        return
 
    current_state = await state.get_state()
    if current_state:
        state_str = str(current_state)
        if "AdminState" in state_str:
            return
 
    if is_admin(user_id) and user_id in user_order_data:
        admin_data = user_order_data[user_id]
        if "order_id" not in admin_data and "admin_type" in admin_data:
            admin_type = admin_data.get("admin_type")
            if admin_type in ["card", "wallet"]:
                if admin_type == "card":
                    crypto = admin_data.get("admin_crypto")
                    if crypto:
                        bank = message.text
                        payment_details = load_payment_details()
                        if crypto not in payment_details:
                            payment_details[crypto] = {}
                        payment_details[crypto]["bank"] = bank
                        save_payment_details(payment_details)
                        await message.answer(f"✅ Реквизиты карты для {crypto} успешно сохранены!\n\nНомер карты: {bank}")
                        del user_order_data[user_id]
                        return
                elif admin_type == "wallet":
                    crypto = admin_data.get("admin_crypto")
                    if crypto:
                        wallet_address = message.text.strip()
                        payment_details = load_payment_details()
                        if crypto not in payment_details:
                            payment_details[crypto] = {}
                        payment_details[crypto]["wallet_address"] = wallet_address
                        save_payment_details(payment_details)
                        await message.answer(f"✅ Адрес кошелька {crypto} успешно сохранен!\n\nАдрес: {wallet_address}")
                        del user_order_data[user_id]
                        return
 
    if user_id in user_transaction_data:
        if user_transaction_data[user_id].get("waiting_payment_details"):
            payment_details_text = message.text
            user_transaction_data[user_id]["payment_details"] = payment_details_text
            del user_transaction_data[user_id]["waiting_payment_details"]
         
            try:
                await message.delete()
            except Exception as e:
                print(f'Exception caught: {e}')
         
            last_message_id = user_transaction_data[user_id].get("last_message_id")
            if last_message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=last_message_id,
                        text="⏳ Подбираем реквизиты..."
                    )
                except:
                    await message.answer("⏳ Подбираем реквизиты...")
            else:
                await message.answer("⏳ Подбираем реквизиты...")
            await asyncio.sleep(5)
         
            transaction = user_transaction_data[user_id]
            crypto_amount = transaction["crypto_amount"]
            crypto_amount_str = transaction.get("crypto_amount_str")
            if not crypto_amount_str:
                if crypto_amount < 0.01:
                    crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                elif crypto_amount < 1:
                    crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                else:
                    crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
            rub_amount = transaction["rub_amount"]
            currency = transaction["currency"]
            payment_method = transaction.get("payment_method", "")
            country = transaction.get("country", "russia")
            order_id = f"{user_id}{int(time.time())}"
         
            payment_details = get_payment_details(currency["symbol"], country)
            wallet_address = payment_details.get("wallet_address", "bc1qnv29qqq46vazssl4vlm4drp3scyay96qxnfakx")
         
            if payment_method == "payment_sbp_phone":
                pass
            else:
                pass
         
            if country == "belarus":
                amount_display = round(rub_amount * 0.036)
                currency_display = "бел.рублей"
            else:
                amount_display = rub_amount
                currency_display = "₽"
         
            text = f"""☑️Заявка №<code>{order_id}</code> успешно создана!

📎 Адрес зачисления:

<code>{payment_details_text}</code>

<b>📎 Вы получаете:</b> <u><b>{amount_display} {currency_display}</b></u>

📎 Реквизиты для оплаты:

<code>{wallet_address}</code>

<b>💳 Сумма к оплате:</b> <u><b>{crypto_amount_str} {currency['symbol'].upper()}</b></u>

✅ На оплату 15 минут, после оплаты необходимо нажать на кнопку "ОПЛАТИЛ" """
         
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатил", callback_data=UserPanelCallback(action="payment_done").pack())],
                [InlineKeyboardButton(text="Отменить заявку", callback_data=UserPanelCallback(action="cancel_order").pack())]
            ])
            if last_message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=last_message_id,
                        text=text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                except:
                    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
         
            user_order_data[user_id] = {
                "order_id": order_id,
                "crypto_amount": crypto_amount,
                "rub_amount": rub_amount,
                "currency": currency,
                "wallet_address": wallet_address,
                "operation_type": "sell"
            }
            del user_transaction_data[user_id]
            return
        elif user_transaction_data[user_id].get("waiting_wallet"):
            wallet_address = message.text
            user_transaction_data[user_id]["wallet_address"] = wallet_address
         
            wallet_request_msg_id = user_transaction_data[user_id].get("wallet_request_msg_id")
            if wallet_request_msg_id:
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=wallet_request_msg_id)
                except Exception as e:
                    print(f'Exception caught: {e}')
         
            try:
                await message.delete()
            except Exception as e:
                print(f'Exception caught: {e}')
         
            text = "Выберите способ доставки"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="ВИП ⚡ 1-25 минут(+170₽)", callback_data=UserPanelCallback(action="delivery_vip").pack())],
                [InlineKeyboardButton(text="Обычная 💨 25-80 минут", callback_data=UserPanelCallback(action="delivery_normal").pack())],
                [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
            ])
            await message.answer(text, reply_markup=keyboard)
            del user_transaction_data[user_id]["waiting_wallet"]
            return
 
    if user_id not in user_selected_currency:
        logger.info(f"User {user_id} not in user_selected_currency. Text: {message.text}, Keys: {list(user_selected_currency.keys())}")
        return
 
    logger.info(f"Processing amount for user {user_id}, currency: {user_selected_currency[user_id]}, text: {message.text}")
 
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer("Сумма должна быть больше нуля.")
            return
     
        currency = user_selected_currency[user_id]
        operation_type = currency.get("type", "buy")
        symbol = currency["symbol"]

        # Получаем динамический курс
        if symbol == "BTC":
            _, rate = await get_btc_rates()
        elif symbol == "LTC":
            _, rate = await get_ltc_rate_coingecko()
        elif symbol == "XMR":
            _, rate = await get_xmr_rate_coingecko()
        else:
            # Для USDT, ETH используем статический курс
            rate = currency["rate"]

        country = "russia"
        if user_id in user_transaction_data:
            country = user_transaction_data[user_id].get("country", "russia")
     
        MIN_AMOUNT_RUB = 1500
     
        commission_multiplier = 1 + COMMISSION_PERCENT / 100
        if operation_type == "sell":
            # Для всей крипты в продаже: до 250 - крипта, иначе - рубли
            if amount < 250:
                crypto_amount = amount
                rub_amount = amount * rate * commission_multiplier
            else:
                rub_amount = amount
                crypto_amount = amount / (rate * commission_multiplier)
            # Для BTC специально: маленькие (0.00xx) всегда крипта, но с порогом <10
            if symbol == "BTC" and amount < 10:
                crypto_amount = amount
                rub_amount = amount * rate * commission_multiplier
        else:  # buy
            if symbol == "BTC":
                # Для BTC buy: маленькие как крипта
                if amount < 10:
                    crypto_amount = amount
                    rub_amount = amount * rate * commission_multiplier
                else:
                    rub_amount = amount
                    crypto_amount = amount / (rate * commission_multiplier)
            else:
                if amount <= 250:
                    crypto_amount = amount
                    rub_amount = amount * rate * commission_multiplier
                else:
                    # 250 < amount: treat as RUB
                    rub_amount = amount
                    crypto_amount = amount / (rate * commission_multiplier)
     
        if country == "belarus":
            min_amount_bel = round(MIN_AMOUNT_RUB * 0.036)
            if rub_amount < MIN_AMOUNT_RUB:
                operation_text = "покупки" if operation_type == "buy" else "продажи"
                await message.answer(f"Минимальная сумма {operation_text} составляет {min_amount_bel} бел.рублей (эквивалент {MIN_AMOUNT_RUB}₽).")
                return
        else:
            if rub_amount < MIN_AMOUNT_RUB:
                await message.answer(f"Минимальная сумма покупки составляет {MIN_AMOUNT_RUB} ₽.")
                return
     
        if country == "belarus":
            amount_display = round(rub_amount * 0.036)
            currency_display = "бел.рублей"
        else:
            amount_display = int(rub_amount)
            currency_display = "₽"
     
        if operation_type == "sell":
            if crypto_amount < 0.01:
                crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_amount < 1:
                crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
            text = f"""-Вам будет зачислено: **{amount_display} {currency_display}**
-Вам необходимо отправить: **{crypto_amount_str} {symbol}**
🎫 У вас используется промокод: **NEWUSER30**, скидка в размере 25% !"""
        else:
            if crypto_amount < 0.01:
                crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_amount < 1:
                crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
            text = f"""-Вам будет зачислено: **{crypto_amount_str} {symbol}**
-Вам необходимо оплатить: **{amount_display} {currency_display}**
🎫 У вас используется промокод: **NEWUSER30**, скидка в размере 25% !"""
     
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Использовать промокод", callback_data=UserPanelCallback(action="payment_next").pack())],
            [InlineKeyboardButton(text="Не использовать промокод", callback_data=UserPanelCallback(action="payment_next").pack())],
            [InlineKeyboardButton(text="Назад", callback_data=UserPanelCallback(action="back").pack())]
        ])
        sent_message = await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")
     
        if user_id not in user_transaction_data:
            user_transaction_data[user_id] = {}
        user_transaction_data[user_id].update({
            "crypto_amount": crypto_amount,
            "crypto_amount_str": crypto_amount_str,
            "rub_amount": int(rub_amount),
            "currency": currency,
            "operation_type": operation_type,
            "country": country,
            "last_message_id": sent_message.message_id,
            "current_step": "amount_entered"
        })
        del user_selected_currency[user_id]
    except ValueError as e:
        logger.error(f"Ошибка преобразования суммы: {e}, текст: {message.text}")
        await message.answer("Пожалуйста, введите корректное число.")
    except Exception as e:
        logger.error(f"Ошибка в handle_amount: {e}")
        await message.answer("Произошла ошибка при обработке суммы. Попробуйте еще раз.")
async def main():
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
