import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import FileCache
from core.config import Config

router = Router()

async def get_cached_file_id(session: AsyncSession, key: str):
    result = await session.execute(select(FileCache).where(FileCache.key == key))
    cached = result.scalar_one_or_none()
    return cached.file_id if cached else None

async def save_file_id(session: AsyncSession, key: str, file_id: str):
    session.add(FileCache(key=key, file_id=file_id))
    await session.commit()

@router.message(F.text == "Настройки")
@router.callback_query(F.data == "settings_main")
async def show_settings(message: Message | CallbackQuery, session: AsyncSession):
    if isinstance(message, CallbackQuery):
        actual_message = message.message
        await message.answer()
        if actual_message and hasattr(actual_message, 'delete'):
            await actual_message.delete()
    else:
        actual_message = message

    if not actual_message:
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🇷🇺 Ru", callback_data="lang_ru"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    video_path = os.path.join(Config.BASE_DIR, "assets", "settings.mp4")
    file_id = await get_cached_file_id(session, "settings_gif")

    try:
        sent_msg = await actual_message.answer_animation(animation=file_id or FSInputFile(video_path), caption="<b>Настройки</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        if not file_id and sent_msg and hasattr(sent_msg, 'animation') and sent_msg.animation:
            await save_file_id(session, "settings_gif", sent_msg.animation.file_id)
    except Exception:
        await actual_message.answer_animation(animation=FSInputFile(video_path), caption="<b>Настройки</b>", reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "merchant_mode")
async def toggle_merchant(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("Merchant Mode временно недоступен", show_alert=True)

@router.callback_query(F.data.startswith("lang_"))
async def set_lang(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("Язык изменен на RU", show_alert=False)