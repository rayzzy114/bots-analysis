from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from src.utils.orders import get_order, update_order_status, get_user_chat_id, load_orders
from src.utils.group import ADMIN_IDS
import os
from dotenv import load_dotenv

load_dotenv()

OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "@expresschanger_support_bot")

admin_orders_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminReplyState(StatesGroup):
    waiting_for_reply = State()
    reply_text = State()


@admin_orders_router.callback_query(F.data.startswith("admin_reply_"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("admin_reply_", "")
    order = get_order(order_id)
    
    if not order:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    await state.set_state(AdminReplyState.reply_text)
    await state.update_data(order_id=order_id)
    
    await callback.message.answer(
        f"💬 Ответ на заявку {order_id}\n\n"
        "Напишите сообщение для клиента (можно отправить текст, фото или PDF):"
    )
    await callback.answer()


@admin_orders_router.message(AdminReplyState.reply_text)
async def admin_reply_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    order_id = data.get("order_id")
    
    if not order_id:
        await message.answer("❌ Ошибка: не найден ID заявки")
        await state.clear()
        return
    
    user_chat_id = get_user_chat_id(order_id)
    
    if not user_chat_id:
        await message.answer("❌ Ошибка: не найден пользователь")
        await state.clear()
        return
    
    try:
        if message.photo:
            photo = message.photo[-1]
            caption = f"Сообщение от оператора:\n\n{message.caption}" if message.caption else "Сообщение от оператора:"
            await message.bot.send_photo(
                chat_id=user_chat_id,
                photo=photo.file_id,
                caption=caption
            )
            await message.answer("✅ Фото отправлено клиенту")
        elif message.document:
            caption = f"Сообщение от оператора:\n\n{message.caption}" if message.caption else "Сообщение от оператора:"
            await message.bot.send_document(
                chat_id=user_chat_id,
                document=message.document.file_id,
                caption=caption
            )
            await message.answer("✅ Документ отправлен клиенту")
        elif message.text:
            reply_text = f"Сообщение от оператора:\n\n{message.text}"
            await message.bot.send_message(
                chat_id=user_chat_id,
                text=reply_text
            )
            await message.answer("✅ Сообщение отправлено клиенту")
        else:
            await message.answer("❌ Поддерживаются только текст, фото и документы")
            return
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке сообщения: {e}")
    
    await state.clear()


@admin_orders_router.callback_query(F.data.startswith("admin_accept_"))
async def admin_accept_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("admin_accept_", "")
    order = get_order(order_id)
    
    if not order:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    update_order_status(order_id, "accepted")
    user_chat_id = get_user_chat_id(order_id)
    
    if user_chat_id:
        try:
            await callback.bot.send_message(
                chat_id=user_chat_id,
                text="Сообщение от оператора:\n\n✅ Ваша заявка принята!"
            )
        except Exception:
            pass
    
    current_text = callback.message.text or callback.message.caption or ""
    new_text = current_text + "\n\n✅ Статус: Принято"
    
    try:
        await callback.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.answer("✅ Заявка принята", show_alert=True)


@admin_orders_router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    order_id = callback.data.replace("admin_reject_", "")
    order = get_order(order_id)
    
    if not order:
        await callback.answer("❌ Заявка не найдена", show_alert=True)
        return
    
    update_order_status(order_id, "rejected")
    user_chat_id = get_user_chat_id(order_id)
    
    if user_chat_id:
        try:
            await callback.bot.send_message(
                chat_id=user_chat_id,
                text=f"Ваша заявка отменена, по дальнейшим вопросам обращайтесь к оператору {OPERATOR_USERNAME}"
            )
        except Exception:
            pass
    
    current_text = callback.message.text or callback.message.caption or ""
    new_text = current_text + "\n\n❌ Статус: Отклонено"
    
    try:
        await callback.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)
    
    await callback.answer("❌ Заявка отклонена", show_alert=True)


@admin_orders_router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def handle_user_message(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        return
    
    if not message.text and not message.photo and not message.document:
        return
    
    current_state = await state.get_state()
    if current_state:
        state_name = str(current_state)
        if "BuyCryptoState" in state_name or "SaleCryptoState" in state_name or "AdminReplyState" in state_name or "PromoCodeState" in state_name:
            return
    
    orders = load_orders()
    user_orders = {oid: order for oid, order in orders.items() if order.get("user_chat_id") == message.chat.id}
    
    if not user_orders:
        return
    
    active_order_id = None
    for oid, order in user_orders.items():
        order_status = order.get("status")
        if order_status in ["pending", "accepted"]:
            active_order_id = oid
            break
    
    if not active_order_id:
        return
    
    username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    
    reply_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin_reply_{active_order_id}")]
    ])
    
    if not ADMIN_IDS:
        return
    
    sent_to_admins = False
    
    if message.photo:
        photo = message.photo[-1]
        caption = f"""💬 Сообщение от клиента

👤 Пользователь: {username}
📜 Заявка: {active_order_id}

💬 Подпись: {message.caption if message.caption else "Без подписи"}"""
        
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=photo.file_id,
                    caption=caption,
                    reply_markup=reply_button
                )
                sent_to_admins = True
            except Exception:
                pass
    
    elif message.document:
        file_name = message.document.file_name or "Файл"
        file_type = ""
        if message.document.mime_type:
            if "pdf" in message.document.mime_type.lower():
                file_type = "📄 PDF"
            elif "image" in message.document.mime_type.lower():
                file_type = "🖼️ Изображение"
            else:
                file_type = "📎 Документ"
        
        caption = f"""💬 Сообщение от клиента

👤 Пользователь: {username}
📜 Заявка: {active_order_id}

{file_type}: {file_name}
💬 Подпись: {message.caption if message.caption else "Без подписи"}"""
        
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_document(
                    chat_id=admin_id,
                    document=message.document.file_id,
                    caption=caption,
                    reply_markup=reply_button
                )
                sent_to_admins = True
            except Exception:
                pass
    
    elif message.text:
        text = f"""💬 Сообщение от клиента

👤 Пользователь: {username}
📜 Заявка: {active_order_id}

💬 Сообщение:
{message.text}"""
        
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(chat_id=admin_id, text=text, reply_markup=reply_button)
                sent_to_admins = True
            except Exception:
                pass
    
    if sent_to_admins:
        try:
            await message.answer("Ваше сообщение доставлено оператору, ожидайте ответ")
        except Exception:
            pass

