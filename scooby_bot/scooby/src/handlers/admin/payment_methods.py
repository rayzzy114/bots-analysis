from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.payment_methods import get_payment_methods, add_payment_method, remove_payment_method
from src.utils.env_writer import update_env_var, read_env_var
import os
from dotenv import load_dotenv

load_dotenv()

admin_router = Router()
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]


class AdminPaymentState(StatesGroup):
    adding_method = State()


class AdminLinksState(StatesGroup):
    waiting_for_link_field = State()


# LINK_FIELDS for scooby_bot
LINK_FIELDS = {
    "link_operator": "OPERATOR_URL",
    "link_reviews": "REVIEWS_URL",
    "link_games_chat": "GAMES_CHAT_URL",
    "link_website": "WEBSITE_URL",
}


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


def admin_payment_methods_keyboard():
    """Клавиатура для управления методами оплаты"""
    methods = get_payment_methods()
    buttons = []

    for method in methods:
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {method['name']}",
                callback_data=f"admin_remove_method_{method['id']}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="➕ Добавить метод", callback_data="admin_add_method")])
    buttons.append([InlineKeyboardButton(text="🔗 Ссылки", callback_data="admin_links")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_links_keyboard():
    """Клавиатура для управления ссылками"""
    buttons = [
        [InlineKeyboardButton(text=f"👨‍💻 operator: {read_env_var('OPERATOR_URL', '—')}", callback_data="link_operator")],
        [InlineKeyboardButton(text=f"✅ reviews: {read_env_var('REVIEWS_URL', '—')}", callback_data="link_reviews")],
        [InlineKeyboardButton(text=f"🎰 games_chat: {read_env_var('GAMES_CHAT_URL', '—')}", callback_data="link_games_chat")],
        [InlineKeyboardButton(text=f"🌐 website: {read_env_var('WEBSITE_URL', '—')}", callback_data="link_website")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_router.message(Command("admin"))
async def admin_command(message: Message):
    """Команда для доступа к админ панели"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к админ панели")
        return
    
    methods = get_payment_methods()
    methods_text = "📋 Текущие методы оплаты:\n\n"
    
    if methods:
        for i, method in enumerate(methods, 1):
            methods_text += f"{i}. {method['name']}\n"
    else:
        methods_text += "Методы оплаты не настроены\n"
    
    methods_text += "\nВыберите действие:"
    
    await message.answer(methods_text, reply_markup=admin_payment_methods_keyboard())


@admin_router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню админки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.clear()
    
    methods = get_payment_methods()
    methods_text = "📋 Текущие методы оплаты:\n\n"
    
    if methods:
        for i, method in enumerate(methods, 1):
            methods_text += f"{i}. {method['name']}\n"
    else:
        methods_text += "Методы оплаты не настроены\n"
    
    methods_text += "\nВыберите действие:"
    
    await callback.message.edit_text(methods_text, reply_markup=admin_payment_methods_keyboard())
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_remove_method_"))
async def admin_remove_method(callback: CallbackQuery):
    """Удаление метода оплаты"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    method_id = callback.data.replace("admin_remove_method_", "")
    remove_payment_method(method_id)
    
    await callback.answer("✅ Метод оплаты удален", show_alert=True)
    
    methods = get_payment_methods()
    methods_text = "📋 Текущие методы оплаты:\n\n"
    
    if methods:
        for i, method in enumerate(methods, 1):
            methods_text += f"{i}. {method['name']}\n"
    else:
        methods_text += "Методы оплаты не настроены\n"
    
    methods_text += "\nВыберите действие:"
    
    await callback.message.edit_text(methods_text, reply_markup=admin_payment_methods_keyboard())


@admin_router.callback_query(F.data == "admin_add_method")
async def admin_add_method_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления метода оплаты"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminPaymentState.adding_method)
    
    await callback.message.edit_text(
        "<b>➕ Добавление нового метода оплаты</b>\n\n"
        "<b>Отправьте сообщение в формате:</b>\n"
        "<code>Название Банка</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>💳 Карта РФ</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
    )
    await callback.answer()


@admin_router.message(AdminPaymentState.adding_method, F.text)
async def admin_add_method_process(message: Message, state: FSMContext):
    """Обработка добавления метода оплаты"""
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    
    try:
        name = message.text.strip()
        
        if not name:
            await message.answer("❌ Название метода не может быть пустым")
            return
        
        import re
        method_id = re.sub(r'[^\w\s]', '', name.lower().replace(' ', '_'))
        method_id = re.sub(r'_+', '_', method_id).strip('_')
        if not method_id:
            method_id = "method_" + str(len(get_payment_methods()) + 1)
        callback_data = f"payment_{method_id}"
        
        add_payment_method(name, callback_data)
        await message.answer(f"✅ Метод оплаты '{name}' успешно добавлен!")
        
        methods = get_payment_methods()
        methods_text = "📋 Текущие методы оплаты:\n\n"
        
        if methods:
            for i, method in enumerate(methods, 1):
                methods_text += f"{i}. {method['name']}\n"
        else:
            methods_text += "Методы оплаты не настроены\n"
        
        methods_text += "\nВыберите действие:"
        
        await message.answer(methods_text, reply_markup=admin_payment_methods_keyboard())
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении метода: {e}")
        await state.clear()


# ==================== LINKS HANDLERS ====================

@admin_router.callback_query(F.data == "admin_links")
async def admin_links(callback: CallbackQuery, state: FSMContext):
    """Показать меню редактирования ссылок"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "🔗 <b>Управление ссылками</b>\n\nВыберите поле для редактирования:",
        reply_markup=admin_links_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.in_(tuple(LINK_FIELDS.keys())))
async def admin_link_field_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования поля ссылки"""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    field_key = callback.data
    env_key = LINK_FIELDS[field_key]
    current_value = read_env_var(env_key, "")

    await state.update_data(link_field=field_key, env_key=env_key)
    await state.set_state(AdminLinksState.waiting_for_link_field)

    await callback.message.edit_text(
        f"🔗 Введите новое значение для <code>{env_key}</code>:\n\n"
        f"Текущее значение: {current_value if current_value else '— не задано'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_links")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.message(AdminLinksState.waiting_for_link_field)
async def admin_set_link_field(message: Message, state: FSMContext):
    """Сохранение нового значения поля ссылки"""
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    env_key = data.get("env_key")
    new_value = message.text.strip()

    update_env_var(env_key, new_value)
    load_dotenv(override=True)

    await message.answer(
        f"✅ <code>{env_key}</code> обновлено: {new_value}",
        parse_mode="HTML"
    )

    # Return to admin menu
    methods = get_payment_methods()
    methods_text = "📋 Текущие методы оплаты:\n\n"

    if methods:
        for i, method in enumerate(methods, 1):
            methods_text += f"{i}. {method['name']}\n"
    else:
        methods_text += "Методы оплаты не настроены\n"

    methods_text += "\nВыберите действие:"

    await message.answer(methods_text, reply_markup=admin_payment_methods_keyboard())
    await state.clear()


