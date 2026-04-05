from __future__ import annotations

from html import escape
import re
from urllib.parse import urlsplit

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..context import AppContext
from ..keyboards import kb_admin_panel, kb_admin_links
from ..states import AdminState
from utils.env_writer import update_env_var
from ..validation import is_valid_btc_address


def _is_admin(ctx: AppContext, user_id: int | None) -> bool:
    return user_id is not None and user_id in ctx.admin_ids


_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")
_ONION_V3_RE = re.compile(r"^[a-z2-7]{56}\.onion$")


def _has_unsafe_url_chars(value: str) -> bool:
    return any(ch.isspace() or ch in {'"', "'", "<", ">", "`"} for ch in value)


def _is_http_url(value: str) -> bool:
    raw = value.strip()
    if not raw or _has_unsafe_url_chars(raw):
        return False
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"}:
        return False
    if parts.username or parts.password:
        return False
    hostname = parts.hostname or ""
    return bool(_DOMAIN_RE.fullmatch(hostname))


def _is_web_url(value: str) -> bool:
    return _is_http_url(value)


def _is_tor_url(value: str) -> bool:
    raw = value.strip()
    if not raw or _has_unsafe_url_chars(raw):
        return False
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"}:
        return False
    if parts.username or parts.password:
        return False
    hostname = (parts.hostname or "").lower()
    return bool(_ONION_V3_RE.fullmatch(hostname))


def _admin_text(ctx: AppContext) -> str:
    settings = ctx.settings.get()
    site_url = escape(str(settings["site_url"]), quote=True)
    tor_url = escape(str(settings["tor_url"]), quote=True)
    return (
        "Admin panel\n\n"
        f"Fee: <b>{float(settings['fee_percent']):.2f}%</b>\n"
        f"Deposit BTC: <code>{settings['deposit_btc_address']}</code>\n"
        f"Website: <a href=\"{site_url}\">{site_url}</a>\n"
        f"Tor: <a href=\"{tor_url}\">{tor_url}</a>"
    )


def build_admin_router(ctx: AppContext) -> Router:
    router = Router(name="admin")

    @router.message(F.text == "/admin")
    async def admin_start(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not _is_admin(ctx, user_id):
            return
        await state.clear()
        await message.answer(_admin_text(ctx), reply_markup=kb_admin_panel())

    @router.callback_query(F.data == "admin:set_fee")
    async def admin_set_fee(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id if callback.from_user else None
        msg = callback.message
        if not _is_admin(ctx, user_id) or msg is None:
            return
        await state.set_state(AdminState.waiting_fee)
        await msg.answer("Send new commission percent (for example 4.5):")
        await callback.answer()

    @router.message(AdminState.waiting_fee, F.text)
    async def admin_fee_input(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not _is_admin(ctx, user_id):
            return
        raw = (message.text or "").strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            await message.answer("Invalid number. Send value like 4.5")
            return
        if value < 0 or value > 50:
            await message.answer("Allowed range: 0..50")
            return
        ctx.settings.set_fee(value)
        await state.clear()
        await message.answer("Fee updated.")
        await message.answer(_admin_text(ctx), reply_markup=kb_admin_panel())

    @router.callback_query(F.data == "admin:set_address")
    async def admin_set_address(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id if callback.from_user else None
        msg = callback.message
        if not _is_admin(ctx, user_id) or msg is None:
            return
        await state.set_state(AdminState.waiting_deposit_address)
        await msg.answer("Send new BTC deposit address:")
        await callback.answer()

    @router.message(AdminState.waiting_deposit_address, F.text)
    async def admin_address_input(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not _is_admin(ctx, user_id):
            return
        wallet = (message.text or "").strip()
        if not is_valid_btc_address(wallet):
            await message.answer("Invalid BTC address. Try again.")
            return
        ctx.settings.set_deposit_address(wallet)
        await state.clear()
        await message.answer("Deposit address updated.")
        await message.answer(_admin_text(ctx), reply_markup=kb_admin_panel())

    @router.callback_query(F.data == "admin:set_website")
    async def admin_set_website(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id if callback.from_user else None
        msg = callback.message
        if not _is_admin(ctx, user_id) or msg is None:
            return
        await state.set_state(AdminState.waiting_website_url)
        await msg.answer("Send new website URL (http/https):")
        await callback.answer()

    @router.message(AdminState.waiting_website_url, F.text)
    async def admin_website_input(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not _is_admin(ctx, user_id):
            return
        url = (message.text or "").strip()
        if not _is_web_url(url):
            await message.answer("Invalid website URL. Send a valid http(s) link.")
            return
        ctx.settings.set_site_url(url)
        await state.clear()
        await message.answer("Website updated.")
        await message.answer(_admin_text(ctx), reply_markup=kb_admin_panel())

    @router.callback_query(F.data == "admin:set_tor")
    async def admin_set_tor(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id if callback.from_user else None
        msg = callback.message
        if not _is_admin(ctx, user_id) or msg is None:
            return
        await state.set_state(AdminState.waiting_tor_url)
        await msg.answer("Send new Tor URL (http/https .onion):")
        await callback.answer()

    @router.message(AdminState.waiting_tor_url, F.text)
    async def admin_tor_input(message: Message, state: FSMContext) -> None:
        user_id = message.from_user.id if message.from_user else None
        if not _is_admin(ctx, user_id):
            return
        url = (message.text or "").strip()
        if not _is_tor_url(url):
            await message.answer("Invalid Tor URL. Send a valid .onion http(s) link.")
            return
        ctx.settings.set_tor_url(url)
        await state.clear()
        await message.answer("Tor URL updated.")
        await message.answer(_admin_text(ctx), reply_markup=kb_admin_panel())

    @router.callback_query(F.data == "admin:links")
    async def admin_links(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id if callback.from_user else None
        msg = callback.message
        if not _is_admin(ctx, user_id) or msg is None:
            return
        await state.clear()
        await msg.answer("🔗 Links", reply_markup=kb_admin_links())
        await callback.answer()

    @router.callback_query(F.data == "admin:back")
    async def admin_back(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback.from_user.id if callback.from_user else None
        msg = callback.message
        if not _is_admin(ctx, user_id) or msg is None:
            return
        await state.clear()
        await msg.answer(_admin_text(ctx), reply_markup=kb_admin_panel())
        await callback.answer()

    _LINK_FIELDS = {
        "admin:set_link_rates": ("RATES", AdminState.waiting_link_rates, "Send rates URL:"),
        "admin:set_link_sell_btc": ("SELL_BTC", AdminState.waiting_link_sell_btc, "Send sell BTC URL:"),
        "admin:set_link_news_channel": ("NEWS_CHANNEL", AdminState.waiting_link_news_channel, "Send news channel URL:"),
        "admin:set_link_operator": ("OPERATOR", AdminState.waiting_link_operator, "Send operator URL:"),
        "admin:set_link_operator2": ("OPERATOR2", AdminState.waiting_link_operator2, "Send operator2 URL:"),
        "admin:set_link_operator3": ("OPERATOR3", AdminState.waiting_link_operator3, "Send operator3 URL:"),
        "admin:set_link_work_operator": ("WORK_OPERATOR", AdminState.waiting_link_work_operator, "Send work operator URL:"),
    }

    for callback_data, (env_key, state, prompt) in _LINK_FIELDS.items():

        @router.callback_query(F.data == callback_data)
        async def admin_set_link(callback: CallbackQuery, state: FSMContext, _callback_data=callback_data) -> None:
            user_id = callback.from_user.id if callback.from_user else None
            msg = callback.message
            if not _is_admin(ctx, user_id) or msg is None:
                return
            _, _state, _prompt = _LINK_FIELDS[_callback_data]
            await state.set_state(_state)
            await msg.answer(_prompt)
            await callback.answer()

    for callback_data, (env_key, state, _) in _LINK_FIELDS.items():

        @router.message(state, F.text)
        async def admin_link_input(message: Message, state: FSMContext, _callback_data=callback_data) -> None:
            user_id = message.from_user.id if message.from_user else None
            if not _is_admin(ctx, user_id):
                return
            _, _, env_key = _LINK_FIELDS[_callback_data]
            value = (message.text or "").strip()
            if not value:
                await message.answer("Empty value. Send a valid URL.")
                return
            update_env_var(env_key, value)
            await state.clear()
            await message.answer(f"{env_key} updated.")
            await message.answer(_admin_text(ctx), reply_markup=kb_admin_panel())

    return router
