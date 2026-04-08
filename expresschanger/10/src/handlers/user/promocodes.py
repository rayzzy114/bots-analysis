from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.states.transaction import PromoCodeState

promocodes_router = Router()

user_promo_codes = {}


@promocodes_router.message(PromoCodeState.waiting_code, F.text)
async def process_promo_code(message: Message, state: FSMContext):
    promo_code = message.text.strip().upper()
    valid_promo_codes = ["EXPRESS", "WELCOME"]

    if promo_code in valid_promo_codes:
        if message.from_user.id not in user_promo_codes:
            user_promo_codes[message.from_user.id] = []

        if promo_code not in user_promo_codes[message.from_user.id]:
            user_promo_codes[message.from_user.id].append(promo_code)
            await message.answer("✅ Промокод применен! Бонус будет применен при следующей покупке.")
        else:
            await message.answer("⚠️ Этот промокод уже применен")
        await state.clear()
    else:
        await message.answer("❌ Этот промокод не найден ❌")

