import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from cfg.base import OPERATOR_USERNAME
from src.utils.ban import banned_users, save_banned
from src.utils.group import ADMIN_IDS
from src.utils.orders import (
    get_order,
    get_user_chat_id,
    load_orders,
    update_order_status,
)

admin_orders_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AdminReplyState(StatesGroup):
    waiting_for_reply = State()
    reply_text = State()


_BAN_RE = re.compile(r"^/ban\s+(\d+)")


@admin_orders_router.message(F.chat.type == "private", Command("ban"))
async def cmd_ban_private(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = message.text or ""
    m = _BAN_RE.match(text)
    target_id = int(m.group(1)) if m else None

    if target_id is None:
        data = await state.get_data()
        order_id = data.get("order_id")
        if order_id:
            target_id = get_user_chat_id(order_id)

    if target_id is None:
        await message.reply("Используйте: /ban <user_id> или нажмите Забанить на сообщении клиента.")
        return

    if target_id in ADMIN_IDS:
        await message.reply("Нельзя забанить администратора.")
        return

    if target_id in banned_users:
        await message.reply(f"Пользователь {target_id} уже заблокирован.")
        return

    banned_users.add(target_id)
    save_banned(banned_users)
    await state.clear()

    unban_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Разбанить", callback_data=f"admin_unban_{target_id}")
    ]])
    await message.reply(
        f"Пользователь <b>{target_id}</b> заблокирован.\nБот полностью игнорирует его сообщения.",
        reply_markup=unban_kb
    )


@admin_orders_router.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    order_id = callback.data.replace("admin_ban_", "")
    target_id = get_user_chat_id(order_id)

    if not target_id:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    if target_id in ADMIN_IDS:
        await message.reply("Нельзя забанить администратора.")
        return

    if target_id in banned_users:
        await callback.answer(f"Пользователь {target_id} уже заблокирован.", show_alert=True)
        return

    banned_users.add(target_id)
    save_banned(banned_users)
    await callback.answer("Заблокирован", show_alert=True)

    unban_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Разбанить", callback_data=f"admin_unban_{target_id}")
    ]])
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=unban_kb)


@admin_orders_router.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    target_id = int(callback.data.replace("admin_unban_", ""))

    if target_id not in banned_users:
        await callback.answer("Пользователь уже разблокирован.", show_alert=True)
        return

    banned_users.discard(target_id)
    save_banned(banned_users)
    await callback.answer("Разблокирован", show_alert=True)
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@admin_orders_router.callback_query(F.data.startswith("admin_reply_"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    order_id = callback.data.replace("admin_reply_", "")
    order = get_order(order_id)

    if not order:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    await state.set_state(AdminReplyState.reply_text)
    await state.update_data(order_id=order_id)

    await callback.message.answer(
        f"Ответ на заявку {order_id}\n\n"
        "Напишите сообщение для клиента (можно отправить текст, фото или PDF):"
    )
    await callback.answer()


@admin_orders_router.message(AdminReplyState.reply_text)
async def admin_reply_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    if message.text and message.text.startswith("/"):
        return

    data = await state.get_data()
    order_id = data.get("order_id")

    if not order_id:
        await message.answer("Ошибка: не найден ID заявки")
        await state.clear()
        return

    user_chat_id = get_user_chat_id(order_id)

    if not user_chat_id:
        await message.answer("Ошибка: не найден пользователь")
        await state.clear()
        return

    try:
        if message.photo:
            photo = message.photo[-1]
            caption = f"Сообщение от оператора:\n\n{message.caption}" if message.caption else "Сообщение от оператора:"
            await message.bot.send_photo(chat_id=user_chat_id, photo=photo.file_id, caption=caption)
            await message.answer("Фото отправлено клиенту")
        elif message.document:
            caption = f"Сообщение от оператора:\n\n{message.caption}" if message.caption else "Сообщение от оператора:"
            await message.bot.send_document(chat_id=user_chat_id, document=message.document.file_id, caption=caption)
            await message.answer("Документ отправлен клиенту")
        elif message.text:
            await message.bot.send_message(chat_id=user_chat_id, text=f"Сообщение от оператора:\n\n{message.text}")
            await message.answer("Сообщение отправлено клиенту")
        else:
            await message.answer("Поддерживаются только текст, фото и документы")
            return
    except Exception as e:
        await message.answer(f"Ошибка при отправке: {e}")

    await state.clear()


@admin_orders_router.callback_query(F.data.startswith("admin_accept_"))
async def admin_accept_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    order_id = callback.data.replace("admin_accept_", "")
    order = get_order(order_id)

    if not order:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    update_order_status(order_id, "accepted")
    user_chat_id = get_user_chat_id(order_id)

    if user_chat_id:
        try:
            await callback.bot.send_message(chat_id=user_chat_id, text="Сообщение от оператора:\n\nВаша заявка принята!")
        except Exception as e:
            print(f'Exception caught: {e}')

    current_text = callback.message.text or ""
    new_text = current_text + "\n\nСтатус: Принято"
    try:
        await callback.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.answer("Заявка принята", show_alert=True)


@admin_orders_router.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return

    order_id = callback.data.replace("admin_reject_", "")
    order = get_order(order_id)

    if not order:
        await callback.answer("Заявка не найдена", show_alert=True)
        return

    update_order_status(order_id, "rejected")
    user_chat_id = get_user_chat_id(order_id)

    if user_chat_id:
        try:
            await callback.bot.send_message(
                chat_id=user_chat_id,
                text=f"Ваша заявка отменена, по дальнейшим вопросам обращайтесь к оператору {OPERATOR_USERNAME}"
            )
        except Exception as e:
            print(f'Exception caught: {e}')

    current_text = callback.message.text or ""
    new_text = current_text + "\n\nСтатус: Отклонено"
    try:
        await callback.message.edit_text(new_text, reply_markup=None)
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.answer("Заявка отклонена", show_alert=True)


@admin_orders_router.message(F.chat.type == "private", ~F.text.startswith("/"))
async def handle_user_message(message: Message, state: FSMContext):
    if is_admin(message.from_user.id):
        return

    if message.from_user.id in banned_users:
        return

    if not (message.text or message.photo or message.document):
        return

    current_state = await state.get_state()
    if current_state:
        if any(s in str(current_state) for s in ["BuyCryptoState", "SaleCryptoState", "CalculatorState", "CouponState", "AdminReplyState"]):
            return

    orders = load_orders()
    active_order = None
    active_order_id = None

    for oid, order in orders.items():
        if order.get("user_chat_id") == message.chat.id:
            if order.get("status") in ["pending", "accepted"]:
                active_order = order
                active_order_id = oid
                break

    if not active_order_id or not active_order:
        return

    username = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
    status_emoji = "?" if active_order["status"] == "pending" else "?"
    status_text = "Ожидает" if active_order["status"] == "pending" else "Принята"

    buttons = []
    if active_order["status"] == "pending":
        buttons.append([
            InlineKeyboardButton(text="Принять", callback_data=f"admin_accept_{active_order_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"admin_reject_{active_order_id}")
        ])
    buttons.append([
        InlineKeyboardButton(text="Ответить", callback_data=f"admin_reply_{active_order_id}"),
        InlineKeyboardButton(text="Забанить", callback_data=f"admin_ban_{active_order_id}")
    ])
    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    sent_to_admins = False

    if message.photo:
        photo = message.photo[-1]
        caption = (
            f"{status_emoji} Сообщение от клиента\n\n"
            f"Пользователь: {username}\n"
            f"Заявка: #{active_order_id} ({status_text})\n\n"
            f"Фото:\n{message.caption or 'Без подписи'}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_photo(chat_id=admin_id, photo=photo.file_id, caption=caption, reply_markup=reply_markup)
                sent_to_admins = True
            except Exception as e:
                print(f"Ошибка: {e}")

    elif message.document:
        file_name = message.document.file_name or "Файл"
        caption = (
            f"{status_emoji} Сообщение от клиента\n\n"
            f"Пользователь: {username}\n"
            f"Заявка: #{active_order_id} ({status_text})\n\n"
            f"Файл: {file_name}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_document(chat_id=admin_id, document=message.document.file_id, caption=caption, reply_markup=reply_markup)
                sent_to_admins = True
            except Exception as e:
                print(f"Ошибка: {e}")

    elif message.text:
        text = (
            f"{status_emoji} Сообщение от клиента\n\n"
            f"Пользователь: {username}\n"
            f"Заявка: #{active_order_id} ({status_text})\n\n"
            f"Текст:\n{message.text}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await message.bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML", reply_markup=reply_markup)
                sent_to_admins = True
            except Exception as e:
                print(f"Ошибка: {e}")

    if sent_to_admins:
        try:
            await message.answer("Ваше сообщение отправлено оператору. Ожидайте ответа.")
        except Exception as e:
            print(f'Exception caught: {e}')
