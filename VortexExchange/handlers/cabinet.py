from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

async def cabinet(message: Message, edit: bool = False):

    kb = InlineKeyboardBuilder()
    kb.button(text="Вывести реф. заработок", callback_data="referral_earnings")
    kb.adjust(1)

    bot = message.bot
    bot_info = await bot.get_me()

    msg = "========================\n" \
            f"Telegram id: {message.from_user.id}\n" \
            f"Юзернейм: {message.from_user.username}\n" \
            "Количество сделок: 0\n" \
            "Личная скидка: 0%\n\n" \
            "Рефералов: 0 чел.\n" \
            "Накопленный заработок с рефералов:  0 руб.\n" \
            "Выведено за все время: 0 руб.\n\n" \
            f"Реферальная ссылка: https://t.me/{bot_info.username}?start={message.from_user.id}\n" \
            "========================"
    
    if edit:
        await message.edit_text(msg, reply_markup=kb.as_markup())
    else:
        await message.answer(msg, reply_markup=kb.as_markup())

@router.message(F.text == "🏠 Личный кабинет")
async def cabinet_handler(message: Message):
    await cabinet(message)

@router.callback_query(F.data == "referral_earnings")
async def referral_earnings_handler(callback: CallbackQuery):
    msg = "Логика не готова."
    await callback.message.answer(msg)
    await callback.answer()