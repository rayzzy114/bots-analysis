from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import operator, rates, work_operator
from db.user import add_user

router = Router()


async def send_start(message: types.Message, edit: bool = False):
    user_id = message.from_user.id

    await add_user(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⚡ Купить LTC ⚡", callback_data="buy_ltc")
    kb.button(text="👥 Партнерская программа", callback_data="partner")
    kb.button(text="Поддержка / Оператор", url=f"https://t.me/{operator}")
    kb.button(text="Отзывы", url=f"https://t.me/{rates}")
    kb.button(text="💰РАБОТА💰", callback_data="work")
    kb.button(text="Правила", callback_data="rules")
    kb.adjust(1, 1, 2, 1, 1)

    caption = (
        "<b>Бот обменник</b>\n\n"
        "Тут ты можешь обменять свои <b>RUB</b> на <b>LTC</b>\n\n"
        'Жми кнопку "<b>👉🏻 Купить LTC 👈🏻</b>" или просто введи сумму в <b>RUB</b> или <b>LTC</b>\n\n'
        "<b>Пример</b>: 0.1 или 0,1 или 5030"
    )

    if edit:
        await message.edit_text(
            text=caption,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            text=caption,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )


@router.message(Command("start"))
async def start_with_check(message: types.Message, state: FSMContext):
    await state.clear()
    await send_start(message)


@router.callback_query(F.data == "back")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await send_start(callback.message)
    await callback.answer()


@router.callback_query(F.data == "work")
async def work_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="Главное меню", callback_data="back")
    kb.adjust(1)

    text = (
        "💵<b>РАБОТА МЕЧТЫ</b>\n\n"
        "Мы ищем людей, которые готовы помогать нам в обработке платежей. "
        "Работа на основе возвращаемого залога. Минимальная сумма залога от 15,000 рублей.\n\n"
        "💳Чем больше карт - тем больше ваш заработок!\n\n"
        "Воспользуйся возможностью и получи работу своей мечты! ⚡️\n\n"
        f"🔗Контакты : @{work_operator}"
    )

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()
