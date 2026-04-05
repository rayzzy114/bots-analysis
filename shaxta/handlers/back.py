from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

from handlers.start import send_start
#from db.user import is_user_banned

router = Router()

@router.callback_query(F.data == "back")
async def back_handler(callback: types.CallbackQuery, state: FSMContext):
    message = callback.message
    if not isinstance(message, types.Message):
        await callback.answer()
        return
    
    await callback.answer()
    await state.clear()
    await send_start(message, edit=True)

@router.callback_query(F.data == "menu")
async def menu_handler(callback: types.CallbackQuery, state: FSMContext):
    message = callback.message
    if not isinstance(message, types.Message):
        await callback.answer()
        return
    
    await callback.answer()
    await state.clear()
    await send_start(message, edit=False)
