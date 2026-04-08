import random

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.settings import get_operator
from db.user import add_user
from runtime_state import get_runtime_state

router = Router()

FRUITS_CAPTCHA = {
    "banana": "🍌",
    "apple": "🍎",
    "orange": "🍊",
    "grape": "🍇",
    "watermelon": "🍉",
    "strawberry": "🍓",
}

user_captcha_passed = {}
user_correct_fruit = {}

async def send_captcha(message: types.Message):
    correct_fruit_key = random.choice(list(FRUITS_CAPTCHA.keys()))
    user_correct_fruit[message.from_user.id] = correct_fruit_key

    kb = InlineKeyboardBuilder()

    all_fruits = list(FRUITS_CAPTCHA.items())
    random.shuffle(all_fruits)

    for fruit_key, fruit_text in all_fruits:
        kb.button(text=fruit_text, callback_data=f"captcha_{fruit_key}")

    kb.adjust(3)

    user = message.from_user
    name = f"@{user.username}" if user.username else user.first_name

    correct_fruit_text = FRUITS_CAPTCHA[correct_fruit_key]
    caption = f"👋 Привет {name}!\n\nВыбери {correct_fruit_text} <b>({correct_fruit_key})</b>"

    await message.answer(caption, reply_markup=kb.as_markup())

async def send_start(message: types.Message, edit: bool = False):
    user_id = message.from_user.id

    await add_user(user_id)

    # Get runtime state for dynamic links
    state = get_runtime_state()

    operator = await get_operator()
    support_link = state.SUPPORT or operator
    reviews_link = state.REVIEWS or state.OTZIVY

    kb = InlineKeyboardBuilder()
    kb.button(text="Ваш кошелёк", callback_data="wallet")
    kb.button(text="Купить", callback_data="buy")
    kb.button(text="Продать", callback_data="sell")
    kb.button(text="Обмен крипта - на крипту", callback_data="exchange")
    kb.button(text="О сервисе❓", callback_data="about")
    kb.button(text="Калькульятор валют", callback_data="calculator")
    kb.button(text="Оставить отзыв", callback_data="review")
    kb.button(text="Как сделать обмен?", callback_data="how_to_exchange")
    kb.button(text="Личный кабинет", callback_data="profile")
    kb.button(text="Актуальные курсы", callback_data="rates")
    kb.button(text="Новости", url=f"https://t.me/{state.NEWS or ''}")
    kb.adjust(1, 2, 1, 2, 2, 2, 1)


    caption = (
        f"Привет! Меня зовут Горняк, и я проведу тебя в мир криптовалют ⛏\n\n"
        f"Это <b>{state.BOT_NAME}</b> — сервис обмена RUB на BTC/LTC/ETH/USDT и наоборот 💰\n\n"
        "Каждый 10-ый обмен без комиссии! (только для обменов до 25 000 р)\n\n"
        "Чтобы совершить операцию, жми кнопку \"Купить\"/\"Продать\". Выбирай нужную криптовалюту и вводи сумму. Готово!\n\n"
        f'<a href="https://t.me/{reviews_link}">📖 Отзывы наших клиентов</a>\n\n'
        f"🔔 Тех. поддержка, оператор 24/7: @{support_link}"
    )

    if edit:
        await message.edit_media(
            media=types.InputMediaPhoto(
                media=FSInputFile("media/start.jpg"),
                caption=caption
            ),
            reply_markup=kb.as_markup()
        )
    else:
        await message.answer_photo(
            photo=FSInputFile("media/start.jpg"),
            caption=caption,
            reply_markup=kb.as_markup()
        )

@router.message(Command("start"))
async def start_with_check(message: Message):
    user_id = message.from_user.id

    if user_id in user_captcha_passed and user_captcha_passed[user_id]:
        await send_start(message)
    else:
        await send_captcha(message)

@router.callback_query(F.data.startswith("captcha_"))
async def process_captcha(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    selected_fruit = callback.data.replace("captcha_", "")

    correct_fruit = user_correct_fruit.get(user_id)

    if correct_fruit and selected_fruit == correct_fruit:
        user_captcha_passed[user_id] = True

        message = callback.message
        if not isinstance(message, types.Message):
            await callback.answer()
            return

        await message.delete()
        await send_start(message)
        await callback.answer("✅ Проверка пройдена успешно!")
    else:
        await callback.answer("❌ Неверный выбор! Попробуйте еще раз.", show_alert=True)
