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


# Кнопка → (транзиентный эмодзи, текст ответа)
FAQ_MAP = {
    kb.BTN_FAQ_ABOUT: (texts.FAQ_TRANSIENT_ABOUT, texts.FAQ_ABOUT),
    kb.BTN_FAQ_SPEED: (texts.FAQ_TRANSIENT_QUESTION, texts.FAQ_SPEED),
    kb.BTN_FAQ_WALLET_ERR: (texts.FAQ_TRANSIENT_QUESTION, texts.FAQ_WALLET_ERR),
    kb.BTN_FAQ_REF: (texts.FAQ_TRANSIENT_QUESTION, texts.FAQ_REF),
    kb.BTN_FAQ_RELIABILITY: (texts.FAQ_TRANSIENT_QUESTION, texts.FAQ_RELIABILITY),
    kb.BTN_FAQ_PRIVACY: (texts.FAQ_TRANSIENT_QUESTION, texts.FAQ_PRIVACY),
}


@router.message(F.text.in_(set(FAQ_MAP)))
async def faq_question(message: Message, state: FSMContext, ctx: AppContext) -> None:
    transient, answer = FAQ_MAP[message.text]
    await utils.send_transient_then(
        message, transient, renderer.render(answer, ctx.settings),
        reply_markup=kb.kb_faq(), disable_web_page_preview=True,
    )


@router.message(F.text == kb.BTN_HOME_ARROW)
async def faq_home(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)


@router.message(F.text == kb.BTN_HOME)
async def home(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)
