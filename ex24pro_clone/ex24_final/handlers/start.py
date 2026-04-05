from __future__ import annotations

import asyncio
import random

from aiogram import Bot, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from config import ADMIN_CHAT_ID, MANAGER_NAMES, PROJECT_DIR
from admin_kit.utils import sanitize_html_fragment
from keyboards import kb_source_choice, kb_welcome
from states import ClientState
from texts import get_text

router = Router()

user_lang: dict[int, str] = {}
user_manager: dict[int, str] = {}
user_ticket: dict[int, str] = {}
user_source_selected: set[int] = set()
_start_processing: set[int] = set()


def _assign_manager(user_id: int) -> str:
    if user_id not in user_manager:
        user_manager[user_id] = random.choice(MANAGER_NAMES)
    return user_manager[user_id]


def _assign_ticket(user_id: int) -> str:
    if user_id not in user_ticket:
        user_ticket[user_id] = str(random.randint(1_000_000, 9_999_999))
    return user_ticket[user_id]


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext) -> None:
    user = message.from_user
    if user is None:
        return
    user_id = user.id

    if user_id in _start_processing:
        return
    _start_processing.add(user_id)

    try:
        username = user.username or "no_username"
        lang = user_lang.get(user_id, "ru")
        manager = _assign_manager(user_id)
        ticket_id = _assign_ticket(user_id)

        if ADMIN_CHAT_ID:
            try:
                from handlers.livechat import register_admin_message
                sent = await bot.send_message(
                    ADMIN_CHAT_ID,
                    f"🆕 Новый клиент: #{user_id} (@{username})\n"
                    f"🎟 Заявка: #{ticket_id}\n"
                    f"👩‍💻 Назначен менеджер: {manager}"
                )
                register_admin_message(sent.message_id, user_id)
            except Exception:
                pass

        from runtime_state import app_context
        if app_context.users is not None:
            app_context.users.user(user_id)

        link_support = sanitize_html_fragment(app_context.settings.link("support"))

        caption = get_text("welcome_caption", lang).format(
            ticket_id=ticket_id,
            manager_name=manager,
            link_support=link_support,
        )

        welcome_photo = PROJECT_DIR / "media" / "welcome.jpg"
        if welcome_photo.exists():
            await message.answer_photo(
                FSInputFile(str(welcome_photo)),
                caption=caption,
                reply_markup=kb_welcome(),
            )
        else:
            await message.answer(caption, reply_markup=kb_welcome())

        if user_id not in user_source_selected:
            source_question = get_text("welcome_source_question", lang)
            source_photo = PROJECT_DIR / "media" / "image_102.png"
            if source_photo.exists():
                await message.answer_photo(
                    FSInputFile(str(source_photo)),
                    caption=source_question,
                    reply_markup=kb_source_choice(),
                )
            else:
                await message.answer(source_question, reply_markup=kb_source_choice())
            await state.set_state(ClientState.waiting_for_source)
        else:
            from handlers.livechat import _send_source_aftercare_via_bot
            asyncio.create_task(
                _send_source_aftercare_via_bot(bot, user_id, lang, is_alt_text=True, skip_cooldown=True)
            )
    finally:
        _start_processing.discard(user_id)
