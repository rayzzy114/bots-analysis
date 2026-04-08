from aiogram import F, Router, types

from runtime_state import get_runtime_state

router = Router()

@router.callback_query(F.data.startswith("promo"))
async def promo_crypto_handler(callback: types.CallbackQuery):
    state = get_runtime_state()

    text = (
        f"Вы не используете промокод в настоящее время.\n\n\n"
        f"Напишите боту промокод, чтобы активировать его!\n\n\n"
        f"Собирать промокоды на одном аккаунте ЗАПРЕЩЕНО!\n\n\n"
        f"""Если ты "новичок" и хочешь получить промокод на скидку? - пиши мне @{state.operator} или @{state.operator2} или @{state.operator3}"""
    )

    await callback.message.answer(
        text
    )
    await callback.answer()
