"""Справочник (Информационная Панель), FAQ и навигация. Регистрируется ПОСЛЕДНИМ."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import keyboards as kb
from .. import media, renderer, texts, utils
from ..runtime import AppContext
from .start import show_main_menu

router = Router(name="common")


@router.message(F.text == kb.BTN_HELP)
async def help_section(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    # 1) GIF-панель с инлайн-ссылками (Оператор / Чат | Новости)
    await utils.send_animation_or_text(
        message, media.help_links_doc(),
        text=renderer.render(texts.HELP_PANEL_TITLE, ctx.settings),
        reply_markup=kb.kb_help_panel(ctx.settings),
    )
    # 2) Предупреждение + нижняя FAQ-клавиатура
    await message.answer(
        renderer.render(texts.HELP_PANEL_BODY, ctx.settings),
        reply_markup=kb.kb_faq(), disable_web_page_preview=True,
    )


@router.message(F.text.in_(kb.FAQ_QUESTION_BTNS))
async def faq_question(message: Message, state: FSMContext, ctx: AppContext) -> None:
    # Тексты FAQ-разделов пользователь добавит позже.
    await message.answer(texts.FAQ_PLACEHOLDER, reply_markup=kb.kb_faq())


@router.message(F.text == kb.BTN_HOME_ARROW)
async def faq_home(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)


@router.message(F.text == kb.BTN_HOME)
async def home(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)
