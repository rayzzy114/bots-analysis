from aiogram import F, Router, types
from aiogram.types import FSInputFile, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.settings import get_commission
from utils.exchange_rates import exchange_rates

router = Router()


async def _render_rates(callback: types.CallbackQuery, force_refresh: bool = False):
    commission = await get_commission()
    rates = await exchange_rates.get_trade_rates(
        commission,
        force_update=force_refresh,
        max_age_seconds=120,
    )

    return (
        "<b>Актуальные курсы:</b>\n\n"
        f"💰 <b>BTC</b>\n"
        f"Покупка: {rates['BTC']['buy']:,.2f} RUB\n"
        f"Продажа: {rates['BTC']['sell']:,.2f} RUB\n\n"
        f"💰 <b>LTC</b>\n"
        f"Покупка: {rates['LTC']['buy']:,.2f} RUB\n"
        f"Продажа: {rates['LTC']['sell']:,.2f} RUB\n\n"
        f"💰 <b>ETH</b>\n"
        f"Покупка: {rates['ETH']['buy']:,.2f} RUB\n"
        f"Продажа: {rates['ETH']['sell']:,.2f} RUB\n\n"
        f"💰 <b>USDT TRC</b>\n"
        f"Покупка: {rates['USDT']['buy']:,.2f} RUB\n"
        f"Продажа: {rates['USDT']['sell']:,.2f} RUB\n\n"
        f"Комиссия сервиса: <b>{commission:.2f}%</b>\n"
        f"Обновлено: <code>{exchange_rates.get_last_update_label()}</code>"
    )


@router.callback_query(F.data == "rates")
async def rates_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Обновить", callback_data="rates_refresh")
        kb.button(text="Назад", callback_data="back")
        kb.adjust(1)

        caption = await _render_rates(callback, force_refresh=False)
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/rates.jpg"),
                    caption=caption,
                ),
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/rates.jpg"),
                caption=caption,
                reply_markup=kb.as_markup(),
            )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [rates_handler]: {e}")


@router.callback_query(F.data == "rates_refresh")
async def refresh_rates_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Обновить", callback_data="rates_refresh")
        kb.button(text="Назад", callback_data="back")
        kb.adjust(1)

        caption = await _render_rates(callback, force_refresh=True)
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/rates.jpg"),
                    caption=caption,
                ),
                reply_markup=kb.as_markup(),
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/rates.jpg"),
                caption=caption,
                reply_markup=kb.as_markup(),
            )
        await callback.answer("Курсы обновлены")
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [refresh_rates_handler]: {e}")
