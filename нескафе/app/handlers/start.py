"""Онбординг: /start, /restart, «⚡️ нaчaть пользоваться!» (clone_spec §7.1)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import constants as const
from .. import keyboards as kb
from .. import media, renderer, texts, utils
from ..runtime import AppContext

router = Router(name="start")

# Пауза перед каждым сообщением в онбординге (сек, фикс. 1с).
STEP_DELAY = 1.0


async def show_main_menu(message: Message, ctx: AppContext) -> None:
    await message.answer(renderer.render_main_menu(ctx.settings), reply_markup=kb.kb_main_menu())


async def _known_user_flow(message: Message, ctx: AppContext) -> None:
    """Стикер ❔ → фото «Вы уже есть в системе» → док (ссылки) → главное меню."""
    await utils.send_sticker(message, const.STICKER_START_KNOWN)
    await utils.human_delay(STEP_DELAY, STEP_DELAY)
    await utils.send_photo_or_text(
        message, media.system_photo(),
        text=renderer.render(texts.ALREADY_IN_SYSTEM, ctx.settings),
    )
    await utils.human_delay(STEP_DELAY, STEP_DELAY)
    await utils.send_animation_or_text(
        message, media.help_links_doc(), text="",
        reply_markup=kb.kb_help_links(ctx.settings),
    )
    await utils.human_delay(STEP_DELAY, STEP_DELAY)
    await show_main_menu(message, ctx)


async def _restart_flow(message: Message, ctx: AppContext) -> None:
    """/restart → GIF со ссылками + главное меню (2 сообщения, см. скрин)."""
    await utils.human_delay(STEP_DELAY, STEP_DELAY)
    await utils.send_animation_or_text(
        message, media.help_links_doc(), text="",
        reply_markup=kb.kb_help_links(ctx.settings),
    )
    await utils.human_delay(STEP_DELAY, STEP_DELAY)
    await show_main_menu(message, ctx)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    is_new = await ctx.users.register(message.from_user.id, ctx.settings.start_bonus)
    if is_new:
        # Начислено N рублей → стикер 😌 → док «запомнить Наш Сайт» (1с перед каждым)
        await utils.human_delay(STEP_DELAY, STEP_DELAY)
        await message.answer(
            renderer.render(texts.START_BONUS, ctx.settings,
                            bonus_emoji=renderer.emoji_number(ctx.settings.start_bonus)),
            reply_markup=kb.kb_start(),
        )
        await utils.human_delay(STEP_DELAY, STEP_DELAY)
        await utils.send_sticker(message, const.STICKER_START_NEW)
        await utils.human_delay(STEP_DELAY, STEP_DELAY)
        await utils.send_animation_or_text(
            message, media.save_site_doc(),
            text=renderer.render(texts.HELP_SAVE_SITE, ctx.settings),
            reply_markup=kb.kb_site(ctx.settings), disable_web_page_preview=True,
        )
        return
    await _known_user_flow(message, ctx)


@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await _restart_flow(message, ctx)


@router.message(F.text == kb.BTN_START)
async def on_start_button(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)


@router.message(F.text == kb.BTN_HOME)
async def on_home(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)
