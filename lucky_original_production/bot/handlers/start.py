import random

import string

import os

import html

from aiogram import Router, F

from aiogram.filters import CommandStart

from aiogram.types import Message, CallbackQuery, FSInputFile

from aiogram.fsm.context import FSMContext

import logging
from sqlalchemy import select, update

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User, FileCache, Setting

from bot.keyboards.main_kb import get_main_reply_kb, get_main_inline_kb, get_profile_kb


router = Router()


async def get_cached_file_id(session: AsyncSession, key: str):

    result = await session.execute(select(FileCache).where(FileCache.key == key))

    cached = result.scalar_one_or_none()

    return cached.file_id if cached else None


async def save_file_id(session: AsyncSession, key: str, file_id: str):

    session.add(FileCache(key=key, file_id=file_id))

    await session.commit()


async def get_links(session: AsyncSession):

    query = select(Setting).where(Setting.key.in_(["link_reviews", "link_news", "link_support"]))

    result = await session.execute(query)

    settings = result.scalars().all()

    return {s.key: s.value for s in settings}


def generate_referral_code(length=8):

    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


@router.message(CommandStart())

@router.message(F.text == "☘️ Главное меню")

async def cmd_start(message: Message, state: FSMContext, session: AsyncSession):

    if state:

        await state.clear()


    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))

    user = result.scalar_one_or_none()

    if not user:

        user = User(

            telegram_id=message.from_user.id,

            username=html.escape(message.from_user.username or "user"),

            referral_code=generate_referral_code()

        )

        session.add(user)

        await session.commit()


    await message.answer("☘️", reply_markup=get_main_reply_kb())


    links = await get_links(session)

    from core.config import Config
    video_path = os.path.join(Config.BASE_DIR, "assets", "animation_start.mp4")
    file_id = await get_cached_file_id(session, "start_gif")

    file_to_send = file_id if file_id else FSInputFile(video_path)


    sent_msg = None
    try:
        sent_msg = await message.answer_animation(
            animation=file_to_send,
            reply_markup=get_main_inline_kb(links),
        )
    except Exception as e:
        if file_id:
            logging.warning(f"Cached file_id for start_gif is invalid, retrying with file...")
            # Если упало на кэшированном id, пробуем отправить файл
            file_to_send = FSInputFile(video_path)
            sent_msg = await message.answer_animation(
                animation=file_to_send,
                reply_markup=get_main_inline_kb(links),
            )
            # Обновляем кэш новым ID
            await session.execute(update(FileCache).where(FileCache.key == "start_gif").values(file_id=sent_msg.animation.file_id))
            await session.commit()
        else:
            raise e


@router.callback_query(F.data == "profile_main")

async def callback_profile(callback: CallbackQuery, session: AsyncSession):

    await callback.message.delete()

    await show_profile(callback.message, session)

    await callback.answer()


@router.message(F.text == "Профиль")

async def show_profile(message: Message, session: AsyncSession):

    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))

    user = result.scalar_one_or_none()


    text = (f"Баланс: {user.balance} ₽\nОборот: 0.00 ₽\nMerchant Mode: 🔴 ВЫКЛ")

    from core.config import Config
    video_path = os.path.join(Config.BASE_DIR, "assets", "animation_profile.mp4")
    file_id = await get_cached_file_id(session, "profile_gif")

    file_to_send = file_id if file_id else FSInputFile(video_path)


    sent_msg = None
    try:
        sent_msg = await message.answer_animation(animation=file_to_send, caption=text, reply_markup=get_profile_kb())
    except Exception as e:
        if file_id:
            logging.warning(f"Cached file_id for profile_gif is invalid, retrying with file...")
            file_to_send = FSInputFile(video_path)
            sent_msg = await message.answer_animation(animation=file_to_send, caption=text, reply_markup=get_profile_kb())
            await session.execute(update(FileCache).where(FileCache.key == "profile_gif").values(file_id=sent_msg.animation.file_id))
            await session.commit()
        else:
            raise e


@router.callback_query(F.data == "back_to_main")

async def back_to_main(callback: CallbackQuery, state: FSMContext, session: AsyncSession):

    await callback.message.delete()

    await cmd_start(callback.message, state, session)

    await callback.answer()

