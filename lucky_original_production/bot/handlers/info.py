import os
import logging
import html
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User, Order, FileCache, Setting
from bot.utils.support import normalize_support
from core.config import Config

router = Router()

async def get_cached_file_id(session: AsyncSession, key: str):
    result = await session.execute(select(FileCache).where(FileCache.key == key))
    cached = result.scalar_one_or_none()
    return cached.file_id if cached else None

async def save_file_id(session: AsyncSession, key: str, file_id: str):
    session.add(FileCache(key=key, file_id=file_id))
    await session.commit()

async def get_app_setting(session: AsyncSession, key: str, default: str):
    res = await session.execute(select(Setting).where(Setting.key == key))
    setting = res.scalar_one_or_none()
    return setting.value if setting else default

async def get_support_contact(session: AsyncSession) -> tuple[str, str]:
    value = await get_app_setting(session, "link_support", "")
    if not value:
        value = await get_app_setting(session, "support_username", "luckyexchangesupport")
    return normalize_support(value)

@router.message(F.text == "О сервисе")
@router.callback_query(F.data == "about_main")
async def show_about(message: Message | CallbackQuery, session: AsyncSession):
    # Определяем сообщение, на которое будем отвечать
    if isinstance(message, CallbackQuery):
        actual_message = message.message
        await message.answer()
        if actual_message and hasattr(actual_message, 'delete'):
            await actual_message.delete()
    else:
        actual_message = message

    if not actual_message:
        return

    support_username, support_url = await get_support_contact(session)
    text = f"""☘️ <b>Lucky Exchange</b> — надежный сервис обмена криптовалют, работающий с 2024 года на рынке СНГ.

🔒 <b>Безопасность:</b> мы используем передовые технологии шифрования.
🌐 <b>API 24/7:</b> подключите наш сервис к своим платформам.

Свяжитесь с нами: @{support_username}"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛠 Связаться с поддержкой", url=support_url))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    photo_path = os.path.join(Config.BASE_DIR, "assets", "about_service.jpg")
    await actual_message.answer_photo(photo=FSInputFile(photo_path), caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(F.text == "Правила")
@router.callback_query(F.data == "rules_main")
async def show_rules(message: Message | CallbackQuery, session: AsyncSession):
    if isinstance(message, CallbackQuery):
        actual_message = message.message
        await message.answer()
        if actual_message and hasattr(actual_message, 'delete'):
            await actual_message.delete()
    else:
        actual_message = message

    if not actual_message:
        return

    support_username, _ = await get_support_contact(session)
    text = build_rules_text("1", support_username)
    video_path = os.path.join(Config.BASE_DIR, "assets", "animation_rules.mp4")
    file_id = await get_cached_file_id(session, "rules_gif")
    file_to_send = file_id if file_id else FSInputFile(video_path)

    try:
        sent_msg = await actual_message.answer_animation(animation=file_to_send, caption=text, reply_markup=get_rules_keyboard(), parse_mode="HTML")
        if not file_id and sent_msg and hasattr(sent_msg, 'animation') and sent_msg.animation:
            await save_file_id(session, "rules_gif", sent_msg.animation.file_id)
    except Exception:
        sent_msg = await actual_message.answer_animation(animation=FSInputFile(video_path), caption=text, reply_markup=get_rules_keyboard(), parse_mode="HTML")
        if sent_msg and hasattr(sent_msg, 'animation') and sent_msg.animation:
            await session.execute(update(FileCache).where(FileCache.key == "rules_gif").values(file_id=sent_msg.animation.file_id))
            await session.commit()

RULES_TEXTS = {"1": "Правила сервиса...", "2": "Гарантии..."}

def build_rules_text(section_id: str, support_username: str) -> str:
    return RULES_TEXTS.get(section_id, "Информация отсутствует.").format(support=support_username)

def get_rules_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))
    return builder.as_markup()

@router.message(F.text == "Мои заказы")
@router.callback_query(F.data == "orders_main")
async def show_orders(message: Message | CallbackQuery, session: AsyncSession):
    if isinstance(message, CallbackQuery):
        actual_message = message.message
        user_id = message.from_user.id
        await message.answer()
        if actual_message and hasattr(actual_message, 'delete'):
            await actual_message.delete()
    else:
        actual_message = message
        user_id = message.from_user.id

    if not actual_message:
        return

    result = await session.execute(select(Order).join(User).where(User.telegram_id == user_id).limit(5))
    orders = result.scalars().all()
    if not orders:
        await actual_message.answer("У вас пока нет заказов.")
        return

    video_path = os.path.join(Config.BASE_DIR, "assets", "animation_myorders.mp4")
    file_id = await get_cached_file_id(session, "orders_gif")
    await actual_message.answer_animation(animation=file_id or FSInputFile(video_path), caption="Ваши заказы:")