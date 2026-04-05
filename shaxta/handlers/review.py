from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, InputMediaPhoto

router = Router()

class ReviewStates(StatesGroup):
    waiting_for_review = State()

@router.callback_query(F.data.startswith("review"))
async def review_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="back")
        kb.adjust(1)

        caption = "Напишите Ваш отзыв."
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/review.jpg"),
                    caption=caption
                ),
                reply_markup=kb.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/review.jpg"),
                caption=caption,
                reply_markup=kb.as_markup()
            )
        
        await state.set_state(ReviewStates.waiting_for_review)
        await callback.answer()
        
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [review_handler]: {e}")

@router.message(ReviewStates.waiting_for_review)
async def process_review(message: types.Message, state: FSMContext):
    try:

        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="menu")
        kb.adjust(1)

        await message.answer("Спасибо за ваш отзыв!", reply_markup=kb.as_markup())
        await state.clear()
    except Exception as e:
        print(f"Ошибка на [process_review]: {e}")
