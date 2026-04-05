from aiogram import Router, F
from aiogram.types import Message

from config import OPERATOR_LINK, SKUPKA
from utils.valute import get_commission_rate

router = Router()

async def sell_btc_xmr(message: Message, edit: bool = False):
    commission_rate = get_commission_rate()
    commission_percent = commission_rate * 100
    
    msg = ("❗ Попробуй наш новый автоматизированный сервис по скупке BTC\n"
           "❗ Выплаты производятся строго после получения 1 подтверждения сети\n"
           f"Комиссия: {commission_percent:.1f}%\n"
           f"Бот по скупке: @{SKUPKA}\n"
           f"Оператор: @{OPERATOR_LINK}")
    
    if edit:
        await message.edit_text(msg)
    else:
        await message.answer(msg)

@router.message(F.text == "💰 Продать BTC/XMR")
async def sell_btc_handler(message: Message):
    await sell_btc_xmr(message)