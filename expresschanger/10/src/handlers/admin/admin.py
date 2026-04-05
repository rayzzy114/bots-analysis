from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
import os
from dotenv import load_dotenv
from src.db.settings import (
    get_requisites, get_bank, update_requisites, update_bank,
    get_payment_methods, add_payment_method, remove_payment_method,
    get_btc_rates, get_commission, set_commission,
    get_requisites_mode, set_requisites_mode,
    update_method_requisites
)

load_dotenv()

router = Router()

ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminForm(StatesGroup):
    waiting_for_requisites = State()
    waiting_for_bank = State()
    waiting_for_new_method = State()
    waiting_for_commission = State()
    waiting_for_method_requisites = State()
    waiting_for_method_bank = State()


async def get_admin_panel_text(username: Optional[str]) -> str:
    requisites = await get_requisites()
    bank_name = await get_bank()
    methods = await get_payment_methods()
    rate_usd, rate_rub = await get_btc_rates()
    commission = await get_commission()
    mode = await get_requisites_mode()

    username_display = f"@{username}" if username else "администратор"
    mode_text = "🔘 Единые реквизиты" if mode == 0 else "🔘 Раздельные реквизиты"

    if mode == 0:
        methods_text = "\n".join([f"  • {m['name']}" for m in methods]) if methods else "  (пусто)"
    else:
        methods_lines = []
        for m in methods:
            req = m.get('requisites', '')
            bank_m = m.get('bank', '')
            if req:
                methods_lines.append(f"  • {m['name']}\n      Реки: {req}\n      Банк: {bank_m or '—'}")
            else:
                methods_lines.append(f"  • {m['name']} (реквизиты не заданы)")
        methods_text = "\n".join(methods_lines) if methods_lines else "  (пусто)"

    text = (
        f"👋 Добро пожаловать, {username_display}\n\n"
        f"├ Режим: <b>{mode_text}</b>\n"
    )

    if mode == 0:
        text += (
            f"├ Реквизиты: <code>{requisites}</code>\n"
            f"├ Банк: <code>{bank_name}</code>\n"
        )

    text += (
        f"├ Курс BTC: <b>${rate_usd:,.2f}</b> / <b>{rate_rub:,.2f} руб.</b> (авто)\n"
        f"├ Комиссия: <b>{commission}%</b>\n"
        f"╰ Способы оплаты:\n{methods_text}"
    )

    return text


def get_admin_keyboard(mode: int):
    kb = InlineKeyboardBuilder()

    if mode == 0:
        kb.button(text="🔄 Режим: Единые", callback_data="admin_toggle_mode")
        kb.button(text="✏️ Реки", callback_data="admin_change_requisites")
        kb.button(text="✏️ Банк", callback_data="admin_change_bank")
        kb.button(text="💵 Комиссия", callback_data="admin_change_commission")
        kb.button(text="➕ Способ оплаты", callback_data="admin_add_method")
        kb.button(text="➖ Удалить способ", callback_data="admin_remove_method")
        kb.button(text="🏠 Главное меню", callback_data="main_menu")
        kb.adjust(1, 2, 1, 2, 1)
    else:
        kb.button(text="🔄 Режим: Раздельные", callback_data="admin_toggle_mode")
        kb.button(text="✏️ Реки способов", callback_data="admin_edit_methods_req")
        kb.button(text="💵 Комиссия", callback_data="admin_change_commission")
        kb.button(text="➕ Способ оплаты", callback_data="admin_add_method")
        kb.button(text="➖ Удалить способ", callback_data="admin_remove_method")
        kb.button(text="🏠 Главное меню", callback_data="main_menu")
        kb.adjust(1, 1, 1, 2, 1)

    return kb.as_markup()


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(message.from_user.username)
    await message.answer(text, reply_markup=get_admin_keyboard(mode))


@router.callback_query(F.data == "admin_toggle_mode")
async def admin_toggle_mode(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    current_mode = await get_requisites_mode()
    new_mode = 1 if current_mode == 0 else 0
    await set_requisites_mode(new_mode)

    mode_name = "Единые реквизиты" if new_mode == 0 else "Раздельные реквизиты"
    await callback.answer(f"✅ Режим: {mode_name}")

    text = await get_admin_panel_text(callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(new_mode))


@router.callback_query(F.data == "admin_edit_methods_req")
async def admin_edit_methods_req(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    methods = await get_payment_methods()

    if not methods:
        await callback.answer("Нет способов оплаты", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for i, method in enumerate(methods):
        req = method.get('requisites', '')
        status = "✅" if req else "❌"
        kb.button(text=f"{status} {method['name']}", callback_data=f"admin_set_method_req_{i}")
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")
    kb.adjust(1)

    await callback.message.edit_text("Выберите способ оплаты для настройки реквизитов:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set_method_req_"))
async def admin_set_method_req(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    index = int(callback.data.split("_")[4])
    methods = await get_payment_methods()

    if index >= len(methods):
        await callback.answer("Способ не найден", show_alert=True)
        return

    method = methods[index]
    current_req = method.get('requisites', '')
    current_bank = method.get('bank', '')

    await state.update_data(editing_method_index=index)
    await state.set_state(AdminForm.waiting_for_method_requisites)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")

    await callback.message.edit_text(
        f"Способ: <b>{method['name']}</b>\n"
        f"Текущие реквизиты: <code>{current_req or '—'}</code>\n"
        f"Текущий банк: <code>{current_bank or '—'}</code>\n\n"
        f"╰ <i>Введите новые реквизиты:</i>",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(AdminForm.waiting_for_method_requisites)
async def process_method_requisites(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    new_requisites = message.text.strip()
    await state.update_data(new_method_requisites=new_requisites)
    await state.set_state(AdminForm.waiting_for_method_bank)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")

    await message.answer(
        f"Реквизиты: <code>{new_requisites}</code>\n\n"
        f"╰ <i>Теперь введите название банка:</i>",
        reply_markup=kb.as_markup()
    )
    await message.delete()


@router.message(AdminForm.waiting_for_method_bank)
async def process_method_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    index = data.get('editing_method_index')
    new_requisites = data.get('new_method_requisites', '')
    new_bank = message.text.strip()

    await update_method_requisites(index, new_requisites, new_bank)
    await state.clear()

    await message.answer("<b>✅ Реквизиты и банк обновлены!</b>")

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(message.from_user.username)
    await message.answer(text, reply_markup=get_admin_keyboard(mode))
    await message.delete()


@router.callback_query(F.data == "admin_change_requisites")
async def admin_change_requisites(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_requisites)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")

    await callback.message.edit_text("╰ <i>Введите новые реквизиты:</i>", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_change_bank")
async def admin_change_bank(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_bank)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")

    await callback.message.edit_text("╰ <i>Введите новое название банка:</i>", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data == "admin_change_commission")
async def admin_change_commission(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    commission = await get_commission()

    await state.set_state(AdminForm.waiting_for_commission)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")

    await callback.message.edit_text(
        f"Текущая комиссия: <b>{commission}%</b>\n\n"
        "╰ <i>Введите новую комиссию (число от 0 до 100):</i>",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(AdminForm.waiting_for_commission)
async def process_commission(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        commission = int(message.text.strip().replace(',', '.').replace('%', ''))
        if commission < 0 or commission > 100:
            await message.answer("❌ Комиссия должна быть от 0 до 100")
            return

        await set_commission(commission)
        await state.clear()

        await message.answer(f"<b>✅ Комиссия обновлена: {commission}%</b>")

        mode = await get_requisites_mode()
        text = await get_admin_panel_text(message.from_user.username)
        await message.answer(text, reply_markup=get_admin_keyboard(mode))
        await message.delete()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (например: 30)")


@router.callback_query(F.data == "admin_add_method")
async def admin_add_method(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_new_method)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")

    await callback.message.edit_text(
        "╰ <i>Введите название нового способа оплаты:</i>\n\n"
        "Например: 💳 СБП или Сбер ➡️ Сбер",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_remove_method")
async def admin_remove_method(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    methods = await get_payment_methods()

    if not methods:
        await callback.answer("Нет способов оплаты для удаления", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for i, method in enumerate(methods):
        kb.button(text=f"❌ {method['name']}", callback_data=f"admin_del_method_{i}")
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")
    kb.adjust(1)

    await callback.message.edit_text("Выберите способ оплаты для удаления:", reply_markup=kb.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del_method_"))
async def admin_delete_method(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    index = int(callback.data.split("_")[3])
    methods = await get_payment_methods()

    if 0 <= index < len(methods):
        removed = methods[index]['name']
        await remove_payment_method(index)
        await callback.answer(f"✅ Удалено: {removed}")

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(mode))


@router.message(AdminForm.waiting_for_requisites)
async def process_requisites(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await update_requisites(message.text.strip())
    await state.clear()

    await message.answer("<b>✅ Реквизиты обновлены!</b>")

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(message.from_user.username)
    await message.answer(text, reply_markup=get_admin_keyboard(mode))
    await message.delete()


@router.message(AdminForm.waiting_for_bank)
async def process_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await update_bank(message.text.strip())
    await state.clear()

    await message.answer("<b>✅ Банк обновлен!</b>")

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(message.from_user.username)
    await message.answer(text, reply_markup=get_admin_keyboard(mode))
    await message.delete()


@router.message(AdminForm.waiting_for_new_method)
async def process_new_method(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await add_payment_method(message.text.strip())
    await state.clear()

    await message.answer("<b>✅ Способ оплаты добавлен!</b>")

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(message.from_user.username)
    await message.answer(text, reply_markup=get_admin_keyboard(mode))
    await message.delete()


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    mode = await get_requisites_mode()
    text = await get_admin_panel_text(callback.from_user.username)
    await callback.message.edit_text(text, reply_markup=get_admin_keyboard(mode))
    await callback.answer()

