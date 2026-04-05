import asyncio
import logging
import json
import re
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, SwitchInlineQueryChosenChat
from aiogram.filters import CommandStart, Command, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class OrderState(StatesGroup):
    crypto = State()
    amount = State()
    wallet_address = State()
    country = State()
from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_ID_STR.split(",") if admin_id.strip().isdigit()] if ADMIN_ID_STR else []
ROULETTE_LINK = os.getenv("ROULETTE_LINK", "https://t.me/DONALD_BTC_INFO/302")
COMMISSION_BUY = float(os.getenv("COMMISSION_BUY", "20"))
COMMISSION_SELL = float(os.getenv("COMMISSION_SELL", "20"))

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AmountFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        if not message.text:
            return False
        if not re.match(r'^[\d.,]+$', message.text):
            return False
        current_state = await state.get_state()
        if current_state:
            state_str = str(current_state)
            if "AdminState" in state_str:
                return False
        data = await state.get_data()
        payment_method = data.get("payment_method")
        if payment_method:
            return False
        return True

class WalletAddressFilter(BaseFilter):
    async def __call__(self, message: Message, state: FSMContext) -> bool:
        if not message.text:
            return False
        if message.text in ["⭐ Купить", "📤 Продать", "📞 Контакты", "😊 Розыгрыши", "🎲 Лотерея", "🎳 Еженедельная рулетка", "◀️ Назад", "🏠 Мой кабинет"]:
            return False
        current_state = await state.get_state()
        if current_state:
            state_str = str(current_state)
            if "AdminState" in state_str:
                return False
        return True

bot = Bot(token=BOT_TOKEN)

BOT_USERNAME = None

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

def get_payment_details(crypto: str):
    details = load_payment_details()
    return details.get(crypto, {
        "bank": "Ozon Банк 2204 3206 0905 0531",
        "amount_rub": "17758"
    })

async def get_bot_username():
    global BOT_USERNAME
    if BOT_USERNAME is None:
        bot_info = await bot.get_me()
        BOT_USERNAME = bot_info.username
    return BOT_USERNAME

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="⭐ Купить"),
                KeyboardButton(text="📤 Продать")
            ],
            [
                KeyboardButton(text="📞 Контакты"),
                KeyboardButton(text="😊 Розыгрыши")
            ],
            [
                KeyboardButton(text="🏠 Мой кабинет")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await state.set_state(AdminState.waiting_crypto)
    sent_message = await message.answer("Выберите криптовалюту для настройки реквизитов:", reply_markup=get_admin_keyboard())
    await state.update_data(admin_message_id=sent_message.message_id)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    features_text = (
        "⚡️ Обмен цифровых активов в несколько шагов\n"
        "🕑 Поддержка 24/7\n"
        "🤖 Автоматизация сделок и простота использования\n"
        "🎯 Программа для постоянных пользователей\n"
        "🔐 Конфиденциальность и безопасность операций"
    )
    
    photo = FSInputFile("images/start.png")
    await message.answer_photo(photo, caption=features_text)
    
    full_text = (
        "<b>👋 Добро пожаловать в сервис DONALD_BTC_BOT — ваш помощник для удобного обмена цифровых активов!\n\n"
        "🎁 Для пользователей действует программа лояльности.\n"
        "ℹ️ Все операции выполняются в соответствии с установленными правилами.\n"
        "🔐 Сервис работает только с проверенными и безопасными транзакциями.\n\n"
        "✅ Нажмите кнопку в меню ниже, чтобы начать пользоваться сервисом.\n\n"
        "💬 Возникли вопросы? Напишите оператору и укажите:\n"
        "1.Сумму и направление.\n"
        "2.Скрин заявки.\n"
        "3.Скрин интерфейса, где создавалась заявка.</b>"
    )
    
    await message.answer(full_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

def get_country_keyboard(action: str):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Россия", callback_data=f"{action}_russia")],
            [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data=f"{action}_belarus")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

@dp.message(F.text == "⭐ Купить")
async def buy_handler(message: Message):
    photo = FSInputFile("images/select.png")
    await message.answer_photo(photo, caption="Выберите свою страну.", reply_markup=get_country_keyboard("buy"))

@dp.message(F.text == "📤 Продать")
async def sell_handler(message: Message):
    photo = FSInputFile("images/select.png")
    await message.answer_photo(photo, caption="Выберите свою страну.", reply_markup=get_country_keyboard("sell"))

def get_contacts_keyboard():
    operator_url = os.getenv("CONTACT_OPERATOR", "https://t.me/operator")
    smoking_url = os.getenv("CONTACT_SMOKING", "https://t.me/smoking_chat")
    info_url = os.getenv("CONTACT_INFO", "https://t.me/info_channel")
    reviews_url = os.getenv("CONTACT_REVIEWS", "https://t.me/reviews")
    admin_url = os.getenv("CONTACT_ADMIN", "https://t.me/admin")
    operator2_url = os.getenv("CONTACT_OPERATOR2", "https://t.me/operator2")
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ОПЕРАТОР 😎", url=operator_url)],
            [InlineKeyboardButton(text="КУРИЛКА-ЧАТ 👾", url=smoking_url)],
            [InlineKeyboardButton(text="ИНФО-КАНАЛ ☁️", url=info_url)],
            [InlineKeyboardButton(text="ОТЗЫВЫ 🔥", url=reviews_url)],
            [InlineKeyboardButton(text="🧑‍💻 Админ чата", url=admin_url)],
            [InlineKeyboardButton(text="ОПЕРАТОР 2 🧑‍💻", url=operator2_url)],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

@dp.message(F.text == "📞 Контакты")
async def contacts_handler(message: Message):
    photo = FSInputFile("images/contact.png")
    await message.answer_photo(photo, caption="Контакты.", reply_markup=get_contacts_keyboard())

def get_giveaways_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎲 Лотерея"),
                KeyboardButton(text="🎳 Еженедельная рулетка")
            ],
            [
                KeyboardButton(text="◀️ Назад")
            ]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(F.text == "😊 Розыгрыши")
async def giveaways_handler(message: Message):
    photo = FSInputFile("images/bonus.png")
    await message.answer_photo(photo, caption="Розыгрыши от сервиса.", reply_markup=get_giveaways_keyboard())

@dp.message(F.text == "🎲 Лотерея")
async def lottery_handler(message: Message):
    lottery_text = "У тебя нету попыток на игру в лотерею. Чтобы получить попытку соверши сделку 👇"
    await message.answer(lottery_text, reply_markup=get_giveaways_keyboard())

@dp.message(F.text == "🎳 Еженедельная рулетка")
async def roulette_handler(message: Message):
    await message.answer(ROULETTE_LINK, reply_markup=get_giveaways_keyboard())

@dp.message(F.text == "◀️ Назад")
async def back_from_giveaways_handler(message: Message):
    welcome_text = (
        "<b>👋 Добро пожаловать в сервис DONALD_BTC_BOT — ваш помощник для удобного обмена цифровых активов!\n\n"
        "🎁 Для пользователей действует программа лояльности.\n"
        "ℹ️ Все операции выполняются в соответствии с установленными правилами.\n"
        "🔐 Сервис работает только с проверенными и безопасными транзакциями.\n\n"
        "✅ Нажмите кнопку в меню ниже, чтобы начать пользоваться сервисом.\n\n"
        "💬 Возникли вопросы? Напишите оператору и укажите:\n"
        "1.Сумму и направление.\n"
        "2.Скрин заявки.\n"
        "3.Скрин интерфейса, где создавалась заявка.</b>"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")

def get_cabinet_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗄 Архив операций", callback_data="cabinet_archive")],
            [InlineKeyboardButton(text="💵 Партнерам", callback_data="cabinet_partners")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

@dp.message(F.text == "🏠 Мой кабинет")
async def cabinet_handler(message: Message):
    await message.answer("Ваш кабинет.", reply_markup=get_cabinet_keyboard())

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


async def get_partners_keyboard(user_id: int):
    bot_username = await get_bot_username()
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Пригласить друга",
                switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                    query=referral_link,
                    allow_user_chats=True,
                    allow_bot_chats=False,
                    allow_group_chats=True,
                    allow_channel_chats=True
                )
            )],
            [InlineKeyboardButton(text="Вывод средств", callback_data="partners_withdraw")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_cabinet")]
        ]
    )
    return keyboard

async def get_referral_text(user_id: int):
    bot_username = await get_bot_username()
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    text = (
        "🤑Реферальная программа.\n"
        "Приглашайте друзей и получайте процент от каждой сделки Вашего друга.\n\n"
        "✅Данные средства Вы можете потратить как скидку во время обмена или же вывести удобным Вам способом.\n"
        f"🔗Ваша реферальная ссылка:\n{referral_link}\n\n"
        "💰Ваш текущий баланс: 0₽ ~ 0 бел.рублей\n\n"
        "👥Количество рефералов: 0, активных 0\n"
        "🤝Всего получено от рефералов: 0\n\n"
        "🎲Количество проведенных сделок:0\n"
        "Ваш ранг: 👶\n"
        "Ваша скидка: 0.0%"
    )
    return text

@dp.callback_query(F.data.startswith("cabinet_"))
async def cabinet_callback_handler(callback: CallbackQuery):
    cabinet_type = callback.data.split("_")[1]
    if cabinet_type == "archive":
        await callback.answer("Вы не совершили ни одной сделки.")
    elif cabinet_type == "partners":
        await callback.answer()
        user_id = callback.from_user.id
        photo = FSInputFile("images/ref.png")
        referral_text = await get_referral_text(user_id)
        partners_kb = await get_partners_keyboard(user_id)
        await callback.message.answer_photo(photo, caption=referral_text, reply_markup=partners_kb)


@dp.callback_query(F.data == "partners_withdraw")
async def withdraw_funds_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Минимальная сумма для вывода средств равна 500₽")

@dp.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()
    await callback.message.answer("Ваш кабинет.", reply_markup=get_cabinet_keyboard())

def get_crypto_keyboard(action: str, country: str):
    buttons = [
        [InlineKeyboardButton(text="Bitcoin - BTC", callback_data=f"{action}_{country}_BTC")],
        [InlineKeyboardButton(text="Litecoin - LTC", callback_data=f"{action}_{country}_LTC")],
        [InlineKeyboardButton(text="USDT - TRC20", callback_data=f"{action}_{country}_USDT")],
        [InlineKeyboardButton(text="Monero - XMR", callback_data=f"{action}_{country}_XMR")]
    ]
    
    if action == "buy":
        buttons.append([InlineKeyboardButton(text="Tron - TRX", callback_data=f"{action}_{country}_TRX")])
        buttons.append([InlineKeyboardButton(text="Ethereum - ETH", callback_data=f"{action}_{country}_ETH")])
    
    buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_main")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

@dp.callback_query(F.data.in_(["buy_russia", "sell_russia", "buy_belarus", "sell_belarus"]))
async def country_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    action_type = callback.data.split("_")[0]
    country = callback.data.split("_")[1]
    
    await state.clear()
    await state.update_data(country=country, action_type=action_type)
    
    if action_type == "buy":
        caption = "✨ Какую криптовалюту хотите приобрести?"
    else:
        caption = "✨ Какую криптовалюту хотите продать?"
    
    if country == "russia":
        photo_path = "images/RU.png"
    elif country == "belarus":
        photo_path = "images/BY.png" if os.path.exists("images/BY.png") else "images/RU.png"
    else:
        photo_path = "images/RU.png"
    
    if os.path.exists(photo_path):
        photo = FSInputFile(photo_path)
        await callback.message.answer_photo(photo, caption=caption, reply_markup=get_crypto_keyboard(action_type, country))
    else:
        await callback.message.answer(caption, reply_markup=get_crypto_keyboard(action_type, country))

def get_amount_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard


crypto_info = {
    "BTC": {"name": "Bitcoin", "photo": "images/btc.png", "symbol": "BTC", "coingecko_id": "bitcoin"},
    "LTC": {"name": "Litecoin", "photo": "images/ltc.png", "symbol": "LTC", "coingecko_id": "litecoin"},
    "USDT": {"name": "USDT", "photo": "images/usdt.png", "symbol": "USDT", "coingecko_id": "tether"},
    "XMR": {"name": "Monero", "photo": "images/monero.png", "symbol": "XMR", "coingecko_id": "monero"},
    "TRX": {"name": "Tron", "photo": None, "symbol": "TRX", "coingecko_id": "tron"},
    "ETH": {"name": "Ethereum", "photo": None, "symbol": "ETH", "coingecko_id": "ethereum"}
}

async def get_official_rate(crypto: str) -> float:
    try:
        crypto_data = crypto_info.get(crypto, crypto_info["BTC"])
        coingecko_id = crypto_data.get("coingecko_id", "bitcoin")
        
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.coingecko.com/api/v3/simple/price?ids={coingecko_id}&vs_currencies=rub") as response:
                if response.status == 200:
                    data = await response.json()
                    official_rate = data.get(coingecko_id, {}).get("rub", 0)
                    if official_rate > 0:
                        return official_rate
    except asyncio.TimeoutError:
        logger.warning(f"Таймаут при получении курса {crypto}, используем fallback")
    except Exception as e:
        logger.error(f"Ошибка получения курса {crypto}: {e}")
    
    fallback_rates = {
        "BTC": 6900000,
        "LTC": 8500,
        "USDT": 92,
        "XMR": 18000,
        "TRX": 8.5,
        "ETH": 280000
    }
    return fallback_rates.get(crypto, 6900000)

async def get_crypto_rate(crypto: str) -> float:
    official_rate = await get_official_rate(crypto)
    return official_rate * (1 + COMMISSION_BUY / 100)

async def get_sell_rate(crypto: str) -> float:
    official_rate = await get_official_rate(crypto)
    return official_rate * (1 - COMMISSION_SELL / 100)

@dp.callback_query((F.data.endswith("_BTC") | F.data.endswith("_LTC") | F.data.endswith("_USDT") | F.data.endswith("_XMR") | F.data.endswith("_TRX") | F.data.endswith("_ETH")) & ~F.data.startswith("admin_set_"))
async def crypto_handler(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state and current_state.startswith("AdminState"):
        return
    
    await callback.answer()
    parts = callback.data.split("_")
    crypto = parts[2]
    country = parts[1]
    action_type = parts[0]
    
    data = await state.get_data()
    data.pop("payment_method", None)
    data.pop("payment_details", None)
    data.pop("wallet_address", None)
    data.pop("order_message_id", None)
    data.pop("order_number", None)
    data.pop("amount", None)
    data.pop("calculated_amount_payment", None)
    await state.update_data(**data)
    await state.update_data(crypto=crypto, country=country, action_type=action_type)
    
    if action_type == "sell":
        amount_text = (
            "🎯ВВЕДИТЕ СУММУ ДЛЯ РАСЧЁТА:\n\n"
            f"✅Введите количество {crypto_info.get(crypto, {}).get('symbol', crypto)}, которое хотите продать\n"
            "Например: 5000 (для USDT) или 0.002 (для BTC)"
        )
    elif crypto == "USDT":
        amount_text = (
            "🎯ВВЕДИТЕ СУММУ ДЛЯ РАСЧЁТА:\n\n"
            "✅Введите сумму в рублях (₽)\n"
            "Например: 1000 (рублей)"
        )
    else:
        amount_text = (
            "🎯ВВЕДИТЕ СУММУ ДЛЯ РАСЧЁТА:\n\n"
            "✅Например: 0.002, 0,002 или 1000(если в рублях)"
        )
    await callback.message.answer(amount_text, reply_markup=get_amount_keyboard())

@dp.message(AmountFilter())
async def amount_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"amount_handler: состояние = {current_state}, текст = {message.text}")
    if current_state:
        state_str = str(current_state)
        if "AdminState" in state_str:
            logger.info("amount_handler: пропускаю, состояние админки")
            return
    data = await state.get_data()
    action_type = data.get("action_type")
    if not action_type:
        return
    
    amount = message.text.replace(',', '.')
    
    processing_msg = None
    try:
        
        crypto = data.get("crypto")
        action_type = data.get("action_type")
        if not crypto or not action_type:
            return
        
        processing_msg = await message.answer("⏳ Обрабатываю...")
        
        amount_float = float(amount)
        country = data.get("country", "russia")
        
        crypto_data = crypto_info.get(crypto, crypto_info["BTC"])
        crypto_data["name"]
        crypto_symbol = crypto_data["symbol"]
        
        get_payment_details(crypto)
        
        
        MIN_PURCHASE_AMOUNT_RUB = 1500
        
        if action_type == "sell":
            if crypto == "USDT":
                crypto_amount = amount_float
            elif amount_float >= 1000:
                try:
                    usdt_rate = await get_crypto_rate("USDT")
                    usdt_amount = amount_float
                    crypto_rate = await get_crypto_rate(crypto)
                    crypto_amount = (usdt_amount * usdt_rate) / crypto_rate
                except Exception as e:
                    logger.error(f"Ошибка конвертации USDT в {crypto}: {e}")
                    crypto_amount = amount_float
            else:
                crypto_amount = amount_float
            
            try:
                sell_rate = await get_sell_rate(crypto)
            except Exception as e:
                logger.error(f"Ошибка получения курса продажи {crypto}: {e}")
                fallback_rates = {
                    "BTC": 6900000 * (1 - COMMISSION_SELL / 100),
                    "LTC": 8500 * (1 - COMMISSION_SELL / 100),
                    "USDT": 92 * (1 - COMMISSION_SELL / 100),
                    "XMR": 18000 * (1 - COMMISSION_SELL / 100),
                    "TRX": 8.5 * (1 - COMMISSION_SELL / 100),
                    "ETH": 280000 * (1 - COMMISSION_SELL / 100)
                }
                sell_rate = fallback_rates.get(crypto, 6900000 * (1 - COMMISSION_SELL / 100))
            
            amount_received_rub = crypto_amount * sell_rate
            
            if country == "belarus":
                amount_received = round(amount_received_rub * 0.036)
                currency = "бел.рублей"
                currency_short = "бел.рублей"
            else:
                amount_received = round(amount_received_rub)
                currency = "₽"
                currency_short = "в рублях"
            
            if crypto_amount < 0.01:
                crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_amount < 1:
                crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
            
            info_text = (
                f"Вам будет зачислено: {amount_received} {currency}\n"
                f"Вам необходимо отправить: {crypto_amount_str} {crypto_symbol}\n"
                f"Итоговая сумма зачисления {currency_short}: {amount_received} {currency}"
            )
            
            await state.update_data(amount=crypto_amount_str, calculated_amount_payment=amount_received)
        else:
            if crypto == "USDT":
                amount_payment_rub = amount_float
                
                if amount_payment_rub < MIN_PURCHASE_AMOUNT_RUB:
                    if processing_msg:
                        try:
                            await processing_msg.delete()
                        except:
                            pass
                    if country == "belarus":
                        min_amount = round(MIN_PURCHASE_AMOUNT_RUB * 0.036)
                        await message.answer(f"Минимальная сумма покупки составляет {min_amount} бел.рублей (эквивалент 1500₽).")
                    else:
                        await message.answer(f"Минимальная сумма покупки составляет {MIN_PURCHASE_AMOUNT_RUB}₽.")
                    return
                
                usdt_rate = await get_crypto_rate("USDT")
                usdt_amount = amount_payment_rub / usdt_rate
                
                if country == "belarus":
                    amount_payment = round(amount_payment_rub * 0.036)
                    currency = "бел.рублей"
                    currency_short = "бел.рублей"
                else:
                    amount_payment = round(amount_payment_rub)
                    currency = "₽"
                    currency_short = "в рублях"
                
                info_text = (
                    f"Вам будет зачислено: {round(usdt_amount, 6)} {crypto_symbol}\n"
                    f"Вам необходимо оплатить: {amount_payment} {currency_short}"
                )
                
                usdt_amount_str = str(round(usdt_amount, 6))
                await state.update_data(amount=usdt_amount_str, calculated_amount_payment=amount_payment)
            else:
                crypto_rate = await get_crypto_rate(crypto)
                
                if amount_float >= 1000:
                    amount_payment_rub = amount_float
                    crypto_amount = amount_payment_rub / crypto_rate
                else:
                    crypto_amount = amount_float
                    amount_payment_rub = crypto_amount * crypto_rate
                
                if amount_payment_rub < MIN_PURCHASE_AMOUNT_RUB:
                    if processing_msg:
                        try:
                            await processing_msg.delete()
                        except:
                            pass
                    if country == "belarus":
                        min_amount = round(MIN_PURCHASE_AMOUNT_RUB * 0.036)
                        await message.answer(f"Минимальная сумма покупки составляет {min_amount} бел.рублей (эквивалент 1500₽).")
                    else:
                        await message.answer(f"Минимальная сумма покупки составляет {MIN_PURCHASE_AMOUNT_RUB}₽.")
                    return
                
                if country == "belarus":
                    amount_payment = round(amount_payment_rub * 0.036)
                    currency = "бел.рублей"
                    currency_short = "бел.рублей"
                else:
                    amount_payment = round(amount_payment_rub)
                    currency = "₽"
                    currency_short = "в рублях"
                
                if crypto_amount < 0.01:
                    crypto_amount_str = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                elif crypto_amount < 1:
                    crypto_amount_str = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                else:
                    crypto_amount_str = f"{crypto_amount:.4f}".rstrip('0').rstrip('.')
                
                info_text = (
                    f"Вам будет зачислено: {crypto_amount_str} {crypto_symbol}\n"
                    f"Вам необходимо оплатить: {amount_payment} {currency_short}"
                )
                
                await state.update_data(amount=crypto_amount_str, calculated_amount_payment=amount_payment)
        
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        await message.answer(info_text)
        
        photo = FSInputFile("images/pay.png")
        await message.answer_photo(photo, caption="Выберите банк, на который удобно сделать оплату.", reply_markup=get_payment_keyboard(action_type))
    except ValueError:
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
    except Exception as e:
        logger.error(f"Ошибка в amount_handler: {e}")
        if processing_msg:
            try:
                await processing_msg.delete()
            except:
                pass
        await message.answer("Произошла ошибка при обработке суммы. Попробуйте еще раз.")

@dp.message(WalletAddressFilter())
async def wallet_address_handler(message: Message, state: FSMContext):
    
    text = message.text.strip()
    data = await state.get_data()
    action_type = data.get("action_type")
    crypto = data.get("crypto")
    payment_method = data.get("payment_method")
    
    if not crypto or not action_type:
        return
    
    if not payment_method:
        return
    
    if action_type == "sell":
        await state.update_data(payment_details=text)
        await message.answer("⏳ Подбираем реквизиты...")
        await asyncio.sleep(5)
        await send_payment_details(message, state, is_vip=False)
        return
    elif action_type == "buy":
        country = data.get("country", "russia")
        await state.update_data(wallet_address=text)
        await message.answer("Выберите способ доставки", reply_markup=get_delivery_keyboard(country))
        return

def get_payment_keyboard(action_type: str = "buy"):
    if action_type == "sell":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 СБП—ПО НОМЕРУ ТЕЛЕФОНА", callback_data="payment_sbp_phone")],
                [InlineKeyboardButton(text="💳 ПО НОМЕРУ КАРТЫ (+1.75%)", callback_data="payment_card_sell")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
            ]
        )
    else:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 НОМЕР КАРТЫ (СКИДКА 10%)", callback_data="payment_card")],
                [InlineKeyboardButton(text="📱 СБП—ТРАНСГРАНИЧНЫЙ (СКИДКА 20%)", callback_data="payment_sbp_cross")],
                [InlineKeyboardButton(text="💳 СБП-СИСТЕМА БЫСТРЫХ ПЛАТЕЖЕЙ", callback_data="payment_sbp")],
                [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
            ]
        )
    return keyboard

def get_wallet_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

@dp.callback_query(F.data.in_(["payment_card", "payment_sbp_cross", "payment_sbp", "payment_sbp_phone", "payment_card_sell"]))
async def payment_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    crypto = data.get("crypto", "BTC")
    amount = data.get("amount", "0.002")
    action_type = data.get("action_type", "buy")
    country = data.get("country", "russia")
    
    await state.update_data(payment_method=callback.data)
    
    if action_type == "sell":
        calculated_amount = data.get("calculated_amount_payment")
        if calculated_amount:
            amount_rub = calculated_amount
        else:
            amount_float = float(amount)
            sell_rate = await get_sell_rate(crypto)
            amount_received_rub = amount_float * sell_rate
            if country == "belarus":
                amount_rub = round(amount_received_rub * 0.036)
            else:
                amount_rub = round(amount_received_rub)
        
        if country == "belarus":
            currency = "бел.рублей"
        else:
            currency = "₽"
        
        if callback.data == "payment_sbp_phone":
            wallet_text = f"Введите 💳 СБП—ПО НОМЕРУ ТЕЛЕФОНА реквизиты, куда вы хотите получить {amount_rub} {currency}."
        else:
            wallet_text = f"Введите 💳 ПО НОМЕРУ КАРТЫ (+1.75%) реквизиты, куда вы хотите получить {amount_rub} {currency}."
        
        photo = FSInputFile("images/walletrub.png")
        await callback.message.answer_photo(photo, caption=wallet_text, reply_markup=get_wallet_keyboard())
    else:
        crypto_data = crypto_info.get(crypto, crypto_info["BTC"])
        crypto_data["name"]
        crypto_symbol = crypto_data["symbol"]
        photo_file = crypto_data.get("photo")
        
        wallet_text = f"Введите {crypto_symbol}-адрес кошелька, куда вы хотите отправить {amount} {crypto_symbol.lower()}."
        
        if photo_file and os.path.exists(photo_file):
            photo = FSInputFile(photo_file)
            await callback.message.answer_photo(photo, caption=wallet_text, reply_markup=get_wallet_keyboard())
        else:
            await callback.message.answer(wallet_text, reply_markup=get_wallet_keyboard())

def get_delivery_keyboard(country: str = "russia"):
    if country == "belarus":
        vip_text = "ВИП ⚡ 1-25 минут (+7бел.рублей)"
    else:
        vip_text = "ВИП ⚡ 1-25 минут (+160₽)"
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=vip_text, callback_data="delivery_vip")],
            [InlineKeyboardButton(text="Обычная 💨 25-80 минут", callback_data="delivery_standard")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

def get_payment_details_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатил", callback_data="payment_done")],
            [InlineKeyboardButton(text="Отменить заявку", callback_data="cancel_order")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

async def send_payment_details(message: Message, state: FSMContext, is_vip: bool = False):
    import re as re_module
    data = await state.get_data()
    crypto = data.get("crypto", "BTC")
    amount = data.get("amount", "0.002")
    action_type = data.get("action_type", "buy")
    country = data.get("country", "russia")
    payment_method = data.get("payment_method", "")
    payment_details_text = data.get("payment_details", "")
    
    crypto_data = crypto_info.get(crypto, crypto_info["BTC"])
    crypto_data["name"]
    crypto_symbol = crypto_data["symbol"]
    
    payment_details = get_payment_details(crypto)
    
    if action_type == "buy":
        calculated_amount = data.get("calculated_amount_payment")
        if calculated_amount:
            amount_payment = calculated_amount
        else:
            amount_float = float(amount)
            crypto_rate = await get_crypto_rate(crypto)
            amount_payment_rub = amount_float * crypto_rate
            if country == "belarus":
                amount_payment = round(amount_payment_rub * 0.036)
            else:
                amount_payment = round(amount_payment_rub)
    else:
        calculated_amount = data.get("calculated_amount_payment")
        if calculated_amount:
            amount_payment = calculated_amount
        else:
            amount_float = float(amount)
            sell_rate = await get_sell_rate(crypto)
            amount_received_rub = amount_float * sell_rate
            if country == "belarus":
                amount_payment = round(amount_received_rub * 0.036)
            else:
                amount_payment = round(amount_received_rub)
    
    if country == "belarus":
        currency = "бел.рублей"
    else:
        currency = "₽"
    
    order_number = "1764893443112"
    
    if action_type == "sell":
        btc_address = payment_details.get("wallet_address", "bc1qtssazvfvm8hzksmjfa0eta9qf3kctyk0zsyr8u")
        btc_address_formatted = f"`{btc_address}`"
        if payment_method == "payment_sbp_phone":
            method_text = "💳 СБП—ПО НОМЕРУ ТЕЛЕФОНА реквизиты:"
        else:
            method_text = "💳 ПО НОМЕРУ КАРТЫ (+1.75%) реквизиты:"
        
        payment_details_formatted = re_module.sub(r'(\d{4}\s+\d{4}\s+\d{4}\s+\d{4})', r'`\1`', payment_details_text)
        if payment_details_formatted == payment_details_text:
            payment_details_formatted = re_module.sub(r'(\d{16})', r'`\1`', payment_details_text)
        if payment_details_formatted == payment_details_text:
            payment_details_formatted = re_module.sub(r'(\d{9,12})', r'`\1`', payment_details_text)
        
        payment_text = (
            f"✅ Заявка №{order_number} успешно создана.\n\n"
            f"Вы получаете: {amount_payment} {currency}\n"
            f"Вам необходимо отправить: {amount} {crypto_symbol.lower()}\n"
            f"{method_text}\n{payment_details_formatted}\n\n"
            f"Ваш ранг: 👶, скидка 0.0 %\n\n"
            f"Реквизиты для перевода {crypto_symbol.lower()}:\n{btc_address_formatted}\n\n"
            f"⏰ Заявка действительна: 15 минут\n\n"
            f"✅ После оплаты необходимо нажать на кнопку 'ОПЛАТА СОВЕРШЕНА'"
        )
    else:
        wallet_address = data.get("wallet_address", "")
        wallet_address_formatted = f"`{wallet_address}`"
        
        if payment_method in ["payment_sbp", "payment_sbp_phone", "payment_sbp_cross"]:
            if country == "belarus":
                bank_details = payment_details.get("sbp_phone_bel", "")
            else:
                bank_details = payment_details.get("sbp_phone", "")
            if not bank_details:
                if country == "belarus":
                    bank_details = payment_details.get("bank_bel", "ЕРИП ПЛАТЕЖИ\nБАНКОВСКИЕ ФИНАНСОВЫЕ УСЛУГИ\nБАНКИ НКΦΟ\nАЛЬФА БАНК\nПОПОЛНЕНИЕ СЧЕТА\n375257298681")
                else:
                    bank_details = payment_details.get("bank", "Ozon Банк 2204 3206 0905 0531")
        else:
            if country == "belarus":
                bank_details = payment_details.get("bank_bel", "ЕРИП ПЛАТЕЖИ\nБАНКОВСКИЕ ФИНАНСОВЫЕ УСЛУГИ\nБАНКИ НКΦΟ\nАЛЬФА БАНК\nПОПОЛНЕНИЕ СЧЕТА\n375257298681")
            else:
                bank_details = payment_details.get("bank", "Ozon Банк 2204 3206 0905 0531")
        
        bank_details_formatted = re_module.sub(r'(\d{4}\s+\d{4}\s+\d{4}\s+\d{4})', r'`\1`', bank_details)
        if bank_details_formatted == bank_details:
            bank_details_formatted = re_module.sub(r'(\d{16})', r'`\1`', bank_details)
        if bank_details_formatted == bank_details:
            bank_details_formatted = re_module.sub(r'(\d{9,12})', r'`\1`', bank_details)
        
        payment_text = (
            f"✅ Заявка №{order_number} успешно создана.\n\n"
            f"Вы получаете: {amount} {crypto_symbol.lower()}\n"
            f"{crypto_symbol}-адрес:\n{wallet_address_formatted}\n\n"
            f"Ваш ранг: 👶, скидка 0.0 %\n\n"
            f"💳 Сумма к оплате: {amount_payment} {currency}\n\n"
            f"Реквизиты для оплаты:\n{bank_details_formatted}\n\n"
            f"⚠️ Оплачивайте точную сумму до КОПЕЕК, иначе проверка займёт больше времени!\n\n"
            f"⏰ Заявка действительна: 15 минут\n\n"
            f"✅ После оплаты необходимо нажать на кнопку 'ОПЛАТА СОВЕРШЕНА'"
        )
    
    sent_message = await message.answer(payment_text, reply_markup=get_payment_details_keyboard(), parse_mode="Markdown")
    await state.update_data(order_message_id=sent_message.message_id, order_number=order_number)

@dp.callback_query(F.data == "delivery_vip")
async def delivery_vip_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_payment_details(callback.message, state, is_vip=True)

@dp.callback_query(F.data == "delivery_standard")
async def delivery_standard_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await send_payment_details(callback.message, state, is_vip=False)

def get_receipt_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
        ]
    )
    return keyboard

@dp.callback_query(F.data == "payment_done")
async def payment_done_handler(callback: CallbackQuery):
    await callback.answer()
    receipt_text = "Отправьте скрин перевода, либо чек оплаты."
    await callback.message.answer(receipt_text, reply_markup=get_receipt_keyboard())
    await callback.message.delete()

@dp.message(F.photo)
async def photo_handler(message: Message, state: FSMContext):
    if ADMIN_IDS:
        try:
            data = await state.get_data()
            order_number = data.get("order_number", "N/A")
            user_info = f"Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: {message.from_user.id})\nЗаявка №{order_number}"
            for admin_id in ADMIN_IDS:
                await bot.send_photo(admin_id, message.photo[-1].file_id, caption=user_info)
        except Exception as e:
            logger.error(f"Ошибка отправки фото админу: {e}")
    
    processing_text = "Заявка обрабатывается.. Ожидайте."
    await message.answer(processing_text, reply_markup=get_main_keyboard())

@dp.message(F.document)
async def document_handler(message: Message, state: FSMContext):
    if ADMIN_IDS:
        try:
            data = await state.get_data()
            order_number = data.get("order_number", "N/A")
            user_info = f"Пользователь: @{message.from_user.username or message.from_user.first_name} (ID: {message.from_user.id})\nЗаявка №{order_number}"
            for admin_id in ADMIN_IDS:
                await bot.send_document(admin_id, message.document.file_id, caption=user_info)
        except Exception as e:
            logger.error(f"Ошибка отправки документа админу: {e}")
    
    processing_text = "Заявка обрабатывается.. Ожидайте."
    await message.answer(processing_text, reply_markup=get_main_keyboard())

def get_cancel_confirm_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data="confirm_cancel"),
                InlineKeyboardButton(text="Нет", callback_data="cancel_cancel")
            ]
        ]
    )
    return keyboard

@dp.callback_query(F.data == "cancel_order")
async def cancel_order_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Вы действительно хотите отменить заявку?", reply_markup=get_cancel_confirm_keyboard())

@dp.callback_query(F.data == "confirm_cancel")
async def confirm_cancel_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    order_message_id = data.get("order_message_id")
    
    if order_message_id:
        await bot.send_message(
            callback.message.chat.id,
            "❌ Заявка была отменена.",
            reply_to_message_id=order_message_id
        )
    else:
        await callback.message.answer("❌ Заявка была отменена.")
    
    await callback.message.delete()

@dp.callback_query(F.data == "cancel_cancel")
async def cancel_cancel_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()

class AdminState(StatesGroup):
    waiting_crypto = State()
    waiting_type = State()
    waiting_country = State()
    waiting_bank = State()
    waiting_sbp_phone = State()
    waiting_crypto_wallet = State()

@dp.message(AdminState.waiting_bank)
async def admin_set_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    bank = message.text
    await state.update_data(bank=bank)
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
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_sbp_phone")]])
            )
        except Exception as e:
            logger.error(f"Ошибка редактирования сообщения админа: {e}")
            await message.answer(f"Введите номер телефона для СБП {country_text} (например: +796538483254):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_sbp_phone")]]))
    else:
        await message.answer(f"Введите номер телефона для СБП {country_text} (например: +796538483254):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_sbp_phone")]]))
    try:
        await message.delete()
    except:
        pass

@dp.message(AdminState.waiting_sbp_phone)
async def admin_set_sbp_phone(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        sbp_phone = message.text
        data = await state.get_data()
        crypto = data.get("crypto")
        country = data.get("country", "russia")
        bank = data.get("bank")
        
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
        crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Назад в меню", callback_data="admin_back_to_crypto")]
            ]
        )
        if admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=admin_message_id,
                    text=f"✅ Реквизиты для {country_name} ({crypto_name}) успешно сохранены!\n\nНомер карты: {bank}\nНомер телефона СБП: {sbp_phone}",
                    reply_markup=keyboard
                )
            except:
                await message.answer(f"✅ Реквизиты для {country_name} ({crypto_name}) успешно сохранены!\n\nНомер карты: {bank}\nНомер телефона СБП: {sbp_phone}", reply_markup=keyboard)
        else:
            await message.answer(f"✅ Реквизиты для {country_name} ({crypto_name}) успешно сохранены!\n\nНомер карты: {bank}\nНомер телефона СБП: {sbp_phone}", reply_markup=keyboard)
        await message.delete()
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()




@dp.message(AdminState.waiting_crypto_wallet)
async def admin_set_crypto_wallet(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    try:
        wallet_address = message.text.strip()
        data = await state.get_data()
        crypto = data.get("crypto")
        crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
        crypto_symbol = crypto_info.get(crypto, {}).get('symbol', crypto)
        
        payment_details = load_payment_details()
        if crypto not in payment_details:
            payment_details[crypto] = {}
        payment_details[crypto]["wallet_address"] = wallet_address
        save_payment_details(payment_details)
        
        admin_message_id = data.get("admin_message_id")
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Назад в меню", callback_data="admin_back_to_crypto")]
            ]
        )
        if admin_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=admin_message_id,
                    text=f"✅ Адрес кошелька {crypto_symbol} для {crypto_name} успешно сохранен!\n\nАдрес: {wallet_address}",
                    reply_markup=keyboard
                )
            except:
                await message.answer(f"✅ Адрес кошелька {crypto_symbol} для {crypto_name} успешно сохранен!\n\nАдрес: {wallet_address}", reply_markup=keyboard)
        else:
            await message.answer(f"✅ Адрес кошелька {crypto_symbol} для {crypto_name} успешно сохранен!\n\nАдрес: {wallet_address}", reply_markup=keyboard)
        await message.delete()
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()

def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="BTC", callback_data="admin_set_BTC")],
            [InlineKeyboardButton(text="LTC", callback_data="admin_set_LTC")],
            [InlineKeyboardButton(text="USDT", callback_data="admin_set_USDT")],
            [InlineKeyboardButton(text="XMR", callback_data="admin_set_XMR")],
            [InlineKeyboardButton(text="TRX", callback_data="admin_set_TRX")],
            [InlineKeyboardButton(text="ETH", callback_data="admin_set_ETH")],
            [InlineKeyboardButton(text="Назад", callback_data="admin_back")]
        ]
    )
    return keyboard

def get_admin_type_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Настроить реквизиты карты", callback_data="admin_type_card")],
            [InlineKeyboardButton(text="₿ Настроить адрес криптокошелька", callback_data="admin_type_crypto")],
            [InlineKeyboardButton(text="Назад", callback_data="admin_back_to_crypto")]
        ]
    )
    return keyboard

def get_admin_country_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="admin_country_russia")],
            [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data="admin_country_belarus")],
            [InlineKeyboardButton(text="Назад", callback_data="admin_back_to_type")]
        ]
    )
    return keyboard

@dp.callback_query(F.data.startswith("admin_set_"))
async def admin_set_crypto(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    crypto = callback.data.split("_")[2]
    await state.update_data(crypto=crypto, admin_message_id=callback.message.message_id)
    await state.set_state(AdminState.waiting_type)
    crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
    await callback.message.edit_text(
        f"Настройка реквизитов для {crypto_name}\n\nВыберите, что хотите настроить:",
        reply_markup=get_admin_type_keyboard()
    )

@dp.callback_query(F.data == "admin_type_card")
async def admin_type_card_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    data = await state.get_data()
    crypto = data.get("crypto")
    crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
    await state.update_data(admin_message_id=callback.message.message_id)
    await state.set_state(AdminState.waiting_country)
    await callback.message.edit_text(
        f"Настройка реквизитов для {crypto_name}\n\nВыберите страну:",
        reply_markup=get_admin_country_keyboard()
    )

@dp.callback_query(F.data == "admin_country_russia")
async def admin_country_russia_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    await state.update_data(country="russia", admin_message_id=callback.message.message_id)
    await state.set_state(AdminState.waiting_bank)
    await callback.message.edit_text(
        "Введите номер карты для России (например: 2204 3206 0905 0531):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_country")]])
    )

@dp.callback_query(F.data == "admin_country_belarus")
async def admin_country_belarus_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    await state.update_data(country="belarus", admin_message_id=callback.message.message_id)
    await state.set_state(AdminState.waiting_bank)
    await callback.message.edit_text(
        "Введите номер карты для Беларуси (например: 2204 3206 0905 0531):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_country")]])
    )

@dp.callback_query(F.data == "admin_back_to_country")
async def admin_back_to_country_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    data = await state.get_data()
    crypto = data.get("crypto")
    crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
    await state.set_state(AdminState.waiting_country)
    await callback.message.edit_text(
        f"Настройка реквизитов для {crypto_name}\n\nВыберите страну:",
        reply_markup=get_admin_country_keyboard()
    )

@dp.callback_query(F.data == "admin_type_crypto")
async def admin_type_crypto_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    data = await state.get_data()
    crypto = data.get("crypto")
    crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
    crypto_symbol = crypto_info.get(crypto, {}).get('symbol', crypto)
    await state.update_data(admin_message_id=callback.message.message_id)
    await state.set_state(AdminState.waiting_crypto_wallet)
    await callback.message.edit_text(
        f"Настройка адреса криптокошелька для {crypto_name}\n\nВведите адрес кошелька {crypto_symbol} (например: bc1qtssazvfvm8hzksmjfa0eta9qf3kctyk0zsyr8u):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_type")]])
    )

@dp.callback_query(F.data == "admin_back_to_type")
async def admin_back_to_type_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    data = await state.get_data()
    crypto = data.get("crypto")
    crypto_name = crypto_info.get(crypto, {}).get('name', crypto)
    await state.set_state(AdminState.waiting_type)
    await callback.message.edit_text(
        f"Настройка реквизитов для {crypto_name}\n\nВыберите, что хотите настроить:",
        reply_markup=get_admin_type_keyboard()
    )

@dp.callback_query(F.data == "admin_back_to_crypto")
async def admin_back_to_crypto_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(AdminState.waiting_crypto)
    await callback.message.edit_text(
        "Выберите криптовалюту для настройки реквизитов:",
        reply_markup=get_admin_keyboard()
    )

@dp.callback_query(F.data == "admin_back")
async def admin_back_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    await state.clear()
    await callback.message.delete()

@dp.callback_query(F.data == "admin_back_to_bank")
async def admin_back_to_bank_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    data = await state.get_data()
    country = data.get("country", "russia")
    await state.set_state(AdminState.waiting_bank)
    if country == "belarus":
        await callback.message.edit_text(
            "Введите номер карты для Беларуси (например: 2204 3206 0905 0531):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_country")]])
        )
    else:
        await callback.message.edit_text(
            "Введите номер карты для России (например: 2204 3206 0905 0531):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="admin_back_to_country")]])
        )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

