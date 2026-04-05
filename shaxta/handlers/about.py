from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, InputMediaPhoto

from config import BOT_NAME, OTZIVY, NEWS, SUPPORT, REVIEWS

router = Router()

@router.callback_query(F.data.startswith("about"))
async def about_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="back")

        kb.adjust(1)

        operator = await get_operator()
        support_link = SUPPORT or operator
        reviews_link = REVIEWS or OTZIVY

        caption = (
            f"{BOT_NAME}: создаем приятные впечатления от обмена и пополнения в кошельке!\n\n"
            "🔵 Быстрый обмен\n"
            "❤️ Низкая комиссия\n"
            f'<a href="https://t.me/{support_link}">⚙️ Тех.поддержка 24/7</a>\n'
            "🔵 Анонимность обмена\n"
            f'<a href="https://t.me/{reviews_link}">🔵 Реальные отзывы клиентов</a>\n'
            f'<a href="https://t.me/{NEWS}">🟢 Ведем новостной канал</a>\n\n'
            "<b>На связи</b>\n"
            "❤️  Обрабатываем 100% обращений\n"
            "<i>💗 Рассматриваем ошибки в платежах, в течение 48 часов от совершения обмена</i>\n\n"
            f"<b>{BOT_NAME}: сервис безопасного обмена криптоактивами.</b>\n"
            "Удерживаем низкие ставки и высокую скорость обмена, как результат нашей ежедневной работы и постоянного технического совершенствования"
        )
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/about.jpg"),
                    caption=caption
                ),
                reply_markup=kb.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/about.jpg"),
                caption=caption,
                reply_markup=kb.as_markup()
            )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [about_handler]: {e}")
