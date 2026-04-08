from __future__ import annotations
import httpx

import asyncio
import logging
import math
import os
import random
import re
import string
from dataclasses import dataclass, field
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import dotenv_values, load_dotenv

from admin_kit import AdminKitConfig, LinkDefinition, build_admin_components
from admin_kit.context import AppContext
from admin_kit.rates import FALLBACK_RATES_RUB
from admin_kit.storage import OrdersStore

from .catalog import FlowCatalog
from .constants import (
    DEFAULT_COMMISSION,
    DEFAULT_LINKS,
    HISTORY_PAGE_SIZE,
    LINK_LABELS,
    PARTNER_MIN_WITHDRAW_BTC,
    SELL_WALLET_LABELS,
)
from .keyboards import kb_history_page
from .overrides import RuntimeOverrides, apply_state_overrides
from .renderer import action_token, edit_state, send_state

logger = logging.getLogger(__name__)

PARTNER_MIN_WITHDRAW_ALERT = f"⚠ Минимальная сумма вывода:\n{PARTNER_MIN_WITHDRAW_BTC} BTC"
PARTNER_EMPTY_HISTORY_TEXT = "Операций по партнерскому счету не производилось."
HISTORY_EMPTY_TEXT = "У вас пока нет обменов."
CAPTCHA_IMAGE = "photo_5880884889631001926.jpg"
CAPTCHA_CORRECT_CODE = "rfp6p"
CAPTCHA_RETRY_TEXT = "❌ Капча нажата неверно. Попробуйте еще раз."
WELCOME_STATE_ID = "4fdfa881597ed3208ee0144e67604ef9"
START_IMAGE = "photo_5998155393936766863.jpg"
ORDER_ID_RE = re.compile(r"Заявка №(?:<strong>|\*\*)?(\d+)")
ORDER_STATUS_HTML_RE = re.compile(r"(Статус:\s*<strong>)([^<]+)(</strong>)")
ORDER_STATUS_MD_RE = re.compile(r"(Статус:\s*\*\*)([^*]+)(\*\*)")
ORDER_STATUS_TEXT_RE = re.compile(r"(Статус:\s*)([^\n]+)")
ORDER_WALLET_HTML_RE = re.compile(
    r"(Адрес, на который поступят чистые средства:\n<code>)([^<]+)(</code>)"
)
ORDER_WALLET_MD_RE = re.compile(
    r"(Адрес, на который поступят чистые средства:\n`)([^`]+)(`)"
)
ORDER_WALLET_TEXT_RE = re.compile(
    r"(Адрес, на который поступят чистые средства:\n)([^\n]+)"
)
ORDER_TX_HTML_RE = re.compile(r"\n\nТранзакции:\s*<strong>[^<]+</strong>")
ORDER_TX_MD_RE = re.compile(r"\n\nТранзакции:\s*\*\*[^*]+\*\*")
ORDER_TX_TEXT_RE = re.compile(r"\n\nТранзакции:\s*[^\n]+")
CANCEL_CONFIRM_RE = re.compile(r"(Обмен #)(\d+)( отменен)")
MINIMUM_RUB = 10_000.0
MIN_AMOUNT_TEXT_RE = re.compile(r"(Минимальная сумма обмена:\s*)([^\n]+)")
MIN_AMOUNT_HTML_RE = re.compile(r"(Минимальная сумма обмена:\s*<strong>)([^<]+)(</strong>)")
MIN_AMOUNT_MD_RE = re.compile(r"(Минимальная сумма обмена:\s*\*\*)([^*]+)(\*\*)")

BTC_ADDRESS_RE = re.compile(r"(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{20,}")
ETH_ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
TRX_ADDRESS_RE = re.compile(r"T[1-9A-HJ-NP-Za-km-z]{25,34}")
LTC_ADDRESS_RE = re.compile(r"[LM3][a-km-zA-HJ-NP-Z1-9]{26,40}")
XMR_ADDRESS_RE = re.compile(r"4[0-9AB][1-9A-HJ-NP-Za-km-z]{90,110}")

_ADDR_PATTERNS = [
    re.compile(rf"\b{BTC_ADDRESS_RE.pattern}\b"),
    re.compile(rf"\b{ETH_ADDRESS_RE.pattern}\b"),
    re.compile(rf"\b{TRX_ADDRESS_RE.pattern}\b"),
    re.compile(rf"\b{LTC_ADDRESS_RE.pattern}\b"),
    re.compile(rf"\b{XMR_ADDRESS_RE.pattern}\b"),
]
_CURRENCY_ADDRESS_PATTERNS: dict[str, re.Pattern[str]] = {
    "чистые btc": re.compile(rf"^{BTC_ADDRESS_RE.pattern}$"),
    "btc (чистый)": re.compile(rf"^{BTC_ADDRESS_RE.pattern}$"),
    "ethereum": re.compile(rf"^{ETH_ADDRESS_RE.pattern}$"),
    "tether erc-20": re.compile(rf"^{ETH_ADDRESS_RE.pattern}$"),
    "usdt erc-20": re.compile(rf"^{ETH_ADDRESS_RE.pattern}$"),
    "tether trc-20": re.compile(rf"^{TRX_ADDRESS_RE.pattern}$"),
    "usdt trc-20": re.compile(rf"^{TRX_ADDRESS_RE.pattern}$"),
    "tether bep-20": re.compile(rf"^{ETH_ADDRESS_RE.pattern}$"),
    "usdt bep-20": re.compile(rf"^{ETH_ADDRESS_RE.pattern}$"),
    "litecoin": re.compile(rf"^{LTC_ADDRESS_RE.pattern}$"),
    "monero": re.compile(rf"^{XMR_ADDRESS_RE.pattern}$"),
}
_ORDER_STATUS_LABELS = {
    "pending_payment": "Ожидает оплаты",
    "paid": "Ожидает оплаты",
    "confirmed": "Подтвержден",
    "cancelled": "Отменен",
}


def _is_valid_crypto_address(text: str) -> bool:
    return any(p.search(text) for p in _ADDR_PATTERNS)


def _normalize_currency_title(value: str | None) -> str:
    return str(value or "").strip().lower()


def _is_valid_address_for_currency(currency_title: str | None, text: str) -> bool:
    normalized_currency = _normalize_currency_title(currency_title)
    pattern = _CURRENCY_ADDRESS_PATTERNS.get(normalized_currency)
    candidate = str(text or "").strip()
    if not pattern:
        return _is_valid_crypto_address(candidate)
    return bool(pattern.fullmatch(candidate))


def _extract_selected_currency_from_state(state: dict[str, object]) -> str:
    text = str(state.get("text") or "")
    for line in text.splitlines():
        if line.startswith("Вы выбрали получить:"):
            return line.split(":", 1)[1].strip()
    return ""


def _state_includes_transactions(state: dict[str, object]) -> bool:
    return "Транзакции:" in str(state.get("text") or "")


def _order_status_text(status: str) -> str:
    return _ORDER_STATUS_LABELS.get(status, "Ожидает оплаты")


def _is_cancel_confirmation_state(state: dict[str, object]) -> bool:
    text = str(state.get("text") or "")
    return bool(CANCEL_CONFIRM_RE.search(text))


def _build_cancel_confirmation_state(
    *,
    state: dict[str, object],
    order_id: str,
) -> dict[str, object]:
    snapshot = dict(state)
    for field_name in ("text", "text_html", "text_markdown"):
        value = str(snapshot.get(field_name) or "")
        if not value:
            continue
        snapshot[field_name] = CANCEL_CONFIRM_RE.sub(
            lambda m: f"{m.group(1)}{order_id}{m.group(3)}",
            value,
            count=1,
        )
    return snapshot


def _gen_captcha_code(*, exclude: set[str] | None = None) -> str:
    banned = exclude or set()
    while True:
        code = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        if code not in banned:
            return code


def _build_captcha_codes(correct: str = CAPTCHA_CORRECT_CODE) -> list[str]:
    codes = [correct]
    seen = {correct}
    while len(codes) < 4:
        candidate = _gen_captcha_code(exclude=seen)
        seen.add(candidate)
        codes.append(candidate)
    random.shuffle(codes)
    return codes


def _should_inject_start_image(state: dict[str, object] | None) -> bool:
    if not isinstance(state, dict):
        return False
    if state.get("media"):
        return False
    text = str(state.get("text") or "").strip()
    return not text


def _parse_order_template_metadata(state: dict[str, object]) -> dict[str, str] | None:
    text = str(state.get("text") or "")
    if "⚡️Заявка №" not in text:
        return None
    service_requisites = _extract_block_value(text, "Реквизиты сервиса:")
    wallet = _extract_block_value(text, "Адрес, на который поступят чистые средства:")
    currency_title = _extract_inline_value(text, "Валюта:")
    if not service_requisites or not wallet or not currency_title:
        return None
    return {
        "service_requisites": service_requisites,
        "wallet": wallet,
        "currency_title": currency_title,
    }


def _build_order_snapshot_state(
    *,
    state: dict[str, object],
    order_id: str,
    wallet: str,
    status_text: str,
    include_transactions: bool,
    drop_buttons: bool = True,
) -> dict[str, object]:
    snapshot = dict(state)
    for field_name, status_re, wallet_re, tx_re, rich in (
        ("text", ORDER_STATUS_TEXT_RE, ORDER_WALLET_TEXT_RE, ORDER_TX_TEXT_RE, False),
        ("text_html", ORDER_STATUS_HTML_RE, ORDER_WALLET_HTML_RE, ORDER_TX_HTML_RE, True),
        ("text_markdown", ORDER_STATUS_MD_RE, ORDER_WALLET_MD_RE, ORDER_TX_MD_RE, True),
    ):
        value = str(snapshot.get(field_name) or "")
        if not value:
            continue
        value = ORDER_ID_RE.sub(lambda m: m.group(0).replace(m.group(1), order_id), value, count=1)
        if rich:
            value = status_re.sub(
                lambda m: f"{m.group(1)}{status_text}{m.group(3)}",
                value,
                count=1,
            )
            value = wallet_re.sub(
                lambda m: f"{m.group(1)}{wallet}{m.group(3)}",
                value,
                count=1,
            )
        else:
            value = status_re.sub(lambda m: f"{m.group(1)}{status_text}", value, count=1)
            value = wallet_re.sub(lambda m: f"{m.group(1)}{wallet}", value, count=1)
        if not include_transactions:
            value = tx_re.sub("", value)
        snapshot[field_name] = value
    if drop_buttons:
        snapshot["buttons"] = []
        snapshot["button_rows"] = []
    return snapshot


def _extract_block_value(text: str, label: str) -> str:
    marker = f"{label}\n"
    start = text.find(marker)
    if start < 0:
        return ""
    value = text[start + len(marker):].split("\n\n", 1)[0].strip()
    return value


def _extract_inline_value(text: str, label: str) -> str:
    for line in text.splitlines():
        if line.startswith(label):
            return line.split(":", 1)[1].strip()
    return ""


@dataclass
class UserSession:
    state_id: str
    history: list[str] = field(default_factory=list)
    history_page: int = 0
    selected_currency_title: str | None = None
    entered_wallet: str | None = None
    current_order_id: str | None = None
    runtime_message_chat_id: int | None = None
    runtime_message_id: int | None = None


class FlowRuntime:
    def __init__(self, *, project_dir: Path, catalog: FlowCatalog, app_context: AppContext):
        self.project_dir = project_dir
        self.media_dir = project_dir / "data" / "media"
        self.catalog = catalog
        self.app_context = app_context
        self.sessions: dict[int, UserSession] = {}
        self.action_tokens: dict[str, str] = {}
        self.token_actions: dict[str, str] = {}
        self.captcha_passed: set[int] = set()
        self.pending_captcha: dict[int, str] = {}
        self.message_state_ids: dict[tuple[int, int], str] = {}
        self.order_template_state_ids: set[str] = set()
        self.order_templates_by_currency: dict[str, dict[bool, str]] = {}
        for state_id, state in self.catalog.states.items():
            parsed = _parse_order_template_metadata(state)
            if parsed is None:
                continue
            self.order_template_state_ids.add(state_id)
            currency_title = parsed["currency_title"]
            by_tx = self.order_templates_by_currency.setdefault(currency_title, {})
            by_tx.setdefault(_state_includes_transactions(state), state_id)

    def token_for_action(self, action_text: str) -> str:
        existing = self.action_tokens.get(action_text)
        if existing:
            return existing
        token = action_token(action_text)
        self.action_tokens[action_text] = token
        self.token_actions[token] = action_text
        return token

    def _remember_state_message(self, sent_message: Message | None, state_id: str) -> None:
        if sent_message is None:
            return
        self.message_state_ids[(sent_message.chat.id, sent_message.message_id)] = state_id

    def _source_state_id(
        self,
        *,
        session_state_id: str,
        chat_id: int | None,
        message_id: int | None,
    ) -> str:
        if chat_id is not None and message_id is not None:
            mapped = self.message_state_ids.get((chat_id, message_id))
            if mapped:
                return mapped
        return session_state_id

    async def start(self, msg: Message) -> None:
        user = msg.from_user
        if user is None:
            return
        user_id = int(user.id)
        logger.info("User %d sent /start", user_id)
        await self.app_context.rates.get_rates(force=True)

        if user_id not in self.captcha_passed:
            await self._send_captcha(msg, user_id)
            return

        await self._do_start(msg, user_id)

    async def _do_start(self, msg: Message, user_id: int) -> None:
        start_sid = self.catalog.start_state_id
        session = UserSession(state_id=start_sid, history=[start_sid])
        self.sessions[user_id] = session
        logger.info("Starting flow for user %d at state %s", user_id, start_sid)
        await self._send_state_by_id(msg, start_sid, user_id=user_id)
        if WELCOME_STATE_ID in self.catalog.states:
            await self._send_state_by_id(msg, WELCOME_STATE_ID, user_id=user_id)
            session.state_id = WELCOME_STATE_ID
            session.history.append(WELCOME_STATE_ID)

    async def _send_captcha(self, msg: Message, user_id: int) -> None:
        correct = CAPTCHA_CORRECT_CODE
        codes = _build_captcha_codes(correct)
        self.pending_captcha[user_id] = correct
        buttons = [
            [
                InlineKeyboardButton(text=codes[0], callback_data=f"captcha:{user_id}:{codes[0]}"),
                InlineKeyboardButton(text=codes[1], callback_data=f"captcha:{user_id}:{codes[1]}"),
            ],
            [
                InlineKeyboardButton(text=codes[2], callback_data=f"captcha:{user_id}:{codes[2]}"),
                InlineKeyboardButton(text=codes[3], callback_data=f"captcha:{user_id}:{codes[3]}"),
            ],
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        caption = f"🤖 Пройдите проверку\n\nНажмите на кнопку: <b>{correct}</b>"
        captcha_path = self.media_dir / CAPTCHA_IMAGE
        logger.info("Sending captcha to user %d, correct=%s", user_id, correct)
        if captcha_path.exists():
            await msg.answer_photo(
                FSInputFile(str(captcha_path)),
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.answer(caption, reply_markup=markup, parse_mode=ParseMode.HTML)

    async def on_callback(self, cb: CallbackQuery) -> None:
        user = cb.from_user
        if user is None:
            await cb.answer()
            return

        data = str(cb.data or "")
        cb_msg = cb.message if isinstance(cb.message, Message) else None
        user_id = int(user.id)

        # Captcha verification
        if data.startswith("captcha:"):
            parts = data.split(":", 2)
            if len(parts) == 3:
                _, uid_str, code = parts
                try:
                    uid = int(uid_str)
                except ValueError:
                    await cb.answer()
                    return
                if uid != user_id:
                    await cb.answer("Эта капча не для вас.", show_alert=True)
                    return
                expected = self.pending_captcha.get(uid)
                logger.info("Captcha attempt user %d: code=%s expected=%s", uid, code, expected)
                if code == expected:
                    self.captcha_passed.add(uid)
                    self.pending_captcha.pop(uid, None)
                    await cb.answer("✅ Проверка пройдена!")
                    if cb_msg is not None:
                        await self._do_start(cb_msg, uid)
                else:
                    await cb.answer(CAPTCHA_RETRY_TEXT, show_alert=True)
            else:
                await cb.answer()
            return

        # History pagination callbacks
        if data.startswith("history:page:"):
            try:
                page = int(data.split(":")[-1])
            except ValueError:
                await cb.answer()
                return
            session = self.sessions.get(user_id)
            if session is not None and cb_msg is not None:
                session.history_page = page
                await self._send_history_page(cb_msg, user_id, page)
            await cb.answer()
            return

        if data.startswith("history:order:"):
            order_id = data.split(":")[-1]
            if cb_msg is not None:
                await self._send_history_order(cb_msg, order_id, requester_user_id=user_id)
            await cb.answer()
            return

        token = data
        action_text = self.token_actions.get(token, "")
        if not action_text:
            await cb.answer()
            return

        session = self.sessions.get(user_id)
        if session is None:
            if cb_msg is not None:
                await self.start(cb_msg)
            await cb.answer()
            return

        source_state_id = self._source_state_id(
            session_state_id=session.state_id,
            chat_id=cb_msg.chat.id if cb_msg is not None else None,
            message_id=cb_msg.message_id if cb_msg is not None else None,
        )
        logger.info("User %d callback action=%r from state %s", user_id, action_text, source_state_id)

        if action_text in {"🏠 Главная", "В начало"} and cb_msg is not None:
            cb_chat_id = getattr(getattr(cb_msg, "chat", None), "id", None)
            cb_msg_id = getattr(cb_msg, "message_id", None)
            if isinstance(cb_chat_id, int) and isinstance(cb_msg_id, int):
                try:
                    await cb_msg.bot.delete_message(chat_id=cb_chat_id, message_id=cb_msg_id)
                except Exception as e:
                    print(f'Exception caught: {e}')
            if self._is_mid_exchange(session):
                await cb_msg.answer("⚠️ Ваш текущий обмен прерван. Возвращаем вас в главное меню.")
            await self._do_start(cb_msg, user_id)
            await cb.answer()
            return

        if await self._handle_partner_actions(cb, source_state_id, action_text, cb_msg=cb_msg):
            return

        if action_text == "История очисток" and cb_msg is not None:
            cb_chat_id = getattr(getattr(cb_msg, "chat", None), "id", None)
            cb_msg_id = getattr(cb_msg, "message_id", None)
            if isinstance(cb_chat_id, int) and isinstance(cb_msg_id, int):
                try:
                    await cb_msg.bot.delete_message(chat_id=cb_chat_id, message_id=cb_msg_id)
                except Exception as e:
                    print(f'Exception caught: {e}')
            await self._send_history_page(cb_msg, user_id, 0)
            await cb.answer()
            return

        next_state = self.catalog.resolve_action(
            source_state_id, action_text, history=session.history
        )
        if action_text == "Отменить заявку":
            if not self._cancel_current_order(user_id):
                await cb.answer("Нельзя отменить эту заявку.", show_alert=True)
                return

        if action_text == "Проверить оплату" and cb_msg is not None:
            await asyncio.sleep(1)

        if next_state is not None and cb_msg is not None:
            cb_chat_id = getattr(getattr(cb_msg, "chat", None), "id", None)
            cb_msg_id = getattr(cb_msg, "message_id", None)
            session.state_id = next_state
            session.history.append(next_state)
            self._remember_selected_currency(session, next_state)
            logger.info("User %d -> state %s", user_id, next_state)
            await self._send_state_by_id(
                cb_msg, next_state, user_id=user_id,
                edit_chat_id=cb_chat_id, edit_message_id=cb_msg_id,
            )
            await self._send_system_chain(cb_msg, session, user_id=user_id)

        await cb.answer()

    async def _handle_partner_actions(
        self,
        cb: CallbackQuery,
        source_state_id: str,
        action_text: str,
        *,
        cb_msg: Message | None,
    ) -> bool:
        if source_state_id != self.catalog.partner_state_id:
            return False
        if action_text == "Запросить вывод":
            await cb.answer(PARTNER_MIN_WITHDRAW_ALERT, show_alert=True)
            return True
        if action_text == "История операций":
            if cb_msg is not None:
                await cb_msg.answer(PARTNER_EMPTY_HISTORY_TEXT)
            await cb.answer()
            return True
        return False

    async def on_message(self, msg: Message) -> None:
        user = msg.from_user
        if user is None:
            return
        text = str(msg.text or "").strip()
        if text.startswith("/"):
            return
        user_id = int(user.id)
        session = self.sessions.get(user_id)
        if session is None:
            await self.start(msg)
            return

        logger.info("User %d message=%r in state %s", user_id, text[:60], session.state_id)

        if self.catalog.is_address_input_state(session.state_id):
            # Check if user pressed a menu navigation button instead of entering an address
            nav_next = self.catalog.resolve_action(session.state_id, text, history=session.history)
            if nav_next is not None:
                await msg.answer("⚠️ Ваш текущий обмен прерван.")
                session.selected_currency_title = None
                session.current_order_id = None
                if text in {"🏠 Главная", "В начало"} or nav_next == self.catalog.start_state_id:
                    await self._do_start(msg, user_id)
                else:
                    session.state_id = nav_next
                    session.history.append(nav_next)
                    await self._send_state_by_id(msg, nav_next, user_id=user_id)
                    await self._send_system_chain(msg, session, user_id=user_id)
                return

            currency_title = (
                session.selected_currency_title
                or _extract_selected_currency_from_state(self.catalog.states.get(session.state_id) or {})
            )
            if not _is_valid_address_for_currency(currency_title, text):
                logger.info("User %d invalid address: %r", user_id, text[:60])
                if currency_title:
                    await msg.answer(f"❌ Введите корректный адрес кошелька для {currency_title}")
                else:
                    await msg.answer("❌ Введите корректный адрес кошелька")
                return
            session.entered_wallet = text
            next_state = self.catalog.get_address_input_next(session.state_id)
            if next_state:
                order = self._create_order_for_session(msg=msg, session=session, wallet=text)
                if order is not None:
                    session.current_order_id = str(order["order_id"])

                # New message for next step after wallet input
                session.state_id = next_state
                session.history.append(next_state)
                logger.info("User %d address accepted -> state %s", user_id, next_state)
                await self._send_state_by_id(
                    msg, next_state, user_id=user_id,
                )
                await self._send_system_chain(msg, session, user_id=user_id)
            return

        next_state = self.catalog.resolve_action(
            session.state_id, text, history=session.history
        )
        if next_state is None and self.catalog.state_accepts_input(session.state_id):
            next_state = self.catalog.resolve_action(
                session.state_id, text, is_text_input=True, history=session.history
            )
        if not next_state:
            return
        if text in {"🏠 Главная", "В начало"}:
            prev_chat = session.runtime_message_chat_id
            prev_msg_id = session.runtime_message_id
            if isinstance(prev_chat, int) and isinstance(prev_msg_id, int):
                bot = getattr(msg, "bot", None)
                if bot is not None:
                    try:
                        await bot.delete_message(chat_id=prev_chat, message_id=prev_msg_id)
                    except Exception as e:
                        print(f'Exception caught: {e}')
            if self._is_mid_exchange(session):
                await msg.answer("⚠️ Ваш текущий обмен прерван. Возвращаем вас в главное меню.")
            await self._do_start(msg, user_id)
            return

        # Only edit for navigation (Назад)
        edit_chat = None
        edit_msg = None
        if text == "Назад":
            edit_chat = session.runtime_message_chat_id
            edit_msg = session.runtime_message_id

        if self._is_mid_exchange(session) and self._is_main_menu_state(next_state):
            await msg.answer("⚠️ Ваш текущий обмен прерван.")
            session.selected_currency_title = None
            session.current_order_id = None

        session.state_id = next_state
        session.history.append(next_state)
        self._remember_selected_currency(session, next_state)
        logger.info("User %d text resolved -> state %s", user_id, next_state)
        await self._send_state_by_id(
            msg, next_state, user_id=user_id,
            edit_chat_id=edit_chat, edit_message_id=edit_msg,
        )
        await self._send_system_chain(msg, session, user_id=user_id)

    async def _send_history_page(self, msg: Message, user_id: int, page: int) -> None:
        orders_store: OrdersStore | None = self.app_context.orders
        all_orders: list[dict] = []
        if orders_store is not None:
            all_orders = [
                o for o in orders_store.all_orders()
                if o.get("user_id") == user_id
            ]
            all_orders.sort(key=lambda o: o.get("created_at", 0), reverse=True)

        if not all_orders:
            await msg.answer(HISTORY_EMPTY_TEXT)
            return

        total_pages = max(1, math.ceil(len(all_orders) / HISTORY_PAGE_SIZE))
        page = max(0, min(page, total_pages - 1))
        start = page * HISTORY_PAGE_SIZE
        page_orders = all_orders[start: start + HISTORY_PAGE_SIZE]

        await msg.answer(
            "📋 <b>История обменов</b>",
            reply_markup=kb_history_page(page_orders, page, total_pages),
        )

    async def _send_history_order(
        self,
        msg: Message,
        order_id: str,
        *,
        requester_user_id: int | None = None,
    ) -> None:
        orders_store: OrdersStore | None = self.app_context.orders
        if orders_store is None:
            return
        order = orders_store.get_order(order_id)
        if order is None:
            return
        if requester_user_id is not None and int(order.get("user_id") or 0) != requester_user_id:
            return
        live_rates = await self.app_context.rates.get_rates()
        state = self._build_order_state_for_order(
            state_id=self._best_order_template_state_id(
                str(order.get("coin_symbol") or ""),
                include_transactions=False,
            ),
            order=order,
            drop_buttons=True,
            live_rates_usd=live_rates,
        )
        if not state:
            return
        sent_message = await send_state(
            msg,
            state,
            media_dir=self.media_dir,
            token_by_action=self.token_for_action,
        )
        self._remember_state_message(sent_message, self._best_order_template_state_id(
            str(order.get("coin_symbol") or ""),
            include_transactions=False,
        ))

    async def _send_state_by_id(
        self,
        msg: Message,
        state_id: str,
        *,
        user_id: int | None = None,
        edit_chat_id: int | None = None,
        edit_message_id: int | None = None,
    ) -> None:
        base_state = self.catalog.states.get(state_id)
        if not base_state:
            return
        live_rates = await self.app_context.rates.get_rates()
        resolved_user_id = user_id
        if resolved_user_id is None:
            user = msg.from_user
            resolved_user_id = int(user.id) if user is not None else None
        session = self.sessions.get(resolved_user_id) if resolved_user_id is not None else None
        order = self._current_order(session)
        if state_id in self.order_template_state_ids and order is not None and order.get("status") != "cancelled":
            state = self._build_order_state_for_order(
                state_id=state_id,
                order=order,
                drop_buttons=False,
                live_rates_usd=live_rates,
            )
        else:
            state = self._apply_runtime_overrides(base_state, live_rates_usd=live_rates)
            if order is not None and str(order.get("status") or "") == "cancelled" and _is_cancel_confirmation_state(base_state):
                state = _build_cancel_confirmation_state(
                    state=state,
                    order_id=str(order.get("order_id") or ""),
                )
        await self._apply_minimum_amount_override(state)
        logger.debug("Sending state %s", state_id)

        # Try editing the previous message first
        edited = False
        if isinstance(edit_chat_id, int) and isinstance(edit_message_id, int):
            bot = getattr(msg, "bot", None)
            if bot is not None:
                edited = await edit_state(
                    bot,
                    edit_chat_id,
                    edit_message_id,
                    state,
                    media_dir=self.media_dir,
                    token_by_action=self.token_for_action,
                )

        if edited:
            if session is not None:
                session.runtime_message_chat_id = edit_chat_id
                session.runtime_message_id = edit_message_id
        else:
            # Edit failed or not requested — delete old + send new
            if isinstance(edit_chat_id, int) and isinstance(edit_message_id, int):
                bot = getattr(msg, "bot", None)
                if bot is not None:
                    try:
                        await bot.delete_message(chat_id=edit_chat_id, message_id=edit_message_id)
                    except Exception as e:
                        print(f'Exception caught: {e}')
            sent_message = await send_state(
                msg,
                state,
                media_dir=self.media_dir,
                token_by_action=self.token_for_action,
            )
            self._remember_state_message(sent_message, state_id)
            if sent_message is not None and session is not None:
                sent_chat = getattr(getattr(sent_message, "chat", None), "id", None)
                sent_msg_id = getattr(sent_message, "message_id", None)
                if isinstance(sent_chat, int):
                    session.runtime_message_chat_id = sent_chat
                if isinstance(sent_msg_id, int):
                    session.runtime_message_id = sent_msg_id

    async def _send_system_chain(
        self,
        msg: Message,
        session: UserSession,
        *,
        user_id: int | None = None,
        max_hops: int = 4,
    ) -> None:
        seen: set[str] = {session.state_id}
        current = session.state_id
        for _ in range(max_hops):
            if self.catalog.state_has_buttons(current):
                break
            next_state = self.catalog.resolve_system_next(current)
            if not next_state or next_state in seen:
                break
            seen.add(next_state)
            session.state_id = next_state
            session.history.append(next_state)
            self._remember_selected_currency(session, next_state)
            await self._send_state_by_id(msg, next_state, user_id=user_id)
            current = next_state

    def _apply_runtime_overrides(
        self,
        state: dict[str, object],
        *,
        live_rates_usd: dict[str, float] | None = None,
    ) -> dict[str, object]:
        overrides = RuntimeOverrides(
            operator_url=self.app_context.settings.link("support"),
            link_overrides=self.app_context.settings.all_links(),
            sell_wallet_overrides=self.app_context.settings.all_sell_wallets(),
            commission_percent=self.app_context.settings.commission_percent,
        )
        return apply_state_overrides(
            state=state,
            overrides=overrides,
            operator_url_aliases=self.catalog.operator_url_aliases,
            operator_handle_aliases=self.catalog.operator_handle_aliases,
            link_url_aliases=self.catalog.link_url_aliases,
            sell_wallet_aliases=self.catalog.sell_wallet_aliases,
            live_rates_usd=live_rates_usd or {},
        )

    async def _apply_minimum_amount_override(self, state: dict[str, object]) -> None:
        text = str(state.get("text") or "")
        if "Минимальная сумма обмена:" not in text:
            return
        rates_rub = await self.app_context.rates.get_rates_rub()
        btc_rub = rates_rub.get("btc", 0.0)
        if btc_rub <= 0:
            btc_rub = float(FALLBACK_RATES_RUB.get("btc", 0.0))
            logger.warning("minimum_override: live btc_rub=0, using fallback %.0f", btc_rub)
        if btc_rub <= 0:
            return
        min_btc = MINIMUM_RUB / btc_rub
        min_btc_str = f"{min_btc:.4f}".rstrip("0").rstrip(".")
        for field_name, regex in (
            ("text", MIN_AMOUNT_TEXT_RE),
            ("text_html", MIN_AMOUNT_HTML_RE),
            ("text_markdown", MIN_AMOUNT_MD_RE),
        ):
            value = str(state.get(field_name) or "")
            if not value:
                continue
            if field_name == "text":
                state[field_name] = regex.sub(rf"\g<1>{min_btc_str} BTC", value)
            else:
                state[field_name] = regex.sub(rf"\g<1>{min_btc_str} BTC\g<3>", value)

    def _remember_selected_currency(self, session: UserSession, state_id: str) -> None:
        state = self.catalog.states.get(state_id) or {}
        currency_title = _extract_selected_currency_from_state(state)
        if currency_title:
            session.selected_currency_title = currency_title

    def _create_order_for_session(
        self,
        *,
        msg: Message,
        session: UserSession,
        wallet: str,
    ) -> dict[str, object] | None:
        orders_store: OrdersStore | None = self.app_context.orders
        user = msg.from_user
        if orders_store is None or user is None:
            return None
        currency_title = session.selected_currency_title or ""
        if not currency_title:
            return None
        order = orders_store.create_order(
            user_id=int(user.id),
            username=str(user.username or ""),
            wallet=wallet.strip(),
            coin_symbol=currency_title,
            coin_amount=0.0,
            amount_rub=0.0,
            payment_method="",
            bank="",
        )
        session.entered_wallet = wallet.strip()
        return order

    def _current_order(self, session: UserSession | None) -> dict[str, object] | None:
        orders_store: OrdersStore | None = self.app_context.orders
        if session is None or orders_store is None or not session.current_order_id:
            return None
        order = orders_store.get_order(session.current_order_id)
        return dict(order) if order is not None else None

    def _best_order_template_state_id(self, currency_title: str, include_transactions: bool) -> str:
        templates = self.order_templates_by_currency.get(currency_title) or {}
        return (
            templates.get(include_transactions)
            or templates.get(False)
            or templates.get(True)
            or next(iter(self.order_template_state_ids), "")
        )

    def _build_order_state_for_order(
        self,
        *,
        state_id: str,
        order: dict[str, object],
        drop_buttons: bool,
        live_rates_usd: dict[str, float] | None = None,
    ) -> dict[str, object]:
        currency_title = str(order.get("coin_symbol") or "")
        resolved_state_id = state_id
        parsed = _parse_order_template_metadata(self.catalog.states.get(resolved_state_id) or {})
        if (
            resolved_state_id not in self.order_template_state_ids
            or parsed is None
            or parsed.get("currency_title") != currency_title
        ):
            resolved_state_id = self._best_order_template_state_id(
                currency_title,
                include_transactions=False,
            )
        base_state = self.catalog.states.get(resolved_state_id) or {}
        include_transactions = _state_includes_transactions(base_state) and order.get("status") != "cancelled"
        live_state = self._apply_runtime_overrides(base_state, live_rates_usd=live_rates_usd)
        return _build_order_snapshot_state(
            state=live_state,
            order_id=str(order.get("order_id") or ""),
            wallet=str(order.get("wallet") or ""),
            status_text=_order_status_text(str(order.get("status") or "")),
            include_transactions=include_transactions,
            drop_buttons=drop_buttons,
        )

    def _is_mid_exchange(self, session: UserSession) -> bool:
        return bool(session.selected_currency_title or session.current_order_id)

    def _is_main_menu_state(self, state_id: str) -> bool:
        return state_id in {
            self.catalog.start_state_id,
            WELCOME_STATE_ID,
            self.catalog.exchange_info_state_id,
            self.catalog.about_state_id,
            self.catalog.partner_state_id,
            self.catalog.receive_currency_state_id,
        }

    def _cancel_current_order(self, user_id: int) -> bool:
        session = self.sessions.get(user_id)
        orders_store: OrdersStore | None = self.app_context.orders
        order = self._current_order(session)
        if session is None or orders_store is None or order is None:
            return False
        order_id = str(order.get("order_id") or "")
        if not order_id:
            return False
        if not orders_store.mark_cancelled(order_id):
            return False
        return True


def should_handle_runtime_message(message: Message, raw_state: str | None = None) -> bool:
    if isinstance(raw_state, str) and raw_state.startswith("AdminState:"):
        return False
    return not (message.text or "").strip().startswith("/")


async def amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    project_dir = Path(__file__).resolve().parents[1]
    env_path = project_dir / ".env"
    load_dotenv(env_path, override=True)

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty — set it in .env")

    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )

    # Keep the captured lightning state text-only; only backfill media for empty starts.
    start_state = catalog.states.get(catalog.start_state_id)
    if _should_inject_start_image(start_state):
        start_state = dict(start_state)
        start_state["media"] = START_IMAGE
        catalog.states[catalog.start_state_id] = start_state

    env = dotenv_values(env_path)
    default_commission_raw = (env.get("DEFAULT_COMMISSION_PERCENT") or str(DEFAULT_COMMISSION)).strip()
    try:
        default_commission = float(default_commission_raw)
    except ValueError:
        default_commission = DEFAULT_COMMISSION

    link_definitions = tuple(
        LinkDefinition(key=k, label=v, default=DEFAULT_LINKS.get(k, ""))
        for k, v in LINK_LABELS.items()
    )

    config = AdminKitConfig(
        env_path=env_path,
        data_dir=project_dir / "data" / "admin",
        link_definitions=link_definitions,
        default_commission=default_commission,
        sell_wallet_labels=SELL_WALLET_LABELS,
        enable_users=True,
        enable_orders=True,
    )

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        admin_ctx, admin_router = build_admin_components(config, client=client)

        runtime = FlowRuntime(
            project_dir=project_dir,
            catalog=catalog,
            app_context=admin_ctx,
        )

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(admin_router)

        @dp.message(CommandStart())
        async def _start(message: Message) -> None:
            await runtime.start(message)

        @dp.callback_query(F.data.startswith("captcha:"))
        async def _captcha_callback(cb: CallbackQuery) -> None:
            await runtime.on_callback(cb)

        @dp.callback_query(F.data.startswith("a:"))
        async def _callback(cb: CallbackQuery) -> None:
            await runtime.on_callback(cb)

        @dp.callback_query(F.data.startswith("history:"))
        async def _history_callback(cb: CallbackQuery) -> None:
            await runtime.on_callback(cb)

        @dp.message(StateFilter(None), should_handle_runtime_message)
        async def _message(message: Message) -> None:
            await runtime.on_message(message)

        bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        logger.info("Bot started")
        await dp.start_polling(bot)


def run() -> None:
    asyncio.run(amain())