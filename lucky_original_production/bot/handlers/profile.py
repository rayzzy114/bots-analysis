from aiogram import Router, F

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User

from aiogram.utils.keyboard import InlineKeyboardBuilder


router = Router()


@router.callback_query(F.data == "deposit")

async def cmd_deposit(callback: CallbackQuery):

    await callback.answer("Пополнение баланса временно недоступно.", show_alert=True)


@router.callback_query(F.data == "withdraw")

async def cmd_withdraw(callback: CallbackQuery):

    await callback.answer("Недостаточно средств для вывода.", show_alert=True)


@router.callback_query(F.data == "promocodes")

async def cmd_promocodes(callback: CallbackQuery):

    await callback.answer("У вас нет активных промокодов.", show_alert=True)


@router.callback_query(F.data == "referral_info")

async def cmd_referral(callback: CallbackQuery, session: AsyncSession):

    result = await session.execute(select(User).where(User.telegram_id == callback.from_user.id))

    user = result.scalar_one()


    bot_info = await callback.bot.get_me()

    ref_link = f"https://t.me/{bot_info.username}?start={user.referral_code}"


    text = (

        "<b>🤝 Реферальная программа</b>\n\n"

        f"Ваша ссылка:\n<code>{ref_link}</code>\n\n"

        "Приглашайте друзей и получайте % от их обменов!"

    )


    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))


    await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")

    await callback.answer()

