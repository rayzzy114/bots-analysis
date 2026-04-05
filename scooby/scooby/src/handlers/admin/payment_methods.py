from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from src.utils.payment_methods import get_payment_methods, add_payment_method, remove_payment_method, save_payment_methods
import os
from dotenv import load_dotenv

load_dotenv()

admin_router = Router()
ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]


class AdminPaymentState(StatesGroup):
    adding_method = State()


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
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
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

