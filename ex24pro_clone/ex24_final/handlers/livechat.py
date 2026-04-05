from __future__ import annotations

import asyncio
import logging
import re
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, LinkPreviewOptions, Message

from config import ADMIN_CHAT_ID, ADMIN_IDS, PROJECT_DIR, banned_users, save_banned
from keyboards import kb_close_select, kb_rating, kb_review, kb_unban
from states import AdminChatState, ClientState
from texts import get_text

router = Router()
logger = logging.getLogger(__name__)

# msg_id in admin chat -> user_id
message_to_user: dict[int, int] = {}
# user_id -> manager name assigned at /start
_close_manager: dict[int, str] = {}

_manager_last_connected: dict[int, float] = {}
MANAGER_COOLDOWN_SECS = 7 * 60


def register_admin_message(message_id: int, user_id: int) -> None:
    """Register a message in admin chat to allow replies to the user."""
    message_to_user[message_id] = user_id


def _get_lang(user_id: int) -> str:
    from handlers.start import user_lang
    return user_lang.get(user_id, "ru")


def _get_ticket(user_id: int) -> str:
    from handlers.start import user_ticket
    return user_ticket.get(user_id, "—")


async def _get_link(key: str) -> str:
    from runtime_state import app_context
    return app_context.settings.link(key)


async def _send_source_aftercare_via_bot(bot: Bot, user_id: int, lang: str, is_alt_text: bool = False, brief_only: bool = False, skip_cooldown: bool = False) -> None:
    now = time.monotonic()
    if not skip_cooldown:
        last = _manager_last_connected.get(user_id, 0)
        if now - last < MANAGER_COOLDOWN_SECS:
            return
    _manager_last_connected[user_id] = now
    connecting = get_text("welcome_manager_connecting_alt" if is_alt_text else "welcome_manager_connecting", lang)
    temp_msg = await bot.send_message(user_id, connecting)
    if brief_only:
        return
    connected = get_text("welcome_manager_connected", lang)
    help_prompt = get_text("welcome_help_prompt", lang)
    await asyncio.sleep(7)
    try:
        await temp_msg.delete()
    except Exception as e:
        print(f'Exception caught: {e}')
    await bot.send_message(
        user_id, connected,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await asyncio.sleep(3)
    await bot.send_message(user_id, help_prompt)


# --- /chatid helper ---

@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    await message.reply(f"Chat ID: `{message.chat.id}`")


# --- /ban & /unban commands ---

_BAN_RE = re.compile(r"^/ban\s+(\d+)")
_UNBAN_RE = re.compile(r"^/unban\s+(\d+)")


_UID_IN_BOT_MSG = re.compile(r"#(\d{5,})")


def _resolve_user_id(message: Message, pattern: re.Pattern) -> int | None:
    """Extract user_id from command arg, reply mapping, or bot message text."""
    text = message.text or ""
    m = pattern.match(text)
    if m:
        return int(m.group(1))
    if message.reply_to_message:
        # 1. Try in-memory mapping (works within same session)
        uid = message_to_user.get(message.reply_to_message.message_id)
        if uid:
            return uid
        # 2. Fallback: parse user_id from bot's forwarded message text
        #    e.g. "📩 Клиент #239953377 (@username):" or "🆕 Новый клиент: #123456"
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        m2 = _UID_IN_BOT_MSG.search(reply_text)
        if m2:
            return int(m2.group(1))
    return None



# --- /ban in admin private chat (by FSM state or explicit user_id) ---

@router.message(
    F.chat.type == "private",
    Command("ban"),
)
async def cmd_ban_private(message: Message, bot: Bot, state: FSMContext) -> None:
    user = message.from_user
    if user is None or user.id not in ADMIN_IDS:
        return

    # Try explicit arg first
    text = message.text or ""
    m = _BAN_RE.match(text)
    target_id: int | None = int(m.group(1)) if m else None

    # Fall back to FSM context (admin is in a reply session)
    if target_id is None:
        data = await state.get_data()
        target_id = data.get("reply_user_id")

    if target_id is None:
        await message.reply(
            "Используйте: /ban <user_id> или нажмите 🚫 Забанить на сообщении клиента."
        )
        return

    if target_id in banned_users:
        await message.reply(f"Пользователь {target_id} уже заблокирован.")
        return

    banned_users.add(target_id)
    save_banned(banned_users)
    await state.clear()
    await message.reply(
        f"🚫 Пользователь <b>{target_id}</b> заблокирован.\n"
        f"Бот полностью игнорирует его сообщения.",
        reply_markup=kb_unban(target_id),
    )


# --- admin:reply_to callback (sets FSM context) ---

@router.callback_query(F.data.startswith("admin:reply_to:"))
async def on_admin_reply_to(cb: CallbackQuery, state: FSMContext) -> None:
    user = cb.from_user
    if user is None or user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    data = cb.data or ""
    target_id = int(data.split(":")[-1])
    await state.set_state(AdminChatState.replying_to_user)
    await state.update_data(reply_user_id=target_id)
    await cb.answer()
    if cb.message:
        await cb.message.answer(
            f"✏️ Ответ на сообщение клиента #{target_id}\n"
            f"Напишите сообщение для клиента (можно отправить текст, фото или PDF):"
        )


# --- admin:ban callback (inline ban button on client message) ---

@router.callback_query(F.data.startswith("admin:ban:"))
async def on_admin_ban_button(cb: CallbackQuery, bot: Bot) -> None:
    user = cb.from_user
    if user is None or user.id not in ADMIN_IDS:
        await cb.answer("Нет доступа", show_alert=True)
        return
    data = cb.data or ""
    target_id = int(data.split(":")[-1])

    if target_id in banned_users:
        await cb.answer(f"Пользователь {target_id} уже заблокирован.", show_alert=True)
        return

    banned_users.add(target_id)
    save_banned(banned_users)
    await cb.answer("Заблокирован", show_alert=True)
    if cb.message:
        await cb.message.edit_reply_markup(reply_markup=kb_unban(target_id))


# --- Admin reply in private chat (when in AdminChatState.replying_to_user) ---

@router.message(
    AdminChatState.replying_to_user,
    F.chat.type == "private",
)
async def admin_private_reply(message: Message, bot: Bot, state: FSMContext) -> None:
    user = message.from_user
    if user is None or user.id not in ADMIN_IDS:
        return
    data = await state.get_data()
    target_id: int | None = data.get("reply_user_id")
    if target_id is None:
        await state.clear()
        return

    # Forward admin message to client
    if message.photo:
        await bot.send_photo(target_id, message.photo[-1].file_id, caption=message.caption)
    elif message.document:
        await bot.send_document(target_id, message.document.file_id, caption=message.caption)
    elif message.video:
        await bot.send_video(target_id, message.video.file_id, caption=message.caption)
    elif message.text and not message.text.startswith("/"):
        await bot.send_message(target_id, message.text)
    else:
        return  # command handled elsewhere

    await state.clear()
    await message.reply(f"✅ Сообщение отправлено клиенту #{target_id}.")


@router.message(
    F.chat.id == ADMIN_CHAT_ID,
    Command("ban"),
)
async def cmd_ban(message: Message, bot: Bot) -> None:
    user_id = _resolve_user_id(message, _BAN_RE)
    if not user_id:
        await message.reply(
            "Используйте: /ban &lt;user_id&gt; или ответьте на сообщение пользователя."
        )
        return

    if user_id in banned_users:
        await message.reply(f"Пользователь {user_id} уже заблокирован.")
        return

    banned_users.add(user_id)
    save_banned(banned_users)
    await message.reply(
        f"🚫 Пользователь <b>{user_id}</b> заблокирован.\n"
        f"Бот полностью игнорирует его сообщения.",
        reply_markup=kb_unban(user_id),
    )


@router.message(
    F.chat.id == ADMIN_CHAT_ID,
    Command("unban"),
)
async def cmd_unban(message: Message, bot: Bot) -> None:
    user_id = _resolve_user_id(message, _UNBAN_RE)
    if not user_id:
        await message.reply(
            "Используйте: /unban &lt;user_id&gt; или ответьте на сообщение пользователя."
        )
        return

    if user_id not in banned_users:
        await message.reply(f"Пользователь {user_id} не в бан-листе.")
        return

    banned_users.discard(user_id)
    save_banned(banned_users)
    await message.reply(f"Пользователь <b>{user_id}</b> разблокирован.")


@router.callback_query(F.data.startswith("admin:unban:"))
async def on_admin_unban(cb: CallbackQuery, bot: Bot) -> None:
    data = cb.data or ""
    user_id = int(data.split(":")[-1])

    if user_id not in banned_users:
        await cb.answer("Пользователь уже разблокирован.", show_alert=True)
        if cb.message:
            await cb.message.edit_reply_markup(reply_markup=None)
        return

    banned_users.discard(user_id)
    save_banned(banned_users)

    if cb.message:
        await cb.message.edit_text(
            f"Пользователь <b>{user_id}</b> разблокирован.",
        )
    await cb.answer("Разблокирован", show_alert=True)


# --- Client -> Admin chat ---

@router.message(
    ClientState.waiting_for_source,
    F.chat.type == "private",
    ~F.text.startswith("/"),
    F.text,
)
async def client_source_reply(message: Message, bot: Bot, state: FSMContext) -> None:
    user_id = message.from_user.id
    lang = _get_lang(user_id)

    # 1. Forward the answer to admins
    await client_text(message, bot)

    # 2. Continue the source flow
    await _send_source_aftercare_via_bot(bot, user_id, lang, skip_cooldown=True)

    # 3. Clear state
    await state.clear()


@router.callback_query(
    ClientState.waiting_for_source,
    F.data.in_({"source:online", "source:offline"}),
)
async def client_source_choice(callback: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = callback.message
    user = callback.from_user
    if msg is None or user is None:
        await callback.answer()
        return

    user_id = user.id
    lang = _get_lang(user_id)
    choice = "Онлайн" if (callback.data or "").endswith("online") else "Офлайн"

    if ADMIN_CHAT_ID:
        try:
            ticket_id = _get_ticket(user_id)
            username = user.username or "no_username"
            sent = await bot.send_message(
                ADMIN_CHAT_ID,
                (
                    f"📝 Источник #{user_id} (@{username}) [🎟 {ticket_id}]: {choice}\n"
                    f"💬 Пользователь выбрал вариант в анкете."
                ),
            )
            message_to_user[sent.message_id] = user_id
        except Exception as e:
            logger.error(f"Failed to notify admins in source choice: {e}")

    try:
        await msg.delete()
    except Exception as e:
        print(f'Exception caught: {e}')

    from handlers.start import user_source_selected
    user_source_selected.add(user_id)

    await _send_source_aftercare_via_bot(bot, user_id, lang, skip_cooldown=True)
    await state.clear()
    await callback.answer("Ответ принят")


@router.message(
    F.chat.type == "private",
    ~F.text.startswith("/"),
    F.text,
)
async def client_text(message: Message, bot: Bot) -> None:
    user = message.from_user
    if user is None:
        return
    user_id = user.id
    username = user.username or "no_username"
    lang = _get_lang(user_id)
    ticket_id = _get_ticket(user_id)
    forward_text = get_text("livechat_forwarded", lang).format(
        user_id=user_id,
        username=username,
        ticket_id=ticket_id,
        text=message.text or "",
    )
    if ADMIN_CHAT_ID:
        sent = await bot.send_message(ADMIN_CHAT_ID, forward_text)
        message_to_user[sent.message_id] = user_id


@router.message(
    F.chat.type == "private",
    F.photo,
)
async def client_photo(message: Message, bot: Bot) -> None:
    user = message.from_user
    if user is None:
        return
    user_id = user.id
    username = user.username or "no_username"
    lang = _get_lang(user_id)
    ticket_id = _get_ticket(user_id)
    caption = get_text("livechat_photo", lang).format(
        user_id=user_id,
        username=username,
        ticket_id=ticket_id,
    )
    photo = message.photo[-1]
    if ADMIN_CHAT_ID:
        sent = await bot.send_photo(ADMIN_CHAT_ID, photo.file_id, caption=caption)
        message_to_user[sent.message_id] = user_id


@router.message(
    F.chat.type == "private",
    F.document,
)
async def client_document(message: Message, bot: Bot) -> None:
    user = message.from_user
    if user is None:
        return
    user_id = user.id
    username = user.username or "no_username"
    lang = _get_lang(user_id)
    ticket_id = _get_ticket(user_id)
    caption = get_text("livechat_document", lang).format(
        user_id=user_id,
        username=username,
        ticket_id=ticket_id,
    )
    if ADMIN_CHAT_ID:
        sent = await bot.send_document(
            ADMIN_CHAT_ID, message.document.file_id, caption=caption,
        )
        message_to_user[sent.message_id] = user_id


@router.message(
    F.chat.type == "private",
    F.video,
)
async def client_video(message: Message, bot: Bot) -> None:
    user = message.from_user
    if user is None:
        return
    user_id = user.id
    username = user.username or "no_username"
    lang = _get_lang(user_id)
    ticket_id = _get_ticket(user_id)
    caption = get_text("livechat_video", lang).format(
        user_id=user_id,
        username=username,
        ticket_id=ticket_id,
    )
    if ADMIN_CHAT_ID:
        sent = await bot.send_video(
            ADMIN_CHAT_ID, message.video.file_id, caption=caption,
        )
        message_to_user[sent.message_id] = user_id


# --- Admin chat -> Client (reply) ---

@router.message(
    F.chat.id == ADMIN_CHAT_ID,
    F.reply_to_message,
)
async def admin_reply(message: Message, bot: Bot) -> None:
    replied = message.reply_to_message
    if replied is None:
        return
    user_id = message_to_user.get(replied.message_id)
    if user_id is None:
        # Fallback: parse user_id from bot's message text/caption
        reply_text = replied.text or replied.caption or ""
        m = _UID_IN_BOT_MSG.search(reply_text)
        if m:
            user_id = int(m.group(1))
    if user_id is None:
        return

    if message.photo:
        photo = message.photo[-1]
        await bot.send_photo(user_id, photo.file_id, caption=message.caption)
    elif message.document:
        await bot.send_document(
            user_id, message.document.file_id, caption=message.caption,
        )
    elif message.video:
        await bot.send_video(
            user_id, message.video.file_id, caption=message.caption,
        )
    elif message.text:
        await bot.send_message(user_id, message.text)


# --- /close command ---

_CLOSE_RE = re.compile(r"^/close\s+(\d+)")


async def start_close_flow(user_id: int, bot: Bot) -> bool:
    """Helper to send the rating request to user."""
    from handlers.start import user_manager
    manager_name = user_manager.get(user_id, "Менеджер")
    _close_manager[user_id] = manager_name

    lang = _get_lang(user_id)
    link_tickets = await _get_link("tickets")

    rating_text = get_text("close_rating", lang).format(
        manager_name=manager_name,
        link_tickets=link_tickets,
    )

    operator_photo = PROJECT_DIR / "media" / "operator.jpg"
    try:
        if operator_photo.exists():
            await bot.send_photo(
                user_id,
                FSInputFile(str(operator_photo)),
                caption=rating_text,
                reply_markup=kb_rating(user_id),
            )
        else:
            await bot.send_message(
                user_id,
                rating_text,
                reply_markup=kb_rating(user_id),
            )
        return True
    except Exception:
        logger.exception("Failed to send close flow to user %d", user_id)
        return False


@router.message(
    F.chat.id == ADMIN_CHAT_ID,
    Command("close"),
)
async def cmd_close(message: Message, bot: Bot) -> None:
    text = message.text or ""
    m = _CLOSE_RE.match(text)
    
    user_id: int | None = None
    
    # 1. Check if argument provided
    if m:
        user_id = int(m.group(1))
    # 2. Check if it's a reply
    elif message.reply_to_message:
        user_id = message_to_user.get(message.reply_to_message.message_id)
    
    if user_id:
        success = await start_close_flow(user_id, bot)
        if success:
            await message.reply(f"✅ Диалог с пользователем {user_id} завершен (отправлен опрос).")
        else:
            await message.reply(f"❌ Не удалось отправить опрос пользователю {user_id}.")
        return

    # 3. Show selection list from recent active users
    recent_users = []
    seen = set()
    for uid in reversed(list(message_to_user.values())):
        if uid not in seen:
            recent_users.append(uid)
            seen.add(uid)
        if len(recent_users) >= 10:
            break
    
    if not recent_users:
        await message.reply("Не найдено недавних активных пользователей для завершения.")
        return
    
    user_list = []
    from handlers.start import user_manager
    for uid in recent_users:
        mgr = user_manager.get(uid, "—")
        user_list.append((uid, f"Клиент #{uid} (Менеджер: {mgr})"))
    
    await message.reply(
        "Выберите пользователя для завершения диалога:",
        reply_markup=kb_close_select(user_list)
    )


@router.callback_query(F.data.startswith("admin:close:"))
async def on_admin_close_select(cb: CallbackQuery, bot: Bot) -> None:
    data = cb.data or ""
    user_id = int(data.split(":")[-1])
    
    success = await start_close_flow(user_id, bot)
    if success:
        await cb.message.edit_text(f"✅ Диалог с пользователем {user_id} завершен.")
    else:
        await cb.answer(f"Ошибка при отправке опроса {user_id}", show_alert=True)
    await cb.answer()


# --- Rating callback ---

@router.callback_query(F.data.startswith("rate:"))
async def on_rating(cb: CallbackQuery, bot: Bot) -> None:
    data = cb.data or ""
    parts = data.split(":")
    if len(parts) != 3:
        await cb.answer()
        return
    _, uid_str, score_str = parts
    try:
        user_id = int(uid_str)
        score = int(score_str)
    except ValueError:
        await cb.answer()
        return

    lang = _get_lang(user_id)
    logger.info("User %d rated service: %d", user_id, score)

    # Forward rating to admin chat
    if ADMIN_CHAT_ID:
        manager_name = _close_manager.get(user_id, "—")
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"⭐ Клиент #{user_id} поставил оценку: {score}/5 (менеджер: {manager_name})",
        )

    # Bad rating response
    if score <= 3:
        bad_text = get_text("close_bad_rating", lang)
        await bot.send_message(user_id, bad_text)

    # Review request with cat photo
    link_reviews = await _get_link("reviews")
    review_text = get_text("close_review", lang).format(link_reviews=link_reviews)

    review_photo = PROJECT_DIR / "media" / "review_cat.jpg"
    if review_photo.exists():
        await bot.send_photo(
            user_id,
            FSInputFile(str(review_photo)),
            caption=review_text,
            reply_markup=kb_review(link_reviews),
        )
    else:
        await bot.send_message(
            user_id,
            review_text,
            reply_markup=kb_review(link_reviews),
        )

    await cb.answer("Спасибо за оценку!")


@router.callback_query(F.data.in_({"source:online", "source:offline"}))
async def client_source_stale(callback: CallbackQuery) -> None:
    lang = _get_lang(callback.from_user.id)
    await callback.answer()
    if callback.message:
        msg = await callback.message.answer(get_text("welcome_followup", lang))
        await asyncio.sleep(2)
        try:
            await msg.delete()
        except Exception as e:
            print(f'Exception caught: {e}')
