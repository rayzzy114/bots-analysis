import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InlineQueryResultArticle, InputTextMessageContent
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "@expresschanger_support_bot")
REVIEWS_USERNAME = os.getenv("REVIEWS_USERNAME", "@expresschanger_reviews")
REVIEWS_LINK = os.getenv("REVIEWS_LINK", "https://t.me/mind_reviews")
CHAT_LINK = os.getenv("CHAT_LINK", "https://t.me/+CDOg2IpoaL43ZmM0")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

from src.handlers.transaction.buy import buy_router
from src.handlers.admin.admin import router as admin_router
from src.handlers.admin.orders import admin_orders_router
from src.handlers.user.promocodes import promocodes_router
from src.utils.manager import manager
from src.db.settings import init_settings_db

async def init_bot():
    await init_settings_db()

dp.include_router(admin_router)
dp.include_router(buy_router)
dp.include_router(admin_orders_router)
dp.include_router(promocodes_router)

def get_main_menu_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💸 Купить", callback_data="buy")],
            [
                InlineKeyboardButton(text="💰 Продать", callback_data="sell"),
                InlineKeyboardButton(text="💷 Миксер", callback_data="mixer")
            ],
            [
                InlineKeyboardButton(text="О сервисе", callback_data="about"),
                InlineKeyboardButton(text="Как совершить обмен?", callback_data="how_to_exchange")
            ],
            [InlineKeyboardButton(text="📖 Прочее", callback_data="other")]
        ]
    )

FIRST_START_TEXT = """🎉 Поздравляем! 🎉

✅ Купон успешно активирован!

🎫 Промокод: EXPRESS
💰 Скидка: 1000₽

Теперь к вашему обмену будут применены:
💌 WELCOME — скидка 300₽
💎 EXPRESS — 1000₽

Итого скидка: 1300₽

Промокод автоматически применен к вашему аккаунту! 🎁"""


@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    from src.db.settings import add_user
    from src.handlers.user.promocodes import user_promo_codes

    await state.clear()
    await manager.delete_main_menu(message.chat.id)
    user_id = message.from_user.id
    is_new = await add_user(user_id)

    if is_new:
        await message.answer(FIRST_START_TEXT)
        user_promo_codes[user_id] = ["WELCOME", "EXPRESS"]

    text2 = f"""<b>Добро пожаловать в Express Changer!</b>

Обменивайте RUB на BTC, LTC или XMR — быстро, удобно и безопасно.

Чтобы купить криптовалюту — нажмите <b>«💸 Купить»</b>
Чтобы продать криптовалюту — нажмите <b>«💰 Продать»</b>
Для анонимного микширования — <b>«💷 Миксер»</b>

Просто выберите монету, укажите сумму — и бот выполнит операцию автоматически.

📢 Отзывы пользователей: <b><a href="{REVIEWS_LINK}">{REVIEWS_USERNAME}</a></b>
🛎 Поддержка 24/7: <b>{OPERATOR_USERNAME}</b>
💬 <b>Наш чат:</b> <b>{CHAT_LINK}</b>

✨ Быстрое выполнение и бонусы при первом обмене!"""
    
    new_message = await message.answer(text2, reply_markup=get_main_menu_keyboard(), disable_web_page_preview=True)
    await manager.set_message(message.chat.id, new_message)

@dp.callback_query(F.data == "how_to_exchange")
async def how_to_exchange_handler(callback: CallbackQuery):
    text = f"""<b>Как сделать обмен?</b>

<b>Покупка криптовалюты</b>
1.Для покупки криптовалюты  в сплывающем окне нажмите кнопку «💸 Купить»
2.В сплывающем окне выберите валюту для покупки и нажмите на соответствующую кнопку:BTC,LTC,XMR
3.Далее,в сплывающем окне нажмите «ОПЛАТА ЛЮБОЙ КАРТОЙ»
4.После нажатия кнопки «ОПЛАТА ЛЮБОЙ КАРТОЙ» Вы увидите всплывающее окно с текущим курсом.
5.Проверив курс валюты,введите количество монет,сколько хотите купить,в строку «ОТПРАВИТЬ СООБЩЕНИЕ»,после чего нажмите  значек «ОТПРАВИТЬ».
6.Появится сообщение «ВВЕДИТЕ АДРЕС  ПОЛУЧЕНИЯ»,после этого введите реквизиты кошелька,куда бы вы хотели получить средства и нажмите  кнопку «ОТПРАВИТЬ»
7.Появится всплывающее окно, оплатите  сумму покупки и нажмите кнопку «ОПЛАТИЛ»
8.После оплаты ожидайте поступления средств на указанный вами кошелек.Средства поступают в течение 20-40 минут,что связано с техническим процессом.

<b>Продажа криптовалюты</b>
Для продажи свяжитесь со специалистом поддержки {OPERATOR_USERNAME}."""
    
    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")]
        ]
    )
    
    await callback.message.answer(text, reply_markup=back_keyboard, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about_handler(callback: CallbackQuery):
    text = """Express Changer: создаем приятные впечатления от обмена и пополнения в кошельке!

🔵 Быстрый обмен
❤️ Низкая комиссия
⚙️ Тех.поддержка 24/7
🔵 Анонимность обмена
🔵 Реальные отзывы клиентов
🟢 Ведем новостной канал

На связи
❤️  Обрабатываем 100% обращений
💝 Рассматриваем ошибки в платежах, в течение 48 часов от совершения обмена

Express Changer: сервис безопасного обмена криптоактивами. Удерживаем низкие ставки и высокую скорость обмена, как результат нашей ежедневной работы и постоянного технического совершенствования"""
    
    back_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")]
        ]
    )
    
    await callback.message.answer(text, reply_markup=back_keyboard, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "other")
async def other_handler(callback: CallbackQuery):
    other_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="☎️ Связь с оператором", url=f"https://t.me/{OPERATOR_USERNAME.replace('@', '')}"),
                InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocodes")
            ],
            [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")]
        ]
    )
    
    await callback.message.edit_reply_markup(reply_markup=other_keyboard)
    await callback.answer()

@dp.callback_query(F.data == "promocodes")
async def promocodes_handler(callback: CallbackQuery, state):
    from src.states.transaction import PromoCodeState
    await state.set_state(PromoCodeState.waiting_code)
    text = """✨ Ваши активные промокоды ✨
💌 <b>WELCOME</b> — скидка 300₽
💎 <b>EXPRESS</b> — скидка 1000₽

🚀 Чтобы применить новый промокод, просто отправьте его в чат и получите бонус мгновенно!"""
    
    await callback.message.answer(text, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def buy_handler(callback: CallbackQuery):
    await manager.delete_main_menu(callback.message.chat.id)
    text = "<b>🌍 Какую крипту хотите приобрести?</b>"
    
    buy_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Bitcoin (BTC)", callback_data="buy_btc")],
            [InlineKeyboardButton(text="🔶 Monero (XMR)", callback_data="buy_xmr")],
            [InlineKeyboardButton(text="🪙 Litecoin (LTC)", callback_data="buy_ltc")],
            [
                InlineKeyboardButton(text="🎟 Промокоды", callback_data="promocodes"),
                InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")
            ]
        ]
    )
    
    new_message = await callback.message.answer(text, reply_markup=buy_keyboard, disable_web_page_preview=True)
    await manager.set_message(callback.message.chat.id, new_message)
    await callback.answer()

@dp.callback_query(F.data == "sell")
async def sell_handler(callback: CallbackQuery):
    text = f"""💷 Для продажи криптовалюты свяжитесь с нашей поддержкой.
Мы поможем провести операцию быстро и безопасно!
🛎 {OPERATOR_USERNAME}"""
    
    await callback.message.answer(text, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "mixer")
async def mixer_handler(callback: CallbackQuery):
    text = f"""💷 Для использования миксера свяжитесь с нашей поддержкой.
Мы поможем провести операцию быстро и безопасно!
🛎 <b>{OPERATOR_USERNAME}</b>"""
    
    await callback.message.answer(text, disable_web_page_preview=True)
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery):
    text = f"""<b>Добро пожаловать в Express Changer!</b>

Обменивайте RUB на BTC, LTC или XMR — быстро, удобно и безопасно.

Чтобы купить криптовалюту — нажмите <b>«💸 Купить»</b>
Чтобы продать криптовалюту — нажмите <b>«💰 Продать»</b>
Для анонимного микширования — <b>«💷 Миксер»</b>

Просто выберите монету, укажите сумму — и бот выполнит операцию автоматически.

📢 Отзывы пользователей: <b><a href="{REVIEWS_LINK}">{REVIEWS_USERNAME}</a></b>
🛎 Поддержка 24/7: <b>{OPERATOR_USERNAME}</b>
💬 <b>Наш чат:</b> <b>{CHAT_LINK}</b>

✨ Быстрое выполнение и бонусы при первом обмене!"""
    
    await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), disable_web_page_preview=True)
    await callback.answer()

@dp.inline_query()
async def inline_calculator(inline_query: types.InlineQuery):
    query = inline_query.query.strip()
    
    currency = None
    amount = None
    
    if query.startswith("calc_"):
        parts = query.split(" ", 1)
        currency_part = parts[0].replace("calc_", "")
        if currency_part in ["btc", "xmr", "ltc"]:
            currency = currency_part
            if len(parts) > 1:
                try:
                    amount = float(parts[1].replace(",", "."))
                except ValueError:
                    pass
    else:
        for curr in ["btc", "xmr", "ltc"]:
            if f"calc_{curr}" in query or curr in query.lower():
                currency = curr
                break
        
        import re
        numbers = re.findall(r'\d+[.,]?\d*', query)
        if numbers:
            try:
                amount = float(numbers[0].replace(",", "."))
            except ValueError:
                pass
    
    if not currency:
        currency = "btc"
    
    from src.utils.rates import get_btc_rub_rate, get_ltc_rub_rate, get_xmr_rub_rate
    
    if currency == "btc":
        rate = await get_btc_rub_rate()
        currency_display = "BTC"
    elif currency == "xmr":
        rate = await get_xmr_rub_rate()
        currency_display = "XMR"
    elif currency == "ltc":
        rate = await get_ltc_rub_rate()
        currency_display = "LTC"
    else:
        rate = await get_btc_rub_rate()
        currency_display = "BTC"
    
    results = []
    
    if amount:
        rub_amount = amount * rate
        amount / rate
        
        result1_text = f"{amount} {currency_display} = {rub_amount:,.2f} ₽"
        result1 = InlineQueryResultArticle(
            id="1",
            title=result1_text,
            description=f"Текущий курс: 1 {currency_display} = {rate:,.2f} ₽",
            input_message_content=InputTextMessageContent(
                message_text=f"{amount} {currency_display} = {rub_amount:,.2f} ₽\n\nТекущий курс: 1 {currency_display} = {rate:,.2f} ₽"
            )
        )
        results.append(result1)
    else:
        result = InlineQueryResultArticle(
            id="1",
            title=f"Текущий курс: 1 {currency_display} = {rate:,.2f} ₽",
            description="Введите число для расчета",
            input_message_content=InputTextMessageContent(
                message_text=f"Текущий курс: 1 {currency_display} = {rate:,.2f} ₽"
            )
        )
        results.append(result)
    
    await inline_query.answer(results, cache_time=1)

async def main():
    await init_bot()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
