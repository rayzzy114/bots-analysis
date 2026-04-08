
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import is_admin
from db.settings import (
    get_bank,
    get_commission,
    get_operator,
    get_requisites,
    update_bank,
    update_commission,
    update_operator,
    update_requisites,
)
from utils.env_writer import read_env_var, update_env_var

router = Router()


class AdminForm(StatesGroup):
    waiting_for_requisites = State()
    waiting_for_bank = State()
    waiting_for_commission = State()
    waiting_for_operator = State()
    # Link states
    waiting_for_support = State()
    waiting_for_reviews = State()
    waiting_for_otzivy = State()
    waiting_for_news = State()


def build_admin_keyboard() -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Реквизиты", callback_data="admin_change_requisites")
    kb.button(text="✏️ Банк", callback_data="admin_change_bank")
    kb.button(text="✏️ Комиссия", callback_data="admin_change_commission")
    kb.button(text="✏️ Оператор", callback_data="admin_change_operator")
    kb.button(text="🔗 Ссылки", callback_data="admin_links")
    kb.button(text="🏠 Главное меню", callback_data="back")
    kb.adjust(2, 2, 1, 1)
    return kb


def get_admin_panel_text(username: str | None, requisites: str, bank: str, commission: float, operator: str) -> str:
    username_display = f"@{username}" if username else "администратор"
    return (
        f"👋 Добро пожаловать, администратор {username_display}\n\n"
        f"├ Текущие реквизиты: <code>{requisites}</code>\n"
        f"├ Текущий банк: <code>{bank}</code>\n"
        f"├ Текущая комиссия: <code>{commission:.2f}%</code>\n"
        f"╰ Текущий оператор: <code>@{operator}</code>"
    )


async def send_admin_panel(message: Message, username: str | None):
    requisites = await get_requisites()
    bank = await get_bank()
    commission = await get_commission()
    operator = await get_operator()
    text = get_admin_panel_text(username, requisites, bank, commission, operator)
    await message.answer(text, reply_markup=build_admin_keyboard().as_markup())


@router.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    current_state = await state.get_state()
    if current_state in [
        AdminForm.waiting_for_requisites,
        AdminForm.waiting_for_bank,
        AdminForm.waiting_for_commission,
        AdminForm.waiting_for_operator,
    ]:
        return

    await send_admin_panel(message, message.from_user.username)


@router.callback_query(F.data == "admin_change_requisites")
async def admin_change_requisites(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_requisites)
    await state.update_data(requisites_request_message_id=callback.message.message_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️", callback_data="admin_cancel")

    await callback.message.edit_text(
        "╰ <i>Введите новые реквизиты:</i>",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_bank")
async def admin_change_bank(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_bank)
    await state.update_data(bank_request_message_id=callback.message.message_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️", callback_data="admin_cancel")

    await callback.message.edit_text(
        "╰ <i>Введите новое название банка:</i>",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_commission")
async def admin_change_commission(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_commission)
    await state.update_data(commission_request_message_id=callback.message.message_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️", callback_data="admin_cancel")

    await callback.message.edit_text(
        "╰ <i>Введите новую комиссию в процентах (пример: 2 или 1.5):</i>",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_operator")
async def admin_change_operator(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminForm.waiting_for_operator)
    await state.update_data(operator_request_message_id=callback.message.message_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️", callback_data="admin_cancel")

    await callback.message.edit_text(
        "╰ <i>Введите username оператора (например: operator_name):</i>",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()


@router.message(AdminForm.waiting_for_requisites)
async def process_requisites(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    data = await state.get_data()
    new_requisites = message.text.strip()
    await update_requisites(new_requisites)

    if "requisites_request_message_id" in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data["requisites_request_message_id"],
            )
        except Exception as e:
            print(f'Exception caught: {e}')

    await state.clear()
    await message.answer("<b>✅ Реквизиты обновлены!</b>")
    await send_admin_panel(message, message.from_user.username)
    await message.delete()


@router.message(AdminForm.waiting_for_bank)
async def process_bank(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    data = await state.get_data()
    new_bank = message.text.strip()
    await update_bank(new_bank)

    if "bank_request_message_id" in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data["bank_request_message_id"],
            )
        except Exception as e:
            print(f'Exception caught: {e}')

    await state.clear()
    await message.answer("<b>✅ Название банка обновлено!</b>")
    await send_admin_panel(message, message.from_user.username)
    await message.delete()


@router.message(AdminForm.waiting_for_commission)
async def process_commission(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    data = await state.get_data()
    raw_value = message.text.strip().replace(",", ".")

    try:
        commission = float(raw_value)
    except ValueError:
        await message.answer("❌ Введите число, например: 2 или 1.5")
        return

    if commission < 0 or commission >= 100:
        await message.answer("❌ Допустимый диапазон комиссии: от 0 до 99.99")
        return

    await update_commission(commission)

    if "commission_request_message_id" in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data["commission_request_message_id"],
            )
        except Exception as e:
            print(f'Exception caught: {e}')

    await state.clear()
    await message.answer(f"<b>✅ Комиссия обновлена: {commission:.2f}%</b>")
    await send_admin_panel(message, message.from_user.username)
    await message.delete()


@router.message(AdminForm.waiting_for_operator)
async def process_operator(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещен")
        return

    data = await state.get_data()
    new_operator = message.text.strip().lstrip("@")
    await update_operator(new_operator)

    if "operator_request_message_id" in data:
        try:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=data["operator_request_message_id"],
            )
        except Exception as e:
            print(f'Exception caught: {e}')

    await state.clear()
    await message.answer(f"<b>✅ Оператор обновлен: @{new_operator}</b>")
    await send_admin_panel(message, message.from_user.username)
    await message.delete()


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    requisites = await get_requisites()
    bank = await get_bank()
    commission = await get_commission()
    operator = await get_operator()
    username = callback.from_user.username

    text = get_admin_panel_text(username, requisites, bank, commission, operator)
    await callback.message.edit_text(text, reply_markup=build_admin_keyboard().as_markup())
    await callback.answer()


# === LINKS MANAGEMENT ===
def get_links_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text=f"📢 OPERATOR: {read_env_var('OPERATOR', '—')}", callback_data="admin_change_link_operator")
    kb.button(text=f"💬 SUPPORT: {read_env_var('SUPPORT', '—')}", callback_data="admin_change_link_support")
    kb.button(text=f"⭐ REVIEWS: {read_env_var('REVIEWS', '—')}", callback_data="admin_change_link_reviews")
    kb.button(text=f"📝 OTZIVY: {read_env_var('OTZIVY', '—')}", callback_data="admin_change_link_otzivy")
    kb.button(text=f"📰 NEWS: {read_env_var('NEWS', '—')}", callback_data="admin_change_link_news")
    kb.button(text="⬅️ Назад", callback_data="admin_cancel")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "admin_links")
async def admin_links(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await callback.message.edit_text("🔗 <b>Настройка ссылок</b>\n\nВыберите поле:", reply_markup=get_links_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_change_link_operator")
async def admin_change_link_operator(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_for_support)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_links")
    await callback.message.edit_text(
        f"Текущее значение OPERATOR: <code>{read_env_var('OPERATOR', '—')}</code>\n\nВведите новое значение (username без @):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_link_support")
async def admin_change_link_support(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_for_support)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_links")
    await callback.message.edit_text(
        f"Текущее значение SUPPORT: <code>{read_env_var('SUPPORT', '—')}</code>\n\nВведите новое значение (username без @):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_link_reviews")
async def admin_change_link_reviews(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_for_reviews)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_links")
    await callback.message.edit_text(
        f"Текущее значение REVIEWS: <code>{read_env_var('REVIEWS', '—')}</code>\n\nВведите новое значение (username без @):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_link_otzivy")
async def admin_change_link_otzivy(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_for_otzivy)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_links")
    await callback.message.edit_text(
        f"Текущее значение OTZIVY: <code>{read_env_var('OTZIVY', '—')}</code>\n\nВведите новое значение (username без @):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_change_link_news")
async def admin_change_link_news(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Доступ запрещен", show_alert=True)
        return
    await state.set_state(AdminForm.waiting_for_news)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="admin_links")
    await callback.message.edit_text(
        f"Текущее значение NEWS: <code>{read_env_var('NEWS', '—')}</code>\n\nВведите новое значение (username без @):",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


@router.message(AdminForm.waiting_for_support)
async def process_support_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    value = message.text.strip().lstrip("@")
    update_env_var("SUPPORT", value)

    # Reload runtime state
    from runtime_state import get_runtime_state
    get_runtime_state().reload()

    await message.answer(f"✅ <b>SUPPORT</b> обновлено: <code>{value}</code>")
    await state.clear()
    await message.answer("🔗 <b>Настройка ссылок</b>\n\nВыберите поле:", reply_markup=get_links_keyboard())
    await message.delete()


@router.message(AdminForm.waiting_for_reviews)
async def process_reviews_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    value = message.text.strip().lstrip("@")
    update_env_var("REVIEWS", value)

    # Reload runtime state
    from runtime_state import get_runtime_state
    get_runtime_state().reload()

    await message.answer(f"✅ <b>REVIEWS</b> обновлено: <code>{value}</code>")
    await state.clear()
    await message.answer("🔗 <b>Настройка ссылок</b>\n\nВыберите поле:", reply_markup=get_links_keyboard())
    await message.delete()


@router.message(AdminForm.waiting_for_otzivy)
async def process_otzivy_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    value = message.text.strip().lstrip("@")
    update_env_var("OTZIVY", value)

    # Reload runtime state
    from runtime_state import get_runtime_state
    get_runtime_state().reload()

    await message.answer(f"✅ <b>OTZIVY</b> обновлено: <code>{value}</code>")
    await state.clear()
    await message.answer("🔗 <b>Настройка ссылок</b>\n\nВыберите поле:", reply_markup=get_links_keyboard())
    await message.delete()


@router.message(AdminForm.waiting_for_news)
async def process_news_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    value = message.text.strip().lstrip("@")
    update_env_var("NEWS", value)

    # Reload runtime state
    from runtime_state import get_runtime_state
    get_runtime_state().reload()

    await message.answer(f"✅ <b>NEWS</b> обновлено: <code>{value}</code>")
    await state.clear()
    await message.answer("🔗 <b>Настройка ссылок</b>\n\nВыберите поле:", reply_markup=get_links_keyboard())
    await message.delete()
