from __future__ import annotations

import logging
import time

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, FSInputFile, Message

from ..context import AppContext
from ..keyboards import kb_back, kb_confirm, kb_language, kb_main, kb_return_to_main
from ..states import UserState
from ..storage import build_wallet_qr_png_bytes
from ..texts import (
    address_accepted,
    clean_prompt,
    confirm_prompt,
    faq_text,
    invalid_btc_warning,
    language_prompt,
    main_caption,
    order_text,
    qr_caption,
    qr_failed_text,
    return_to_main_echo,
)
from ..validation import is_valid_btc_address

logger = logging.getLogger(__name__)

LANG_BY_BUTTON = {
    "English": "en",
    "Русский": "ru",
    "中文": "zh",
}

BACK_BUTTONS = {"🔙 Back", "🔙 Назад", "🔙 返回"}
CLEAN_BUTTONS = {"💸 Clean coins", "💸 Очистить монеты", "💸 清洗币"}
FAQ_BUTTONS = {"❓ FAQ", "❓ 常见问题"}
RETURN_MAIN_BUTTONS = {"🏠 Return to main menu", "🏠 Вернуться в главное меню", "🏠 返回主菜单"}


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _is_start_cleaning_action(text: str | None) -> bool:
    t = _norm(text)
    return any(
        token in t
        for token in [
            "continue cleaning",
            "start cleaning",
            "продолжить очист",
            "начать очист",
            "开始清洗",
            "继续清洗",
        ]
    )


def _is_cancel_cleaning_action(text: str | None) -> bool:
    t = _norm(text)
    return any(token in t for token in ["cancel cleaning", "отмен", "取消清洗"])


def _lang_from_state_or_text(data_lang: str | None, text: str | None) -> str:
    if text in LANG_BY_BUTTON:
        return LANG_BY_BUTTON[text]
    if text == "💸 Очистить монеты" or text == "🔙 Назад":
        return "ru"
    if text == "💸 清洗币" or text == "🔙 返回" or text == "🏠 返回主菜单":
        return "zh"
    return str(data_lang or "en")


def _qr_input_file(qr_bytes: bytes) -> BufferedInputFile:
    return BufferedInputFile(qr_bytes, filename="payment_qr.png")


async def _send_qr_message(message: Message, qr_bytes: bytes, lang: str, deposit_wallet: str) -> None:
    caption = qr_caption(lang, deposit_wallet)

    try:
        await message.answer_photo(
            photo=_qr_input_file(qr_bytes),
            caption=caption,
        )
        return
    except Exception:
        logger.exception("QR send as photo failed.")

    try:
        await message.answer_document(
            document=_qr_input_file(qr_bytes),
            caption=caption,
            disable_content_type_detection=True,
        )
        return
    except Exception:
        logger.exception("QR send as document failed.")

    await message.answer(qr_failed_text(lang))


async def _send_main_menu(message: Message, ctx: AppContext, lang: str, state: FSMContext | None = None) -> None:
    data = ctx.settings.get()
    signature = (
        lang,
        float(data["fee_percent"]),
        float(data["fee_fixed_btc"]),
        str(data["site_url"]),
        str(data["tor_url"]),
    )
    if state is not None:
        state_data = await state.get_data()
        last_signature = state_data.get("_last_main_menu_signature")
        last_sent_at = float(state_data.get("_last_main_menu_sent_at") or 0.0)
        now = time.monotonic()
        if last_signature == signature and (now - last_sent_at) < 2.0:
            logger.warning("Skipping duplicate main menu send for lang=%s", lang)
            return
        await state.update_data(_last_main_menu_signature=signature, _last_main_menu_sent_at=now)
    photo = FSInputFile(str(ctx.root_dir / "assets" / "main_cover.jpg"))
    await message.answer_photo(
        photo=photo,
        caption=main_caption(lang, signature[1], signature[2], signature[3], signature[4]),
        reply_markup=kb_main(lang),
    )


async def _show_faq(message: Message, ctx: AppContext, lang: str) -> None:
    data = ctx.settings.get()
    await message.answer(
        faq_text(lang, float(data["fee_percent"]), float(data["fee_fixed_btc"])),
        reply_markup=kb_back(lang),
    )


def build_user_router(ctx: AppContext) -> Router:
    router = Router(name="user")

    @router.message(F.text == "/start")
    async def start(message: Message, state: FSMContext) -> None:
        state_data = await state.get_data()
        last_start_sent_at = float(state_data.get("_last_start_sent_at") or 0.0)
        now = time.monotonic()
        if (now - last_start_sent_at) < 2.0:
            logger.warning("Skipping duplicate /start for chat_id=%s", message.chat.id)
            return
        await state.clear()
        await state.update_data(
            lang="en",
            active_cleaning=False,
            resume_continue=False,
            _last_start_sent_at=now,
        )
        await message.answer(language_prompt(), reply_markup=kb_language())

    @router.message(F.text.in_(list(LANG_BY_BUTTON.keys())))
    async def select_language(message: Message, state: FSMContext) -> None:
        lang = LANG_BY_BUTTON[message.text]
        data = await state.get_data()
        active_cleaning = bool(data.get("active_cleaning"))
        active_order = data.get("active_order") if isinstance(data.get("active_order"), dict) else None
        await state.clear()
        await state.update_data(
            lang=lang,
            active_cleaning=active_cleaning,
            resume_continue=False,
            active_order=active_order,
        )
        await _send_main_menu(message, ctx, lang, state)

    @router.message(F.text.in_(list(FAQ_BUTTONS)))
    async def faq(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        lang = _lang_from_state_or_text(data.get("lang"), message.text)
        await state.update_data(lang=lang)
        await _show_faq(message, ctx, lang)

    @router.message(F.text.in_(list(CLEAN_BUTTONS)))
    async def clean_start(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        lang = _lang_from_state_or_text(data.get("lang"), message.text)
        active_cleaning = bool(data.get("active_cleaning"))
        resume_continue = bool(data.get("resume_continue"))
        show_continue = active_cleaning and resume_continue
        active_order = data.get("active_order") if isinstance(data.get("active_order"), dict) else None
        if show_continue and active_order:
            await state.set_state(UserState.waiting_confirm)
            await state.update_data(
                lang=lang,
                active_cleaning=active_cleaning,
                resume_continue=resume_continue,
                show_continue=True,
                active_order=active_order,
            )
            await message.answer(confirm_prompt(lang), reply_markup=kb_confirm(lang, True))
            return

        await state.set_state(UserState.waiting_receiver_address)
        await state.update_data(
            lang=lang,
            active_cleaning=active_cleaning,
            resume_continue=resume_continue,
            show_continue=show_continue,
            active_order=active_order,
        )
        await message.answer(clean_prompt(lang), reply_markup=kb_back(lang))

    @router.message(UserState.waiting_receiver_address)
    async def clean_address(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        lang = _lang_from_state_or_text(data.get("lang"), message.text)
        active_cleaning = bool(data.get("active_cleaning"))
        active_order = data.get("active_order") if isinstance(data.get("active_order"), dict) else None
        text = (message.text or "").strip()

        if text in BACK_BUTTONS:
            await state.clear()
            await state.update_data(
                lang=lang,
                active_cleaning=active_cleaning,
                resume_continue=bool(data.get("resume_continue")),
                active_order=active_order,
            )
            await _send_main_menu(message, ctx, lang, state)
            return

        wallet = text
        if not is_valid_btc_address(wallet):
            await message.answer(invalid_btc_warning(lang))
            await message.answer(clean_prompt(lang))
            return

        await state.update_data(receiver_wallet=wallet, lang=lang)
        await message.answer(address_accepted(lang, wallet))
        await state.set_state(UserState.waiting_confirm)
        show_continue = bool(data.get("show_continue"))
        await message.answer(confirm_prompt(lang), reply_markup=kb_confirm(lang, show_continue))

    @router.message(UserState.waiting_confirm)
    async def waiting_confirm(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        lang = _lang_from_state_or_text(data.get("lang"), message.text)
        text = (message.text or "").strip()

        if _is_cancel_cleaning_action(text):
            await state.clear()
            await state.update_data(lang=lang, active_cleaning=False, resume_continue=False)
            await _send_main_menu(message, ctx, lang, state)
            return

        if _is_start_cleaning_action(text):
            receiver_wallet = str(data.get("receiver_wallet") or "")
            settings = ctx.settings.get()
            show_continue = bool(data.get("show_continue"))
            saved_order = data.get("active_order") if isinstance(data.get("active_order"), dict) else None

            if show_continue and saved_order:
                order_id = int(saved_order.get("order_id", ctx.runtime.next_order_id()))
                receiver_wallet = str(saved_order.get("receiver_wallet") or receiver_wallet)
                deposit_wallet = str(saved_order.get("deposit_wallet") or settings["deposit_btc_address"])
            else:
                order_id = ctx.runtime.next_order_id()
                deposit_wallet = str(settings["deposit_btc_address"])
                saved_order = {
                    "order_id": order_id,
                    "receiver_wallet": receiver_wallet,
                    "deposit_wallet": deposit_wallet,
                }

            await message.answer(
                order_text(
                    lang=lang,
                    order_id=order_id,
                    receiver_wallet=receiver_wallet,
                    deposit_wallet=deposit_wallet,
                    min_btc=float(settings["order_min_btc"]),
                    max_btc=float(settings["order_max_btc"]),
                ),
                reply_markup=kb_return_to_main(lang),
            )

            qr_bytes = build_wallet_qr_png_bytes(deposit_wallet)
            await _send_qr_message(message, qr_bytes, lang, deposit_wallet)

            await state.clear()
            await state.update_data(
                lang=lang,
                active_cleaning=True,
                resume_continue=False,
                active_order=saved_order,
            )
            return

        show_continue = bool(data.get("show_continue"))
        await message.answer(confirm_prompt(lang), reply_markup=kb_confirm(lang, show_continue))

    @router.message(F.text.in_(list(RETURN_MAIN_BUTTONS)))
    async def return_to_main(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        lang = _lang_from_state_or_text(data.get("lang"), message.text)
        active_cleaning = bool(data.get("active_cleaning"))
        active_order = data.get("active_order") if isinstance(data.get("active_order"), dict) else None
        await state.clear()
        await state.update_data(
            lang=lang,
            active_cleaning=active_cleaning,
            resume_continue=active_cleaning,
            active_order=active_order,
        )
        await message.answer(return_to_main_echo(lang))
        await _send_main_menu(message, ctx, lang, state)

    return router
