from aiogram import Router, types, F

from config import operator, operator2, operator3

router = Router()

@router.callback_query(F.data.startswith("promo"))
async def promo_crypto_handler(callback: types.CallbackQuery):
    
    text = (
        f"Вы не используете промокод в настоящее время.\n\n\n"
        f"Напишите боту промокод, чтобы активировать его!\n\n\n"
        f"Собирать промокоды на одном аккаунте ЗАПРЕЩЕНО!\n\n\n"
        f"""Если ты "новичок" и хочешь получить промокод на скидку? - пиши мне @{operator} или @{operator2} или @{operator3}"""
    )

    await callback.message.answer(
        text
    )
    await callback.answer()