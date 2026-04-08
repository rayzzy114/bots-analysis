from aiogram import F, Router, types
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import REFERRAL_REWARD_PERCENT

router = Router()

@router.callback_query(F.data.startswith("profile"))
async def profile_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Отправить приглашение", switch_inline_query="invite")
        kb.button(text="Вывод", callback_data="withdraw")
        kb.button(text="Назад", callback_data="back")

        kb.adjust(1)

        bot_username = (await callback.bot.get_me()).username

        caption = (
            "<b>Ваш статус: Новичок\n\n</b>"
            "Количество успешных сделок: <b>0</b>\n\n"
            f"Приглашайте друзей и получайте <b>{REFERRAL_REWARD_PERCENT}</b> % от оборота с каждой сделки вашего друга.\n\n"
            "Вы пригласили <b>0 чел.</b>\n\n"
            "Текущий баланс: <b>0 руб.</b>\n\n"
            "Ссылка для приглашения:\n"
            f"t.me/{bot_username}?start={callback.from_user.id}"
        )
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/profile.jpg"),
                    caption=caption
                ),
                reply_markup=kb.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/profile.jpg"),
                caption=caption,
                reply_markup=kb.as_markup()
            )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [profile_handler]: {e}")
