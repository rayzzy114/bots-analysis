from aiogram import F, Router, types
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.settings import get_operator
from runtime_state import get_runtime_state

router = Router()

@router.callback_query(F.data.startswith("about"))
async def about_handler(callback: types.CallbackQuery):
    try:
        # Get runtime state for dynamic links
        state = get_runtime_state()

        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="back")

        kb.adjust(1)

        operator = await get_operator()
        support_link = state.SUPPORT or operator
        reviews_link = state.REVIEWS or state.OTZIVY

        caption = (
            f"{state.BOT_NAME}: создаем приятные впечатления от обмена и пополнения в кошельке!\n\n"
            "🔵 Быстрый обмен\n"
            "❤️ Низкая комиссия\n"
            f'<a href="https://t.me/{support_link}">⚙️ Тех.поддержка 24/7</a>\n'
            "🔵 Анонимность обмена\n"
            f'<a href="https://t.me/{reviews_link}">🔵 Реальные отзывы клиентов</a>\n'
            f'<a href="https://t.me/{state.NEWS}">🟢 Ведем новостной канал</a>\n\n'
            "<b>На связи</b>\n"
            "❤️  Обрабатываем 100% обращений\n"
            "<i>💗 Рассматриваем ошибки в платежах, в течение 48 часов от совершения обмена</i>\n\n"
            f"<b>{state.BOT_NAME}: сервис безопасного обмена криптоактивами.</b>\n"
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
