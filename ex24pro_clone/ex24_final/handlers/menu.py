from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from config import ADMIN_CHAT_ID, PROJECT_DIR
from keyboards import kb_country_sub
from texts import get_text

router = Router()
logger = logging.getLogger(__name__)


def _get_lang(user_id: int) -> str:
    from handlers.start import user_lang
    return user_lang.get(user_id, "ru")


def _get_ticket(user_id: int) -> str:
    from handlers.start import user_ticket
    return user_ticket.get(user_id, "—")


async def _notify_admin(cb: CallbackQuery, bot: Bot, action: str) -> None:
    if not ADMIN_CHAT_ID:
        return
    user = cb.from_user
    ticket_id = _get_ticket(user.id)
    try:
        sent = await bot.send_message(
            ADMIN_CHAT_ID,
            f"🖱 Клиент #{user.id} (@{user.username or 'no_username'}) [🎟 {ticket_id}] -> {action}"
        )
        from handlers.livechat import register_admin_message
        register_admin_message(sent.message_id, user.id)
    except Exception as e:
        logger.error(f"Failed to notify admins: {e}")


def _set_lang(user_id: int, lang: str) -> None:
    from handlers.start import user_lang
    user_lang[user_id] = lang


async def _check_aftercare(user_id: int, state: FSMContext, bot: Bot, lang: str) -> None:
    from states import ClientState
    current_state = await state.get_state()
    if current_state == ClientState.waiting_for_source:
        await state.clear()
        from handlers.start import user_source_selected
        user_source_selected.add(user_id)
    from handlers.livechat import _send_source_aftercare_via_bot
    task = asyncio.create_task(_send_source_aftercare_via_bot(bot, user_id, lang, is_alt_text=True))
    task.add_done_callback(lambda t: t.exception() and logger.debug("Aftercare task failed: %s", t.exception()))

async def _get_rate_kwargs() -> dict[str, str]:
    from runtime_state import rate_service
    rates = await rate_service.get_rates()
    rub_idr = rates.get("rub_idr", 0.0053)
    if rub_idr and rub_idr < 1:
        rub_idr_inv = str(int(round(1.0 / rub_idr)))
    else:
        rub_idr_inv = str(int(round(rub_idr)))
    return {
        "rate_rub_thb": str(rates.get("rub_thb", "—")),
        "rate_usdt_thb": str(rates.get("usdt_thb", "—")),
        "rate_usdt_cny": str(rates.get("usdt_cny", "—")),
        "rate_rub_cny": str(rates.get("rub_cny", "—")),
        "rate_usdt_aed": str(rates.get("usdt_aed", "—")),
        "rate_rub_aed": str(rates.get("rub_aed", "—")),
        "rate_usdt_idr": str(rates.get("usdt_idr", "—")),
        "rate_rub_idr_inv": rub_idr_inv,
        "rate_usdt_try": str(rates.get("usdt_try", "—")),
        "rate_rub_try": str(rates.get("rub_try", "—")),
    }


async def _get_link_kwargs() -> dict[str, str]:
    from runtime_state import app_context
    return {
        "link_support": app_context.settings.link("support"),
        "link_offices": app_context.settings.link("offices"),
        "link_reviews": app_context.settings.link("reviews"),
        "link_tickets": app_context.settings.link("tickets"),
    }


def _answer_msg(cb: CallbackQuery) -> Message | None:
    return cb.message if isinstance(cb.message, Message) else None


@router.callback_query(F.data == "menu:turkey")
async def on_turkey(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("turkey_info", lang)

    welcome_photo = PROJECT_DIR / "media" / "welcome.jpg"
    if welcome_photo.exists():
        await msg.answer_photo(FSInputFile(str(welcome_photo)), caption=text, reply_markup=kb_country_sub("turkey"))
    else:
        await msg.answer(text, reply_markup=kb_country_sub("turkey"))

    await _notify_admin(cb, bot, "Инфо Турция")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)

@router.callback_query(F.data == "menu:turkey_rates")
async def on_turkey_rates(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    kwargs = await _get_rate_kwargs()
    text = get_text("turkey_rates", lang).format(**kwargs)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Курсы Турция")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)

@router.callback_query(F.data == "menu:turkey_methods")
async def on_turkey_methods(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("turkey_methods", lang)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Методы Турция")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:rates_th")
async def on_rates_th(cb: CallbackQuery, bot: Bot) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    kwargs = await _get_rate_kwargs()
    text = get_text("rates_th", lang).format(**kwargs)

    welcome_photo = PROJECT_DIR / "media" / "welcome.jpg"
    if welcome_photo.exists():
        await msg.answer_photo(FSInputFile(str(welcome_photo)), caption=text)
    else:
        await msg.answer(text)

    await _notify_admin(cb, bot, "Курсы Таиланд")
    await cb.answer()


@router.callback_query(F.data == "menu:china")
async def on_china(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("china_info", lang)

    welcome_photo = PROJECT_DIR / "media" / "welcome.jpg"
    if welcome_photo.exists():
        await msg.answer_photo(FSInputFile(str(welcome_photo)), caption=text, reply_markup=kb_country_sub("china"))
    else:
        await msg.answer(text, reply_markup=kb_country_sub("china"))

    await _notify_admin(cb, bot, "Инфо Китай")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:china_rates")
async def on_china_rates(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    kwargs = await _get_rate_kwargs()
    text = get_text("china_rates", lang).format(**kwargs)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Курсы Китай")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:china_methods")
async def on_china_methods(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("china_methods", lang)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Методы Китай")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:dubai")
async def on_dubai(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("dubai_info", lang)

    welcome_photo = PROJECT_DIR / "media" / "welcome.jpg"
    if welcome_photo.exists():
        await msg.answer_photo(FSInputFile(str(welcome_photo)), caption=text, reply_markup=kb_country_sub("dubai"))
    else:
        await msg.answer(text, reply_markup=kb_country_sub("dubai"))

    await _notify_admin(cb, bot, "Инфо Дубай")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:dubai_rates")
async def on_dubai_rates(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    kwargs = await _get_rate_kwargs()
    text = get_text("dubai_rates", lang).format(**kwargs)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Курсы Дубай")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:dubai_methods")
async def on_dubai_methods(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("dubai_methods", lang)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Методы Дубай")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:bali")
async def on_bali(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("bali_info", lang)

    welcome_photo = PROJECT_DIR / "media" / "welcome.jpg"
    if welcome_photo.exists():
        await msg.answer_photo(FSInputFile(str(welcome_photo)), caption=text, reply_markup=kb_country_sub("bali"))
    else:
        await msg.answer(text, reply_markup=kb_country_sub("bali"))

    await _notify_admin(cb, bot, "Инфо Бали")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:bali_rates")
async def on_bali_rates(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    kwargs = await _get_rate_kwargs()
    text = get_text("bali_rates", lang).format(**kwargs)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Курсы Бали")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:bali_methods")
async def on_bali_methods(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    lang = _get_lang(user_id)
    text = get_text("bali_methods", lang)
    await msg.answer(text)
    await _notify_admin(cb, bot, "Методы Бали")
    await cb.answer()
    await _check_aftercare(user_id, state, bot, lang)


@router.callback_query(F.data == "menu:lang")
async def on_lang(cb: CallbackQuery, bot: Bot, state: FSMContext) -> None:
    msg = _answer_msg(cb)
    if msg is None:
        await cb.answer()
        return
    user_id = cb.from_user.id
    current = _get_lang(user_id)
    new_lang = "en" if current == "ru" else "ru"
    _set_lang(user_id, new_lang)
    await _check_aftercare(user_id, state, bot, new_lang)
    text = get_text("lang_switched", new_lang)
    await msg.answer(text)
    await _notify_admin(cb, bot, f"Язык: {new_lang}")
    await cb.answer()
