from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from handlers.start import send_start
#from db.user import is_user_banned

router = Router()

@router.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    await callback.answer()
    await state.clear()
    await send_start(callback.message, edit=True)

@router.callback_query(F.data == "menu")
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    await callback.answer()
    await state.clear()
    await send_start(callback.message, edit=False)