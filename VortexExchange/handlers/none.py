from aiogram import Router, F
from aiogram.types import CallbackQuery

router = Router()

@router.callback_query(F.data.startswith("none"))
async def nothing(callback: CallbackQuery):
    await callback.answer()