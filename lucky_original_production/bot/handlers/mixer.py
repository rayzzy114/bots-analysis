import os
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import FileCache
from core.config import Config

router = Router()

class MixerSG(StatesGroup):
    choosing_give = State()
    entering_amount = State()
    entering_address = State()
    confirming = State()

async def get_cached_file_id(session: AsyncSession, key: str):
    result = await session.execute(select(FileCache).where(FileCache.key == key))
    cached = result.scalar_one_or_none()
    return cached.file_id if cached else None

async def save_file_id(session: AsyncSession, key: str, file_id: str):
    session.add(FileCache(key=key, file_id=file_id))
    await session.commit()

@router.callback_query(F.data == "clean_main")
async def show_mixer(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.message:
        await callback.message.delete()
    await state.clear()

    video_path = os.path.join(Config.BASE_DIR, "assets", "animation_clean.mp4")
    file_id = await get_cached_file_id(session, "clean_gif")
    file_to_send = file_id if file_id else FSInputFile(video_path)

    text = "<b>Крипто-Миксер 🌪</b>\n\nВыберите валюту, которую вы хотите очистить:"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="BTC", callback_data="mixer_give_BTC"))
    builder.row(InlineKeyboardButton(text="USDT", callback_data="mixer_give_USDT"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))

    try:
        sent_msg = await callback.message.answer_animation(
            animation=file_to_send,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        if not file_id and sent_msg and hasattr(sent_msg, 'animation') and sent_msg.animation:
            await save_file_id(session, "clean_gif", sent_msg.animation.file_id)
    except Exception:
        sent_msg = await callback.message.answer_animation(
            animation=FSInputFile(video_path),
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        if sent_msg and hasattr(sent_msg, 'animation') and sent_msg.animation:
            await session.execute(update(FileCache).where(FileCache.key == "clean_gif").values(file_id=sent_msg.animation.file_id))
            await session.commit()
    
    await callback.answer()

@router.callback_query(F.data.startswith("mixer_give_"))
async def process_mixer_give(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.split("_")[2]
    await state.update_data(give_currency=currency)
    await callback.message.edit_caption(caption=f"<b>Очистка {currency}</b>\n\nВведите сумму, которую вы отправите в миксер:", parse_mode="HTML")
    await state.set_state(MixerSG.entering_amount)
    await callback.answer()

@router.message(MixerSG.entering_amount)
async def process_mixer_amount(message: Message, state: FSMContext):
    if not message.text: return
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount <= 0: raise ValueError
        await state.update_data(amount=amount)
        await message.answer(f"✅ Сумма <b>{amount}</b> принята.\n\nТеперь введите <b>адрес кошелька</b>, на который вы хотите получить чистые монеты:", parse_mode="HTML")
        await state.set_state(MixerSG.entering_address)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число (например, 0.5).")

@router.message(MixerSG.entering_address)
async def process_mixer_address(message: Message, state: FSMContext):
    if not message.text: return
    address = message.text.strip()
    
    # Базовая валидация адреса
    if len(address) < 25 or not re.match(r"^[a-zA-Z0-9]+$", address):
        await message.answer("⚠️ <b>Некорректный адрес!</b>\n\nПожалуйста, проверьте и введите правильный адрес вашего кошелька:", parse_mode="HTML")
        return

    await state.update_data(address=address)
    data = await state.get_data()
    
    text = f"""🌪 <b>Подтверждение очистки:</b>

📥 <b>Вы отдаете:</b> {data['amount']} {data['give_currency']}
📤 <b>Вы получаете:</b> {data['amount'] * 0.97:.6f} {data['give_currency']} (Чистые)
🛡 <b>Комиссия миксера:</b> 3%
📍 <b>Адрес зачисления:</b> <code>{address}</code>

Все данные верны?"""

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💎 Подтвердить", callback_data="mixer_confirm"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main"))
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(MixerSG.confirming)

@router.callback_query(MixerSG.confirming, F.data == "mixer_confirm")
async def mixer_final(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.get_data()
    # Тут можно добавить логику создания заказа в БД для миксера
    await callback.message.answer("🚀 <b>Заявка принята!</b>\n\nВ ближайшее время вам будут отправлены реквизиты для перевода монет в миксер.", parse_mode="HTML")
    await state.clear()
    await callback.answer()
