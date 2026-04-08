from aiogram import F, Router
from aiogram.types import Message

from config import OPERATOR_LINK

router = Router()

async def support(message: Message, edit: bool = False):

    msg = f"Чтобы получить поддержку - напишите оператору: @{OPERATOR_LINK}"

    if edit:
        await message.edit_text(msg)
    else:
        await message.answer(msg)

@router.message(F.text == "👩🏻‍💻 Тех. Поддержка")
async def support_handler(message: Message):
    await support(message)
