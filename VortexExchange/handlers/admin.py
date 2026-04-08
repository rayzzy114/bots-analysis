from aiogram import F, Router, types
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS, BOT_NAME
from handlers.start import send_start
from utils.database import (
    get_bank_details,
    get_commission,
    update_bank_detail,
    update_commission,
)
from utils.valute import BANK_DETAILS as DEFAULT_BANK_DETAILS

router = Router()

class AdminStates(StatesGroup):
    waiting_for_commission = State()
    waiting_for_card_details = State()
    waiting_for_sbp_details = State()
    waiting_for_sim_details = State()

async def send_admin(message: Message):
    user_id = message.from_user.id

    if user_id not in ADMIN_IDS:
        await send_start(message, user_id)
        return

    current_commission = get_commission()
    current_bank_details = get_bank_details()

    if not current_bank_details:
        current_bank_details = DEFAULT_BANK_DETAILS

    msg = f"<b>Панель администратора {BOT_NAME}!</b>\n\n"
    msg += f"Текущая комиссия: <code>{current_commission * 100}%</code>\n\n"
    msg += "💳 Текущие реквизиты:\n"

    for i, (bank_type, details) in enumerate(current_bank_details.items(), 1):
        short_details = details.get('details', '')[:50] + "..." if len(details.get('details', '')) > 50 else details.get('details', '')
        msg += f"{i}. {details.get('name', bank_type)}: <code>{short_details}</code>\n\n"

    msg += "Выберите действие из меню ниже:"

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Изменить Карту", callback_data="change_card")
    kb.button(text="🏧 Изменить СБП", callback_data="change_sbp")
    kb.button(text="📱 Изменить SIM", callback_data="change_sim")
    kb.button(text="💸 Комиссия %", callback_data="change_commission")
    kb.adjust(1)

    await message.answer(
        text=msg,
        reply_markup=kb.as_markup()
    )

@router.message(Command("admin"), F.chat.type == ChatType.PRIVATE)
async def admin_command_handler(message: types.Message):
    try:
        await send_admin(message)
    except Exception as e:
        print(f"[admin_command_handler error] {e}")

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin_handler(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    try:
        await callback.message.delete()
        await send_admin(callback.message)
    except Exception as e:
        print(f"[back_to_admin_handler error] {e}")
        await callback.answer("[back_to_admin_handler error]", show_alert=True)

@router.callback_query(F.data == "change_commission")
async def change_commission_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return

    current_commission = get_commission()

    await callback.message.edit_text(
        text=f"Текущая комиссия: <code>{current_commission * 100}%</code>\n\n"
             "Введите новое значение комиссии:",
        reply_markup=InlineKeyboardBuilder().button(text="↩️ Назад", callback_data="back_to_admin").as_markup()
    )

    await state.set_state(AdminStates.waiting_for_commission)

@router.callback_query(F.data.startswith("change_"))
async def change_bank_details_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        return

    action = callback.data
    current_bank_details = get_bank_details()

    if "card" in action:
        bank_type = "card"
        bank_name = current_bank_details.get("card", {}).get("name", "Банковская карта")
        current_details = current_bank_details.get("card", {}).get("details", "")
        await state.set_state(AdminStates.waiting_for_card_details)
    elif "sbp" in action:
        bank_type = "sbp"
        bank_name = current_bank_details.get("sbp", {}).get("name", "СБП")
        current_details = current_bank_details.get("sbp", {}).get("details", "")
        await state.set_state(AdminStates.waiting_for_sbp_details)
    elif "sim" in action:
        bank_type = "sim"
        bank_name = current_bank_details.get("sim", {}).get("name", "SIM")
        current_details = current_bank_details.get("sim", {}).get("details", "")
        await state.set_state(AdminStates.waiting_for_sim_details)
    else:
        return

    await state.update_data(bank_type=bank_type)

    await callback.message.edit_text(
        text=f"Изменение реквизитов: <b>{bank_name}</b>\n\n"
             f"Текущие реквизиты:\n<code>{current_details}</code>\n\n"
             "Введите новые реквизиты:",
        reply_markup=InlineKeyboardBuilder().button(text="↩️ Назад", callback_data="back_to_admin").as_markup()
    )

@router.message(AdminStates.waiting_for_commission)
async def process_commission_update(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        text = message.text.strip().replace(",", ".")

        if text.endswith('%'):
            text = text[:-1].strip()

        if not text:
            raise ValueError

        value = float(text)

        if value < 0 or value > 100:
            await message.answer("❌ Комиссия должна быть от 0% до 100%.\n\nВведите новое значение:")
            return

        new_commission = value / 100

        update_commission(new_commission)

        if value.is_integer():
            percent_display = f"{int(value)}"
        else:
            percent_display = f"{value:.2f}".rstrip('0').rstrip('.')

        await message.answer(f"✅ Комиссия успешно обновлена на <b>{percent_display}%</b>")
        await state.clear()
        await send_admin(message)

    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректный процент.\n\n"
            "Введите новое значение:"
        )

@router.message(AdminStates.waiting_for_card_details)
async def process_card_details_update(message: Message, state: FSMContext):
    await process_bank_details_update(message, state, "card")

@router.message(AdminStates.waiting_for_sbp_details)
async def process_sbp_details_update(message: Message, state: FSMContext):
    await process_bank_details_update(message, state, "sbp")

@router.message(AdminStates.waiting_for_sim_details)
async def process_sim_details_update(message: Message, state: FSMContext):
    await process_bank_details_update(message, state, "sim")

async def process_bank_details_update(message: Message, state: FSMContext, bank_type: str):
    if message.from_user.id not in ADMIN_IDS:
        return

    new_details = message.text.strip()

    if not new_details:
        await message.answer("❌ Реквизиты не могут быть пустыми.\n\nПопробуйте снова:")
        return

    success = update_bank_detail(bank_type, new_details)

    if success:
        await message.answer("✅ Реквизиты успешно обновлены!")
        await state.clear()
        await send_admin(message)
    else:
        await message.answer("❌ Ошибка при обновлении реквизитов.\n\nПопробуйте снова:")
