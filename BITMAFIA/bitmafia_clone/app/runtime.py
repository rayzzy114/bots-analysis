from __future__ import annotations
import httpx

import asyncio
import json
import os
import random
import re
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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
    ReplyKeyboardRemove,
)
from dotenv import dotenv_values, load_dotenv

from .catalog import FlowCatalog
from .constants import DEFAULT_LINKS, FALLBACK_RATES
from .context import AppContext
from .handlers.admin import build_admin_router
from .keyboards import kb_admin_order_confirm
from .overrides import RuntimeOverrides, apply_state_overrides
from .qr import generate_wallet_qr, qr_path
from .rates import RateService
from .renderer import action_token, edit_state, send_state
from .storage import OrdersStore, SettingsStore, UsersStore
from .utils import (
    fmt_coin,
    fmt_money,
    parse_admin_ids,
    parse_amount,
    parse_non_negative_amount,
    safe_username,
)

PAYMENT_PROOF_PROMPT = "📸 Прикрепите фото успешной оплаты. После отправки заявка уйдет в админку."
PAYMENT_PROOF_NEED_PHOTO = "Прикрепите именно фото успешной оплаты (чек/скрин)."
PAYMENT_PROOF_SENT = "✅ Фото получено. Заявка передана в админку."
PAYMENT_PROOF_STORED = "✅ Фото получено. Админы пока не настроены, заявка сохранена локально."
PAYMENT_OPERATOR_TEXT = "Если возникнут вопросы по заявке, свяжитесь с оператором."
PARTNER_MIN_WITHDRAW_ALERT = "⚠ Минимальная сумма вывода:\n0.0001 BTC"
PARTNER_EMPTY_HISTORY_TEXT = "Операций по партнерскому счету не производилось."
CAPTCHAS = [
    ("captcha_1.png", "I62ji"),
    ("captcha_2.png", "nqyNh"),
    ("captcha_3.png", "yqRWn"),
    ("photo_5880884889631001926.jpg", "rfp6p"),
]
CAPTCHA_RETRY_TEXT = "❌ Капча нажата неверно. Попробуйте еще раз."
CAPTCHA_CAPTION = "Пройдите капчу для использования бота"
KEYBOARD_REMOVE_SENTINEL = "."


RUB_AMOUNT_RE = re.compile(r"([0-9][0-9\s.,]{1,})\s*(?:RUB|руб)", re.IGNORECASE)
COIN_AMOUNT_RE = re.compile(
    r"([0-9]+(?:[.,][0-9]+)?)\s*(BTC|LTC|XMR|USDT|ETH|TRX|TON)\b",
    re.IGNORECASE,
)
WALLET_RE = re.compile(r"(?:кошелек|кошел[её]к|wallet)\s*:?\s*([^\n]+)", re.IGNORECASE)
PAYMENT_METHOD_ACTIONS = (
    "Оплата по QR",
    "Тинькофф",
    "Сбербанк",
    "Карта",
    "СБП (Система Быстрых Платежей)",
    "Сбербанк QR",
    "Тинькофф QR",
)
CRYPTO_RECEIVE_ACTIONS = ("Bitcoin", "Litecoin", "Monero", "Tether TRC-20")
DATETIME_RE = re.compile(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}")
ORDER_ID_RE = re.compile(r"Обмен #\d+")
PAYMENT_DEADLINE_MINUTES = 120
MINIMUM_RUB = 10_000.0
MINIMUM_RECEIVE_BY_TITLE: dict[str, float] = {
    "Наличные": 300_000.0,
}


@dataclass(frozen=True)
class AssetSpec:
    title: str
    symbol: str
    rate_symbol: str | None
    wallet_key: str | None
    is_fiat: bool = False


ASSET_SPECS: dict[str, AssetSpec] = {
    "Bitcoin": AssetSpec("Bitcoin", "BTC", "BTC", "btc"),
    "BTC": AssetSpec("Bitcoin", "BTC", "BTC", "btc"),
    "Litecoin": AssetSpec("Litecoin", "LTC", "LTC", "ltc"),
    "LTC": AssetSpec("Litecoin", "LTC", "LTC", "ltc"),
    "Monero": AssetSpec("Monero", "XMR", "XMR", "xmr"),
    "XMR": AssetSpec("Monero", "XMR", "XMR", "xmr"),
    "Tether TRC-20": AssetSpec("Tether TRC-20", "USDTTRC", "USDT", "usdt_trc20"),
    "USDTTRC": AssetSpec("Tether TRC-20", "USDTTRC", "USDT", "usdt_trc20"),
    "USDTBEP": AssetSpec("Tether BEP-20", "USDTBEP", "USDT", "usdt_bsc"),
    "RUB": AssetSpec("RUB", "RUB", None, None, is_fiat=True),
}


def _inject_home_button(state: dict[str, Any]) -> None:
    btn: dict[str, Any] = {"text": "🏠 Главная", "type": "KeyboardButtonCallback"}
    rows = state.get("button_rows")
    if isinstance(rows, list):
        state["button_rows"] = rows + [[btn]]
    else:
        state["button_rows"] = [[btn]]


def _gen_captcha_code(*, exclude: set[str] | None = None) -> str:
    banned = exclude or set()
    while True:
        code = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        if code not in banned:
            return code


def _build_captcha_codes(correct: str) -> list[str]:
    codes = [correct]
    seen = {correct}
    while len(codes) < 4:
        candidate = _gen_captcha_code(exclude=seen)
        seen.add(candidate)
        codes.append(candidate)
    random.shuffle(codes)
    return codes


@dataclass
class UserSession:
    state_id: str
    history: list[str] = field(default_factory=list)
    awaiting_payment_proof: bool = False
    payment_context: str = ""
    selected_payment_method: str = ""
    selected_receive_title: str = ""
    selected_amount_currency: str = ""
    amount_options: tuple[str, ...] = ()
    entered_amount: float | None = None
    destination_value: str = ""
    city: str = ""
    quote: ExchangeQuote | None = None
    current_order_id: str = ""
    runtime_message_chat_id: int | None = None
    runtime_message_id: int | None = None
    runtime_message_state_id: str = ""
    menu_message_id: int | None = None
    menu_chat_id: int | None = None
    amount_error_text: str = ""


@dataclass
class ExchangeQuote:
    send_title: str
    send_symbol: str
    send_amount: float
    receive_title: str
    receive_symbol: str
    receive_amount: float
    user_destination: str
    service_wallet: str
    payment_method: str
    amount_currency: str
    deadline_text: str
    city: str = ""


class FlowRuntime:
    def __init__(
        self,
        *,
        project_dir: Path,
        catalog: FlowCatalog,
        app_context: AppContext,
    ):
        self.project_dir = project_dir
        self.raw_dir = project_dir / "data" / "raw"
        self.media_dir = project_dir / "data" / "media"
        self.catalog = catalog
        self.app_context = app_context
        self.sessions: dict[int, UserSession] = {}
        self.action_tokens: dict[str, str] = {}
        self.token_actions: dict[str, str] = {}
        self.captcha_passed: set[int] = set()
        self.pending_captcha: dict[int, str] = {}
        self.payment_proofs_path = project_dir / "data" / "admin" / "payment_proofs.json"
        self.console_logs_enabled = True
        self._ensure_payment_proofs_file()

        self._log(
            "runtime_init",
            states=len(self.catalog.states),
            edges=len(self.catalog.edges),
            start_state=self.catalog.start_state_id,
            manual_input_states=sum(
                1
                for sid in self.catalog.states
                if self.catalog.state_accepts_input(sid)
            ),
            captcha_candidates=self._captcha_candidates_count(),
        )

    def _log(self, event: str, **fields: Any) -> None:
        if not self.console_logs_enabled:
            return
        ts = datetime.now().isoformat(timespec="seconds")
        payload = " ".join(f"{k}={fields[k]!r}" for k in sorted(fields))
        print(f"[{ts}] [runtime] {event} {payload}".rstrip(), flush=True)

    def _state_preview(self, state_id: str) -> str:
        state = self.catalog.states.get(state_id) or {}
        return str(state.get("text") or "").splitlines()[0][:120]

    def _captcha_candidates_count(self) -> int:
        keywords = ("капч", "captcha", "я не робот", "robot")
        count = 0
        for state in self.catalog.states.values():
            blob = "\n".join(
                [
                    str(state.get("text") or ""),
                    str(state.get("text_html") or ""),
                    str(state.get("text_markdown") or ""),
                ]
            ).lower()
            if any(kw in blob for kw in keywords):
                count += 1
        return count

    def token_for_action(self, action_text: str) -> str:
        existing = self.action_tokens.get(action_text)
        if existing:
            return existing
        token = action_token(action_text)
        self.action_tokens[action_text] = token
        self.token_actions[token] = action_text
        return token

    def _payment_method_mapping_for_state(self, state_id: str) -> dict[str, str]:
        state = self.catalog.states.get(state_id) or {}
        rows = state.get("button_rows") or []
        available_actions: list[str] = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, list):
                    continue
                for btn in row:
                    if not isinstance(btn, dict):
                        continue
                    text = str(btn.get("text") or "").strip()
                    if text in PAYMENT_METHOD_ACTIONS and text not in available_actions:
                        available_actions.append(text)

        if not available_actions:
            return {}

        configured_methods = [
            method for method in self.app_context.settings.payment_methods() if str(method or "").strip()
        ]
        if not configured_methods:
            return {}

        mapping: dict[str, str] = {}
        used_actions: set[str] = set()
        assigned_methods: set[str] = set()

        for method in configured_methods:
            matched = self._preferred_payment_action_for_method(method, available_actions)
            if matched and matched not in used_actions:
                mapping[matched] = method
                used_actions.add(matched)
                assigned_methods.add(method)

        remaining_actions = [action for action in available_actions if action not in used_actions]
        remaining_methods = [method for method in configured_methods if method not in assigned_methods]
        for action, method in zip(remaining_actions, remaining_methods):
            mapping[action] = method

        return mapping

    def _preferred_payment_action_for_method(self, method: str, available_actions: list[str]) -> str:
        normalized = (method or "").strip().lower()
        candidates: list[str] = []
        if "сбп" in normalized:
            candidates.append("СБП (Система Быстрых Платежей)")
        if "тин" in normalized and "qr" in normalized:
            candidates.append("Тинькофф QR")
        if "сбер" in normalized and "qr" in normalized:
            candidates.append("Сбербанк QR")
        if "тин" in normalized:
            candidates.append("Тинькофф")
        if "сбер" in normalized:
            candidates.append("Сбербанк")
        if "карт" in normalized:
            candidates.append("Карта")
        if "qr" in normalized:
            candidates.append("Оплата по QR")
        for candidate in candidates:
            if candidate in available_actions:
                return candidate
        return ""

    def _apply_payment_method_button_overrides(self, state: dict[str, Any], state_id: str) -> None:
        mapping = self._payment_method_mapping_for_state(state_id)
        if not mapping:
            return

        def patch_rows(key: str) -> None:
            rows = state.get(key)
            if not isinstance(rows, list):
                return
            patched_rows: list[Any] = []
            for row in rows:
                if not isinstance(row, list):
                    patched_rows.append(row)
                    continue
                patched_row: list[Any] = []
                for btn in row:
                    if not isinstance(btn, dict):
                        patched_row.append(btn)
                        continue
                    original_text = str(btn.get("text") or "").strip()
                    if original_text not in PAYMENT_METHOD_ACTIONS:
                        patched_row.append(btn)
                        continue
                    replacement = mapping.get(original_text)
                    if not replacement:
                        continue
                    patched = dict(btn)
                    patched["callback_text"] = original_text
                    patched["text"] = replacement
                    patched_row.append(patched)
                if patched_row:
                    patched_rows.append(patched_row)
            state[key] = patched_rows

        patch_rows("button_rows")

        buttons = state.get("buttons")
        if isinstance(buttons, list):
            patched_buttons: list[Any] = []
            for btn in buttons:
                if not isinstance(btn, dict):
                    patched_buttons.append(btn)
                    continue
                original_text = str(btn.get("text") or "").strip()
                if original_text not in PAYMENT_METHOD_ACTIONS:
                    patched_buttons.append(btn)
                    continue
                replacement = mapping.get(original_text)
                if not replacement:
                    continue
                patched = dict(btn)
                patched["callback_text"] = original_text
                patched["text"] = replacement
                patched_buttons.append(patched)
            state["buttons"] = patched_buttons

    def _replace_selected_payment_method_in_text(
        self,
        state: dict[str, Any],
        *,
        selected_method: str,
    ) -> None:
        if not selected_method:
            return
        for field in ("text", "text_html", "text_markdown"):
            raw_value = state.get(field)
            if not isinstance(raw_value, str) or not raw_value:
                continue
            present = [action for action in PAYMENT_METHOD_ACTIONS if action in raw_value]
            if len(present) != 1:
                continue
            state[field] = raw_value.replace(present[0], selected_method, 1)

    def _selected_payment_method(self, session: UserSession | None) -> str:
        if session is None:
            return ""
        selected = str(session.selected_payment_method or "").strip()
        if not selected:
            return ""
        if selected not in self.app_context.settings.payment_methods():
            session.selected_payment_method = ""
            return ""
        return selected

    def _state_text_blob(self, state_id: str) -> str:
        state = self.catalog.states.get(state_id) or {}
        return "\n".join(
            [
                str(state.get("text") or ""),
                str(state.get("text_html") or ""),
                str(state.get("text_markdown") or ""),
            ]
        )

    def _state_is_receive_choice(self, state_id: str) -> bool:
        state = self.catalog.states.get(state_id) or {}
        return str(state.get("text") or "").strip() == "Выберите валюту которую вы получаете:"

    def _state_is_amount_choice(self, state_id: str) -> bool:
        state = self.catalog.states.get(state_id) or {}
        return str(state.get("text") or "").strip() == "В какой валюте Вы хотите указать сумму?"

    def _state_is_amount_input(self, state_id: str) -> bool:
        state = self.catalog.states.get(state_id) or {}
        return str(state.get("text") or "").startswith("Введите, сколько ")

    def _state_is_destination_input(self, state_id: str) -> bool:
        state = self.catalog.states.get(state_id) or {}
        return str(state.get("text") or "").startswith("Введите реквизиты, на которые хотите получить ")

    def _state_is_city_input(self, state_id: str) -> bool:
        state = self.catalog.states.get(state_id) or {}
        return str(state.get("text") or "").startswith("Введите желаемый город")

    def _state_is_confirm_template(self, state: dict[str, Any]) -> bool:
        return str(state.get("text") or "").startswith("Подтвердите создание заявки")

    def _state_is_order_template(self, state: dict[str, Any]) -> bool:
        return str(state.get("text") or "").startswith("Обмен #")

    def _state_is_payment_template(self, state: dict[str, Any]) -> bool:
        return str(state.get("text") or "").startswith("Оплата обмена #")

    def _state_is_payment_qr_template(self, state: dict[str, Any]) -> bool:
        return str(state.get("text") or "").strip() == "QR-код для оплаты"

    def _state_is_sticky(self, session: UserSession, state_id: str, state: dict[str, Any]) -> bool:
        if state_id == self.catalog.start_state_id:
            return True
        if self._is_input_state(session, state_id):
            return True
        if self._state_is_confirm_template(state):
            return True
        if self._state_is_order_template(state):
            return True
        if self._state_is_payment_template(state):
            return True
        if self._state_is_payment_qr_template(state):
            return True
        text = str(state.get("text") or "").strip()
        if text == "Если у Вас есть действующий промокод, введите его":
            return True
        return False

    def _is_fiat_receive_flow(self, session: UserSession | None) -> bool:
        return session is not None and self._receive_spec(session).symbol == "RUB"

    def _should_replace_btc_amount_choice_with_rub(self, session: UserSession | None, state_id: str) -> bool:
        if session is None or not self._is_fiat_receive_flow(session) or not self._state_is_amount_choice(state_id):
            return False
        state = self.catalog.states.get(state_id) or {}
        texts = [
            str(btn.get("text") or "").strip()
            for row in state.get("button_rows") or []
            if isinstance(row, list)
            for btn in row
            if isinstance(btn, dict)
        ]
        return "BTC" in texts and any(text.startswith("USDT") for text in texts)

    def _state_is_cancel_template(self, state: dict[str, Any]) -> bool:
        first_line = str(state.get("text") or "").splitlines()[0].strip().lower()
        return first_line.startswith("обмен #") and first_line.endswith("отменен")

    def _reset_quote(self, session: UserSession) -> None:
        session.entered_amount = None
        session.destination_value = ""
        session.city = ""
        session.quote = None
        session.current_order_id = ""

    def _remember_receive_choice(self, session: UserSession, action_text: str, state_id: str) -> None:
        if not self._state_is_receive_choice(state_id):
            return
        action = (action_text or "").strip()
        if not action or action == "Назад":
            return
        mapped_method = self._match_payment_method(action_text, state_id=state_id)
        session.selected_receive_title = mapped_method or action
        session.selected_amount_currency = ""
        session.amount_options = ()
        self._reset_quote(session)

    def _remember_amount_choice(self, session: UserSession, action_text: str, state_id: str) -> None:
        if not self._state_is_amount_choice(state_id):
            return
        action = (action_text or "").strip()
        if not action or action == "Назад":
            return
        if self._should_replace_btc_amount_choice_with_rub(session, state_id) and action == "BTC":
            action = "RUB"
        session.selected_amount_currency = action
        state = self.catalog.states.get(state_id) or {}
        options: list[str] = []
        for row in state.get("button_rows") or []:
            if not isinstance(row, list):
                continue
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                text = str(btn.get("text") or "").strip()
                if text and text != "Назад":
                    options.append(text)
        session.amount_options = tuple(dict.fromkeys(options))
        self._reset_quote(session)

    def _spec_for_token(self, token: str, *, receive_title: str = "") -> AssetSpec:
        raw = (token or "").strip()
        if not raw:
            return ASSET_SPECS["RUB"]
        if raw in ASSET_SPECS:
            return ASSET_SPECS[raw]
        if raw in PAYMENT_METHOD_ACTIONS or raw == "Наличные":
            return AssetSpec(raw, "RUB", None, None, is_fiat=True)
        if receive_title and raw == receive_title:
            if raw in ASSET_SPECS:
                return ASSET_SPECS[raw]
            return AssetSpec(raw, "RUB", None, None, is_fiat=True)
        return AssetSpec(raw, raw.upper(), None, None)

    def _receive_spec(self, session: UserSession) -> AssetSpec:
        title = (session.selected_receive_title or "").strip()
        if not title:
            return ASSET_SPECS["RUB"]
        return self._spec_for_token(title, receive_title=title)

    def _other_amount_option(self, session: UserSession) -> str:
        selected = (session.selected_amount_currency or "").strip()
        for option in session.amount_options:
            if self._should_replace_btc_amount_choice_with_rub(session, session.state_id) and option == "BTC":
                option = "RUB"
            if option != selected:
                return option
        return ""

    def _apply_amount_choice_overrides(self, state: dict[str, Any], *, session: UserSession | None) -> None:
        state_id = str(session.state_id if session else "")
        if not self._should_replace_btc_amount_choice_with_rub(session, state_id):
            return

        for key in ("button_rows", "buttons"):
            rows = state.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, list):
                    for btn in row:
                        if isinstance(btn, dict) and str(btn.get("text") or "").strip() == "BTC":
                            btn["text"] = "RUB"
                elif isinstance(row, dict) and str(row.get("text") or "").strip() == "BTC":
                    row["text"] = "RUB"

    def _override_next_state(self, session: UserSession, action_text: str, next_state: str | None) -> str | None:
        if next_state is None:
            return None
        if not self._is_fiat_receive_flow(session):
            return next_state
        if self._should_replace_btc_amount_choice_with_rub(session, session.state_id) and action_text in {"BTC", "RUB"}:
            return "7397e2a0d871b02aebeafb3cf58702f4"
        if session.state_id == "d391ab9a83fd5470c66dad08e9d8202c" and next_state == "130db6ee61f26215b6c328e6555a8a2a":
            return "3ffc5596982df1b27c8cb7bdf80d2bc8"
        return next_state

    def _commit_transition(self, session: UserSession, *, action_text: str, next_state: str) -> None:
        if action_text == "Назад":
            if session.history:
                session.history.pop()
            if session.history and session.history[-1] != next_state:
                session.history.append(next_state)
            elif not session.history:
                session.history = [next_state]
        else:
            session.history.append(next_state)
        session.state_id = next_state

    def _back_history_target(self, session: UserSession) -> str | None:
        if len(session.history) >= 2:
            return session.history[-2]
        return None

    def _rate_with_commission(self, spec: AssetSpec, *, buying: bool, live_rates_rub: dict[str, float]) -> float:
        if spec.symbol == "RUB":
            return 1.0
        rate_symbol = spec.rate_symbol or spec.symbol
        base_rate = float(live_rates_rub.get(rate_symbol, 0.0))
        fee = max(float(self.app_context.settings.commission_percent), 0.0) / 100.0
        return base_rate * (1.0 + fee if buying else 1.0 - fee)

    def _compute_receive_amount(
        self,
        send_amount: float,
        *,
        send_spec: AssetSpec,
        receive_spec: AssetSpec,
        live_rates_rub: dict[str, float],
    ) -> float:
        rub_value = send_amount if send_spec.symbol == "RUB" else send_amount * self._rate_with_commission(
            send_spec,
            buying=False,
            live_rates_rub=live_rates_rub,
        )
        if rub_value <= 0:
            self._log("rate_zero_warning", send_symbol=send_spec.symbol, send_amount=send_amount)
            return 0.0
        if receive_spec.symbol == "RUB":
            return float(round(rub_value))
        buy_rate = self._rate_with_commission(receive_spec, buying=True, live_rates_rub=live_rates_rub)
        if buy_rate <= 0:
            self._log("rate_zero_warning", receive_symbol=receive_spec.symbol)
            return 0.0
        return rub_value / buy_rate

    def _compute_send_amount(
        self,
        receive_amount: float,
        *,
        send_spec: AssetSpec,
        receive_spec: AssetSpec,
        live_rates_rub: dict[str, float],
    ) -> float:
        rub_target = receive_amount if receive_spec.symbol == "RUB" else receive_amount * self._rate_with_commission(
            receive_spec,
            buying=True,
            live_rates_rub=live_rates_rub,
        )
        if send_spec.symbol == "RUB":
            return float(round(rub_target))
        sell_rate = self._rate_with_commission(send_spec, buying=False, live_rates_rub=live_rates_rub)
        if sell_rate <= 0:
            return 0.0
        return rub_target / sell_rate

    def _service_wallet_for_spec(self, spec: AssetSpec) -> str:
        wallet_key = spec.wallet_key or ""
        if not wallet_key:
            return ""
        return self.app_context.settings.sell_wallet(wallet_key).strip()

    def _payment_wallet_key(self, quote: ExchangeQuote | None) -> str:
        if quote is None:
            return ""
        send_spec = self._spec_for_token(quote.send_title, receive_title=quote.receive_title)
        wallet_key = str(send_spec.wallet_key or "").strip().lower()
        if wallet_key:
            return wallet_key
        for spec in ASSET_SPECS.values():
            if spec.symbol == quote.send_symbol and spec.wallet_key:
                return str(spec.wallet_key).strip().lower()
        return ""

    def _ensure_payment_qr(self, quote: ExchangeQuote | None) -> Path | None:
        if quote is None:
            return None
        wallet_key = self._payment_wallet_key(quote)
        wallet_value = str(quote.service_wallet or "").strip()
        if not wallet_key or not wallet_value:
            return None
        path = qr_path(self.project_dir, wallet_key)
        if path.exists():
            return path
        return generate_wallet_qr(self.project_dir, wallet_key, wallet_value)

    def _format_amount_plain(self, amount: float, symbol: str) -> str:
        if symbol == "RUB":
            return f"{fmt_money(amount)} RUB"
        if symbol.startswith("USDT"):
            return f"{fmt_coin(amount)} {symbol}"
        return f"{amount:.4f}".rstrip("0").rstrip(".") + f" {symbol}"

    def _format_amount_bold(self, amount: float, symbol: str) -> str:
        return f"<strong>{self._format_amount_plain(amount, symbol)}</strong>"

    def _format_amount_markdown(self, amount: float, symbol: str) -> str:
        return f"**{self._format_amount_plain(amount, symbol)}**"

    def _format_amount_code(self, amount: float, symbol: str) -> str:
        if symbol == "RUB":
            return f"<code>{fmt_money(amount)}</code> RUB"
        if symbol.startswith("USDT"):
            return f"<code>{fmt_coin(amount)}</code> {symbol}"
        return f"<code>{amount:.4f}".rstrip("0").rstrip(".") + f"</code> {symbol}"

    def _format_amount_code_markdown(self, amount: float, symbol: str) -> str:
        if symbol == "RUB":
            return f"`{fmt_money(amount)}` RUB"
        if symbol.startswith("USDT"):
            return f"`{fmt_coin(amount)}` {symbol}"
        return f"`{amount:.4f}".rstrip("0").rstrip(".") + f"` {symbol}"

    def _build_quote_context(self, quote: ExchangeQuote) -> str:
        lines = [
            f"Направление: {quote.send_title} – {quote.receive_title}",
            f"Отдаете: {self._format_amount_plain(quote.send_amount, quote.send_symbol)}",
            f"Получаете: {self._format_amount_plain(quote.receive_amount, quote.receive_symbol)}",
        ]
        if quote.user_destination:
            lines.append(f"Ваши реквизиты/Доп.Инфо: {quote.user_destination}")
        if quote.city:
            lines.append(f"Город: {quote.city}")
        if quote.service_wallet:
            lines.append(f"Кошелек сервиса: {quote.service_wallet}")
        return "\n".join(lines)

    async def _minimum_amount_for_input(self, session: UserSession) -> tuple[float, AssetSpec] | None:
        if not session.selected_receive_title or not session.selected_amount_currency:
            return None

        input_spec = self._spec_for_token(
            session.selected_amount_currency,
            receive_title=session.selected_receive_title,
        )

        import math
        minimum_rub = float(MINIMUM_RECEIVE_BY_TITLE.get(session.selected_receive_title, MINIMUM_RUB))

        # RUB input: minimum is just the RUB threshold directly, no rate lookup needed
        if input_spec.symbol == "RUB" or input_spec.is_fiat:
            return math.ceil(minimum_rub), input_spec

        live_rates_rub = await self._get_live_rates_rub()
        rate_key = input_spec.rate_symbol or input_spec.symbol
        rate_rub = float(live_rates_rub.get(rate_key, 0.0))
        if rate_rub <= 0:
            # Live fetch failed — fall back to hardcoded rates so minimum is never bypassed
            rate_rub = float(FALLBACK_RATES.get(rate_key.lower(), 0.0))
        if rate_rub <= 0:
            return None

        minimum_send = minimum_rub / rate_rub
        if minimum_send <= 0:
            return None
        # Round UP to display precision so user can always enter the shown value.
        if input_spec.symbol.startswith("USDT"):
            minimum_send = math.ceil(minimum_send * 100) / 100
        else:
            minimum_send = math.ceil(minimum_send * 10000) / 10000
        return minimum_send, input_spec

    async def _ensure_quote(self, session: UserSession) -> ExchangeQuote | None:
        if not session.selected_receive_title or not session.selected_amount_currency or session.entered_amount is None:
            return None

        receive_spec = self._receive_spec(session)
        input_spec = self._spec_for_token(
            session.selected_amount_currency,
            receive_title=session.selected_receive_title,
        )
        other_option = self._other_amount_option(session)
        other_spec = self._spec_for_token(other_option, receive_title=session.selected_receive_title) if other_option else input_spec
        live_rates_rub = await self._get_live_rates_rub()

        if input_spec.symbol == receive_spec.symbol:
            receive_amount = float(session.entered_amount)
            send_spec = other_spec
            send_amount = self._compute_send_amount(
                receive_amount,
                send_spec=send_spec,
                receive_spec=receive_spec,
                live_rates_rub=live_rates_rub,
            )
        else:
            send_spec = input_spec
            send_amount = float(session.entered_amount)
            receive_amount = self._compute_receive_amount(
                send_amount,
                send_spec=send_spec,
                receive_spec=receive_spec,
                live_rates_rub=live_rates_rub,
            )

        payment_method = receive_spec.title if receive_spec.symbol == "RUB" else ""
        quote = ExchangeQuote(
            send_title=send_spec.title,
            send_symbol=send_spec.symbol,
            send_amount=send_amount,
            receive_title=receive_spec.title,
            receive_symbol=receive_spec.symbol,
            receive_amount=receive_amount,
            user_destination=session.destination_value,
            service_wallet=self._service_wallet_for_spec(send_spec),
            payment_method=payment_method,
            amount_currency=session.selected_amount_currency,
            deadline_text=(datetime.now() + timedelta(minutes=PAYMENT_DEADLINE_MINUTES)).strftime("%d.%m.%Y %H:%M:%S"),
            city=session.city,
        )
        session.quote = quote
        return quote

    def _replace_line(self, value: str, prefix: str, replacement: str) -> str:
        pattern = re.compile(rf"({re.escape(prefix)})([^\n]+)")
        return pattern.sub(lambda m: f"{m.group(1)}{replacement}", value, count=1)

    def _replace_first_datetime(self, value: str, deadline_text: str) -> str:
        return DATETIME_RE.sub(deadline_text, value, count=1)

    def _replace_first_order_id(self, value: str, order_id: str) -> str:
        return ORDER_ID_RE.sub(f"Обмен #{order_id}", value, count=1)

    async def _apply_quote_state(self, state: dict[str, Any], *, session: UserSession) -> None:
        is_amount_input_state = self._state_matches_amount_input(state)
        minimum_input = await self._minimum_amount_for_input(session) if is_amount_input_state else None
        quote = session.quote
        if quote is None and minimum_input is None and not self._state_is_cancel_template(state):
            return

        order_id = session.current_order_id or "000000"
        for field in ("text", "text_html", "text_markdown"):
            raw_value = state.get(field)
            if not isinstance(raw_value, str) or not raw_value:
                continue

            if is_amount_input_state:
                updated = raw_value
                selected_symbol = session.selected_amount_currency or ""
                if selected_symbol:
                    if field == "text_html":
                        selected_markup = f"<strong>{selected_symbol}</strong>"
                    elif field == "text_markdown":
                        selected_markup = f"**{selected_symbol}**"
                    else:
                        selected_markup = selected_symbol
                    updated = self._replace_line(updated, "Введите, сколько ", f"{selected_markup} у Вас есть")
                if minimum_input is not None:
                    minimum_value, minimum_spec = minimum_input
                    if field == "text_html":
                        minimum_markup = self._format_amount_bold(minimum_value, minimum_spec.symbol)
                    elif field == "text_markdown":
                        minimum_markup = self._format_amount_markdown(minimum_value, minimum_spec.symbol)
                    else:
                        minimum_markup = self._format_amount_plain(minimum_value, minimum_spec.symbol)
                    updated = self._replace_line(
                        updated,
                        "⚠️ Сумма обмена по выбранному направлению должна быть не менее ",
                        minimum_markup,
                    )
                state[field] = updated
                continue

            if self._state_is_cancel_template(state):
                state[field] = self._replace_first_order_id(raw_value, order_id)
                continue

            if self._state_matches_destination_input(state):
                symbol_markup = quote.receive_symbol
                if field == "text_html":
                    symbol_markup = f"<strong>{quote.receive_symbol}</strong>"
                elif field == "text_markdown":
                    symbol_markup = f"**{quote.receive_symbol}**"
                state[field] = self._replace_line(
                    raw_value,
                    "Введите реквизиты, на которые хотите получить ",
                    symbol_markup,
                )
                continue

            if self._state_is_confirm_template(state) or self._state_is_order_template(state):
                if field == "text":
                    give_value = self._format_amount_plain(quote.send_amount, quote.send_symbol)
                    receive_value = self._format_amount_plain(quote.receive_amount, quote.receive_symbol)
                    requisites_value = quote.user_destination
                    city_value = quote.city
                elif field == "text_html":
                    give_value = self._format_amount_bold(quote.send_amount, quote.send_symbol)
                    receive_value = self._format_amount_bold(quote.receive_amount, quote.receive_symbol)
                    requisites_value = f"<strong>{quote.user_destination}</strong>" if quote.user_destination else ""
                    city_value = f"<strong>{quote.city}</strong>" if quote.city else ""
                else:
                    give_value = self._format_amount_markdown(quote.send_amount, quote.send_symbol)
                    receive_value = self._format_amount_markdown(quote.receive_amount, quote.receive_symbol)
                    requisites_value = f"**{quote.user_destination}**" if quote.user_destination else ""
                    city_value = f"**{quote.city}**" if quote.city else ""

                updated = self._replace_line(raw_value, "Направление: ", f"{quote.send_title} – {quote.receive_title}")
                updated = self._replace_line(updated, "Отдаете: ", give_value)
                updated = self._replace_line(updated, "Получаете: ", receive_value)
                if "Ваши реквизиты/Доп.Инфо:" in updated:
                    updated = self._replace_line(updated, "Ваши реквизиты/Доп.Инфо: ", requisites_value)
                if "Город:" in updated:
                    updated = self._replace_line(updated, "Город: ", city_value)
                if self._state_is_order_template(state):
                    updated = self._replace_first_order_id(updated, order_id)
                    updated = self._replace_first_datetime(updated, quote.deadline_text)
                state[field] = updated
                continue

            if self._state_is_payment_template(state):
                if field == "text":
                    amount_value = self._format_amount_plain(quote.send_amount, quote.send_symbol)
                    wallet_value = quote.service_wallet
                elif field == "text_html":
                    amount_value = self._format_amount_code(quote.send_amount, quote.send_symbol)
                    wallet_value = f"<code>{quote.service_wallet}</code>"
                else:
                    amount_value = self._format_amount_code_markdown(quote.send_amount, quote.send_symbol)
                    wallet_value = f"`{quote.service_wallet}`"
                updated = re.sub(r"Оплата обмена #\d+", f"Оплата обмена #{order_id}", raw_value, count=1)
                updated = self._replace_line(updated, "Сумма: ", amount_value)
                updated = self._replace_line(updated, "Кошелек: ", wallet_value)
                updated = self._replace_first_datetime(updated, quote.deadline_text)
                state[field] = updated
                continue

    def _state_matches_destination_input(self, state: dict[str, Any]) -> bool:
        return str(state.get("text") or "").startswith("Введите реквизиты, на которые хотите получить ")

    def _state_matches_amount_input(self, state: dict[str, Any]) -> bool:
        return str(state.get("text") or "").startswith("Введите, сколько ")

    def _is_input_state(self, session: UserSession, state_id: str) -> bool:
        if session.awaiting_payment_proof:
            return True
        if self._state_is_amount_input(state_id):
            return True
        if self._state_is_city_input(state_id):
            return True
        if self._state_is_destination_input(state_id):
            return True
        return False

    def _normalize_message_action(self, action_text: str, *, state_id: str) -> str:
        action = (action_text or "").strip()
        if not action:
            return ""
        mapping = self._payment_method_mapping_for_state(state_id)
        for original_action, method in mapping.items():
            if method.strip().lower() == action.lower():
                return original_action
        return action

    def _should_hide_menu(self, session: UserSession, state_id: str, state: dict[str, Any]) -> bool:
        _ = state
        if session.awaiting_payment_proof:
            return True
        if self._state_is_amount_input(state_id):
            return True
        if self._state_is_city_input(state_id):
            return True
        if self._state_is_destination_input(state_id):
            return True
        return False

    async def start(self, msg: Message) -> None:
        user = msg.from_user
        if user is None:
            return
        user_id = int(user.id)
        await self.app_context.rates.get_rates(force=True)
        if user_id not in self.captcha_passed:
            await self._send_captcha(msg, user_id)
            return
        await self._do_start(msg, user_id)

    async def _do_start(self, msg: Message, user_id: int) -> None:
        start_sid = self.catalog.start_state_id
        session = UserSession(state_id=start_sid, history=[start_sid])
        self.sessions[user_id] = session
        self._log("start", user_id=user_id, state_id=start_sid, preview=self._state_preview(start_sid))
        await self._send_state_by_id(msg, start_sid, session=session)
        await self._send_start_chain(msg, session)

    async def _send_captcha(self, msg: Message, user_id: int) -> None:
        captcha_img, correct = random.choice(CAPTCHAS)
        codes = _build_captcha_codes(correct)
        self.pending_captcha[user_id] = correct
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=codes[0], callback_data=f"captcha:{user_id}:{codes[0]}"),
                    InlineKeyboardButton(text=codes[1], callback_data=f"captcha:{user_id}:{codes[1]}"),
                ],
                [
                    InlineKeyboardButton(text=codes[2], callback_data=f"captcha:{user_id}:{codes[2]}"),
                    InlineKeyboardButton(text=codes[3], callback_data=f"captcha:{user_id}:{codes[3]}"),
                ],
            ]
        )
        caption = f"🤖 Пройдите проверку\n\nНажмите на кнопку: <b>{correct}</b>"
        captcha_path = self.media_dir / captcha_img
        self._log("send_captcha", user_id=user_id, correct=correct, has_media=captcha_path.exists())
        if captcha_path.exists():
            await msg.answer_photo(
                FSInputFile(str(captcha_path)),
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML,
            )
        else:
            await msg.answer(caption, reply_markup=markup, parse_mode=ParseMode.HTML)

    async def _send_start_chain(self, msg: Message, session: UserSession) -> None:
        current = session.state_id
        next_state = self.catalog.resolve_system_next(current)
        if not next_state or next_state == current:
            self._log("start_chain_skip", from_state=current, next_state=next_state)
            return

        session.state_id = next_state
        session.history.append(next_state)
        self._log(
            "start_chain_next",
            from_state=current,
            to_state=next_state,
            preview=self._state_preview(next_state),
        )
        await self._send_state_by_id(msg, next_state, session=session)

    async def on_callback(self, cb: CallbackQuery) -> None:
        user = cb.from_user
        if user is None:
            await cb.answer()
            return

        data = str(cb.data or "")
        callback_message = cb.message if isinstance(cb.message, Message) or hasattr(cb.message, "answer") else None
        user_id = int(user.id)

        if data.startswith("captcha:"):
            parts = data.split(":", 2)
            if len(parts) != 3:
                await cb.answer()
                return
            _, uid_raw, code = parts
            try:
                expected_user_id = int(uid_raw)
            except ValueError:
                await cb.answer()
                return
            if expected_user_id != user_id:
                await cb.answer("Эта капча не для вас.", show_alert=True)
                return
            expected_code = self.pending_captcha.get(user_id)
            self._log("captcha_attempt", user_id=user_id, code=code, expected=expected_code)
            if code != expected_code:
                await cb.answer(CAPTCHA_RETRY_TEXT, show_alert=True)
                if callback_message is not None:
                    try:
                        await callback_message.delete()
                    except Exception as e:
                        print(f'Exception caught: {e}')
                    await self._send_captcha(callback_message, user_id)
                return
            self.captcha_passed.add(user_id)
            self.pending_captcha.pop(user_id, None)
            await cb.answer("✅ Проверка пройдена!")
            if callback_message is not None:
                await self._do_start(callback_message, user_id)
            return

        token = data
        action_text = self.token_actions.get(token, "")
        if not action_text:
            self._log("callback_unknown_token", token=token)
            await cb.answer()
            return

        session = self.sessions.get(user_id)
        if session is None:
            if callback_message is not None:
                await self.start(callback_message)
            await cb.answer()
            return

        selected_method = self._match_payment_method(action_text, state_id=session.state_id)
        if selected_method:
            session.selected_payment_method = selected_method
        self._remember_receive_choice(session, action_text, session.state_id)
        self._remember_amount_choice(session, action_text, session.state_id)

        self._log(
            "callback_action",
            user_id=user_id,
            state_id=session.state_id,
            action=action_text,
        )

        if action_text in {"🏠 Главная", "В начало"}:
            await cb.answer()
            if callback_message is not None:
                try:
                    await callback_message.delete()
                except Exception as e:
                    print(f'Exception caught: {e}')
                await self._do_start(callback_message, user_id)
            return

        if await self._handle_partner_actions(cb, session, action_text, callback_message=callback_message):
            return

        if action_text == "✅ Я оплатил" and callback_message is not None:
            session.awaiting_payment_proof = True
            if session.quote is not None:
                session.payment_context = self._build_quote_context(session.quote)
            else:
                session.payment_context = await self._state_text(session.state_id, session=session)
            self._log("awaiting_payment_proof_on", user_id=user_id, state_id=session.state_id)
            await callback_message.answer(PAYMENT_PROOF_PROMPT)
            await cb.answer()
            return

        next_state = self._back_history_target(session) if action_text == "Назад" else None
        if next_state is None:
            next_state = self.catalog.resolve_action(
                session.state_id,
                action_text,
                history=session.history,
            )
        next_state = self._override_next_state(session, action_text, next_state)

        if action_text == "Проверить оплату" and callback_message is not None:
            await asyncio.sleep(1)

        if next_state and callback_message is not None:
            cb_chat_id = getattr(getattr(callback_message, "chat", None), "id", None)
            cb_msg_id = getattr(callback_message, "message_id", None)
            self._log("callback_transition", from_state=session.state_id, action=action_text, to_state=next_state)
            self._commit_transition(session, action_text=action_text, next_state=next_state)
            session.awaiting_payment_proof = False
            await self._send_state_by_id(
                callback_message, next_state, session=session,
                edit_chat_id=cb_chat_id, edit_message_id=cb_msg_id,
            )
            await self._send_system_chain(callback_message, session)
        else:
            self._log("callback_no_transition", from_state=session.state_id, action=action_text)

        await cb.answer()

    async def _handle_partner_actions(
        self,
        cb: CallbackQuery,
        session: UserSession,
        action_text: str,
        *,
        callback_message: Message | None,
    ) -> bool:
        if session.state_id != self.catalog.partner_state_id:
            return False

        if action_text == "Запросить вывод":
            self._log("partner_withdraw_alert", state_id=session.state_id)
            await cb.answer(PARTNER_MIN_WITHDRAW_ALERT, show_alert=True)
            return True

        if action_text == "История операций":
            self._log("partner_history_empty", state_id=session.state_id)
            if callback_message is not None:
                await callback_message.answer(PARTNER_EMPTY_HISTORY_TEXT)
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

        if session.awaiting_payment_proof:
            self._log("payment_proof_message", user_id=user_id, has_photo=bool(msg.photo))
            await self._handle_payment_proof(msg, session)
            return

        if not text:
            self._log("message_ignored_non_text", user_id=user_id, state_id=session.state_id)
            return

        normalized_text = self._normalize_message_action(text, state_id=session.state_id)

        if normalized_text in {"🏠 Главная", "В начало"}:
            await self._do_start(msg, user_id)
            return

        selected_method = self._match_payment_method(normalized_text, state_id=session.state_id)
        if selected_method:
            session.selected_payment_method = selected_method
        self._remember_receive_choice(session, normalized_text, session.state_id)
        self._remember_amount_choice(session, normalized_text, session.state_id)

        if self._state_is_amount_input(session.state_id):
            parsed_amount = parse_amount(text)
            if parsed_amount is None:
                return
            if parsed_amount is not None:
                minimum_input = await self._minimum_amount_for_input(session)
                if minimum_input is not None and parsed_amount < minimum_input[0]:
                    self._reset_quote(session)
                    self._log(
                        "amount_below_minimum",
                        user_id=user_id,
                        state_id=session.state_id,
                        entered_amount=parsed_amount,
                        minimum_amount=minimum_input[0],
                        symbol=minimum_input[1].symbol,
                    )
                    minimum_amount = self._format_amount_bold(minimum_input[0], minimum_input[1].symbol)
                    try:
                        await msg.answer(
                            f"Минимальная сумма обмена: {minimum_amount}",
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception as e:
                        print(f'Exception caught: {e}')
                    return
                if session.entered_amount != parsed_amount:
                    self._reset_quote(session)
                session.entered_amount = parsed_amount
                await self._ensure_quote(session)

        if self._state_is_city_input(session.state_id):
            if session.city != text:
                session.current_order_id = ""
            session.city = text
            quote = await self._ensure_quote(session)
            if quote is not None:
                quote.city = text
            if not session.current_order_id:
                session.current_order_id = self._create_pending_order(msg=msg, session=session)

        if self._state_is_destination_input(session.state_id):
            if session.destination_value != text:
                session.current_order_id = ""
            session.destination_value = text
            quote = await self._ensure_quote(session)
            if quote is not None:
                quote.user_destination = text
            if not session.current_order_id:
                session.current_order_id = self._create_pending_order(msg=msg, session=session)

        next_state = self._back_history_target(session) if normalized_text == "Назад" else None
        if next_state is None:
            next_state = self.catalog.resolve_action(
                session.state_id,
                normalized_text,
                history=session.history,
            )
        if next_state is None and self.catalog.state_accepts_input(session.state_id):
            self._log("manual_input_try", user_id=user_id, state_id=session.state_id, text=text)
            next_state = self.catalog.resolve_action(
                session.state_id,
                normalized_text,
                is_text_input=True,
                history=session.history,
            )
        next_state = self._override_next_state(session, normalized_text, next_state)

        if not next_state:
            self._log("message_no_transition", user_id=user_id, state_id=session.state_id, text=text)
            return

        self._log(
            "message_transition",
            user_id=user_id,
            from_state=session.state_id,
            text=text,
            to_state=next_state,
        )

        # Only use editing for navigation (Назад)
        edit_chat = None
        edit_msg = None
        if normalized_text == "Назад":
            edit_chat = session.runtime_message_chat_id
            edit_msg = session.runtime_message_id

        self._commit_transition(session, action_text=normalized_text, next_state=next_state)
        session.awaiting_payment_proof = False
        await self._send_state_by_id(
            msg, next_state, session=session,
            edit_chat_id=edit_chat, edit_message_id=edit_msg,
        )
        await self._send_system_chain(msg, session)

    async def _handle_payment_proof(self, msg: Message, session: UserSession) -> None:
        photos = list(msg.photo or [])
        if not photos:
            await msg.answer(PAYMENT_PROOF_NEED_PHOTO)
            return

        user = msg.from_user
        if user is None:
            return

        photo_file_id = photos[-1].file_id
        order = self._create_paid_order(user_id=int(user.id), username=(user.username or ""), session=session)
        order_id = order["order_id"]

        caption = self._build_admin_caption(
            order_id=order_id,
            user_id=int(user.id),
            username=(user.username or ""),
            order_context=session.payment_context,
        )

        forwarded = await self._forward_payment_to_admins(
            msg=msg,
            photo_file_id=photo_file_id,
            caption=caption,
            order_id=order_id,
        )

        self._append_payment_proof(
            user_id=int(user.id),
            username=(user.username or ""),
            order_id=order_id,
            order_context=session.payment_context,
            photo_file_id=photo_file_id,
            forwarded_to_admins=forwarded,
        )

        session.awaiting_payment_proof = False
        session.payment_context = ""

        session.state_id = self.catalog.start_state_id
        session.history.append(self.catalog.start_state_id)
        await self._send_state_by_id(msg, self.catalog.start_state_id, session=session)

        operator_url = str(self.app_context.settings.link("operator") or "").strip()
        operator_markup = None
        if operator_url:
            operator_markup = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Поддержка", url=operator_url)]]
            )

        if forwarded:
            await msg.answer(PAYMENT_PROOF_SENT, reply_markup=operator_markup)
        else:
            await msg.answer(PAYMENT_PROOF_STORED, reply_markup=operator_markup)
        if operator_markup is not None:
            await msg.answer(PAYMENT_OPERATOR_TEXT, reply_markup=operator_markup)

    async def _forward_payment_to_admins(
        self,
        *,
        msg: Message,
        photo_file_id: str,
        caption: str,
        order_id: str,
    ) -> bool:
        bot = msg.bot
        if bot is None:
            return False

        forwarded = False
        for admin_id in self.app_context.admin_ids:
            try:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=photo_file_id,
                    caption=caption,
                    parse_mode=None,
                    reply_markup=kb_admin_order_confirm(order_id),
                )
                forwarded = True
            except Exception:
                continue
        return forwarded

    def _create_pending_order(self, *, msg: Message, session: UserSession) -> str:
        user = msg.from_user
        details = self._order_details_from_quote(session)
        if details is None or user is None:
            return ""
        order = self.app_context.orders.create_order(
            user_id=int(user.id),
            username=(user.username or ""),
            wallet=details["wallet"],
            coin_symbol=details["coin_symbol"],
            coin_amount=details["coin_amount"],
            amount_rub=details["amount_rub"],
            payment_method=details["payment_method"],
            bank=details["bank"],
        )
        return str(order["order_id"])

    def _create_paid_order(self, *, user_id: int, username: str, session: UserSession) -> Any:
        if session.current_order_id:
            existing = self.app_context.orders.get_order(session.current_order_id)
            if existing is not None:
                self.app_context.orders.mark_paid(session.current_order_id)
                return self.app_context.orders.get_order(session.current_order_id) or existing

        details = self._order_details_from_quote(session) or self._extract_order_details(session.payment_context)
        payment_method = str(details.get("payment_method") or self._selected_payment_method(session) or self._default_payment_method())
        bank = str(details.get("bank") or self._effective_bank_for_session(session, session.state_id))
        order = self.app_context.orders.create_order(
            user_id=user_id,
            username=username,
            wallet=str(details["wallet"]),
            coin_symbol=str(details["coin_symbol"]),
            coin_amount=float(details["coin_amount"]),
            amount_rub=float(details["amount_rub"]),
            payment_method=payment_method,
            bank=bank,
        )
        self.app_context.orders.mark_paid(order["order_id"])
        return order

    def _order_details_from_quote(self, session: UserSession) -> dict[str, Any] | None:
        quote = session.quote
        if quote is None:
            return None
        return {
            "wallet": quote.user_destination or quote.city or "(не указан)",
            "coin_symbol": quote.receive_symbol if quote.receive_symbol != "RUB" else quote.send_symbol,
            "coin_amount": quote.receive_amount if quote.receive_symbol != "RUB" else quote.send_amount,
            "amount_rub": quote.receive_amount if quote.receive_symbol == "RUB" else 0.0,
            "payment_method": quote.payment_method or self._selected_payment_method(session) or self._default_payment_method(),
            "bank": self._effective_bank_for_session(session, session.state_id) if quote.receive_symbol == "RUB" else "",
        }

    def _extract_order_details(self, text: str) -> dict[str, Any]:
        amount_rub = 0.0
        coin_amount = 0.0
        coin_symbol = "BTC"
        wallet = "(не указан)"

        rub_matches = RUB_AMOUNT_RE.findall(text or "")
        if rub_matches:
            parsed_rub = _parse_decimal(rub_matches[-1])
            if parsed_rub is not None:
                amount_rub = parsed_rub

        coin_matches = COIN_AMOUNT_RE.findall(text or "")
        if coin_matches:
            coin_amount_raw, coin_symbol_raw = coin_matches[-1]
            parsed_coin = _parse_decimal(coin_amount_raw)
            if parsed_coin is not None:
                coin_amount = parsed_coin
            coin_symbol = coin_symbol_raw.upper()

        wallet_match = WALLET_RE.search(text or "")
        if wallet_match:
            wallet_value = wallet_match.group(1).strip()
            if wallet_value:
                wallet = wallet_value

        return {
            "amount_rub": amount_rub,
            "coin_amount": coin_amount,
            "coin_symbol": coin_symbol,
            "wallet": wallet,
        }

    def _ensure_payment_proofs_file(self) -> None:
        self.payment_proofs_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.payment_proofs_path.exists():
            self.payment_proofs_path.write_text("[]\n", encoding="utf-8")

    def _append_payment_proof(
        self,
        *,
        user_id: int,
        username: str,
        order_id: str,
        order_context: str,
        photo_file_id: str,
        forwarded_to_admins: bool,
    ) -> None:
        try:
            payload = json.loads(self.payment_proofs_path.read_text(encoding="utf-8"))
        except Exception:
            payload = []

        if not isinstance(payload, list):
            payload = []

        payload.append(
            {
                "user_id": int(user_id),
                "username": username,
                "order_id": order_id,
                "order_context": order_context,
                "photo_file_id": photo_file_id,
                "forwarded_to_admins": bool(forwarded_to_admins),
            }
        )

        self.payment_proofs_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    async def _send_state_by_id(
        self,
        msg: Message,
        state_id: str,
        *,
        session: UserSession | None,
        edit_chat_id: int | None = None,
        edit_message_id: int | None = None,
    ) -> None:
        base_state = self.catalog.states.get(state_id)
        if not base_state:
            self._log("state_missing", state_id=state_id)
            return

        state = await self._materialize_state(state_id, session=session)

        self._log(
            "send_state",
            state_id=state_id,
            preview=self._state_preview(state_id),
            has_media=bool(base_state.get("media")),
            buttons=sum(len(r) for r in (base_state.get("button_rows") or [])),
        )

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
            # Update tracking to keep the same message id
            if session is not None:
                session.runtime_message_chat_id = edit_chat_id
                session.runtime_message_id = edit_message_id
                session.runtime_message_state_id = state_id
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
            if session is not None:
                await self._replace_runtime_message(
                    msg=msg,
                    session=session,
                    sent_message=sent_message,
                    state_id=state_id,
                )

    async def _remove_reply_keyboard(self, msg: Message) -> None:
        try:
            sent = await msg.answer(KEYBOARD_REMOVE_SENTINEL, reply_markup=ReplyKeyboardRemove())
            delete = getattr(sent, "delete", None)
            if callable(delete):
                try:
                    await delete()
                    return
                except Exception as e:
                    print(f'Exception caught: {e}')

            bot = getattr(msg, "bot", None) or getattr(sent, "bot", None)
            sent_chat_id = getattr(getattr(sent, "chat", None), "id", None) or getattr(getattr(msg, "chat", None), "id", None)
            sent_message_id = getattr(sent, "message_id", None)
            if bot is not None and isinstance(sent_chat_id, int) and isinstance(sent_message_id, int):
                await bot.delete_message(chat_id=sent_chat_id, message_id=sent_message_id)
        except Exception:
            return

    async def _replace_runtime_message(
        self,
        *,
        msg: Message,
        session: UserSession,
        sent_message: Message | None,
        state_id: str,
    ) -> None:
        if sent_message is None:
            return

        current_state = self.catalog.states.get(state_id) or {}
        previous_state_id = str(session.runtime_message_state_id or "")
        previous_state = self.catalog.states.get(previous_state_id) or {}
        previous_chat_id = session.runtime_message_chat_id
        previous_message_id = session.runtime_message_id

        should_delete_previous = (
            isinstance(previous_chat_id, int)
            and isinstance(previous_message_id, int)
            and previous_message_id != getattr(sent_message, "message_id", None)
            and previous_state_id
            and not self._state_is_sticky(session, previous_state_id, previous_state)
            and not self._state_is_sticky(session, state_id, current_state)
        )

        if should_delete_previous:
            bot = getattr(msg, "bot", None) or getattr(sent_message, "bot", None)
            if bot is not None:
                try:
                    await bot.delete_message(chat_id=previous_chat_id, message_id=previous_message_id)
                except Exception as e:
                    print(f'Exception caught: {e}')

        sent_chat = getattr(getattr(sent_message, "chat", None), "id", None)
        sent_message_id = getattr(sent_message, "message_id", None)
        if isinstance(sent_chat, int):
            session.runtime_message_chat_id = sent_chat
        if isinstance(sent_message_id, int):
            session.runtime_message_id = sent_message_id
        session.runtime_message_state_id = state_id

    async def _send_system_chain(self, msg: Message, session: UserSession, max_hops: int = 4) -> None:
        seen: set[str] = {session.state_id}
        current = session.state_id
        hops = 0

        while hops < max_hops:
            if self.catalog.state_has_buttons(current):
                self._log("system_chain_stop_buttons", state_id=current)
                break
            next_state = self.catalog.resolve_system_next(current)
            if not next_state or next_state in seen:
                self._log("system_chain_stop_no_next", state_id=current, next_state=next_state)
                break
            seen.add(next_state)
            self._log("system_chain_next", from_state=current, to_state=next_state)
            session.state_id = next_state
            session.history.append(next_state)
            await self._send_state_by_id(msg, next_state, session=session)
            current = next_state
            hops += 1

    async def _materialize_state(self, state_id: str, *, session: UserSession | None) -> dict[str, Any]:
        base_state = self.catalog.states.get(state_id)
        if not base_state:
            return {}
        overrides = RuntimeOverrides(
            operator_url=self.app_context.settings.link("operator"),
            payment_requisites=self._effective_requisites_for_state(session, state_id),
            link_overrides=self.app_context.settings.all_links(),
            sell_wallet_overrides=self.app_context.settings.all_sell_wallets(),
            commission_percent=self.app_context.settings.commission_percent,
        )
        live_rates_rub = await self._get_live_rates_rub()
        materialized = apply_state_overrides(
            state=base_state,
            overrides=overrides,
            operator_url_aliases=self.catalog.operator_url_aliases,
            operator_handle_aliases=self.catalog.operator_handle_aliases,
            detected_requisites=self.catalog.detected_requisites,
            link_url_aliases=self.catalog.link_url_aliases,
            sell_wallet_aliases=self.catalog.sell_wallet_aliases,
            live_rates_rub=live_rates_rub,
        )
        self._apply_payment_method_button_overrides(materialized, state_id)
        self._apply_amount_choice_overrides(materialized, session=session)
        self._replace_selected_payment_method_in_text(
            materialized,
            selected_method=self._selected_payment_method(session),
        )
        if session is not None and session.quote is None:
            await self._ensure_quote(session)
        if session is not None:
            await self._apply_quote_state(materialized, session=session)
            if self._state_is_payment_qr_template(materialized):
                qr_file = self._ensure_payment_qr(session.quote)
                if qr_file is not None and qr_file.exists():
                    materialized["media"] = str(qr_file)
        if state_id == self.catalog.about_state_id:
            _inject_home_button(materialized)
        return materialized

    def _best_context_text(self, state: dict[str, Any]) -> str:
        for field in ("text", "text_html", "text_markdown"):
            value = str(state.get(field) or "").strip()
            if value:
                return value
        return ""

    async def _state_text(self, state_id: str, *, session: UserSession | None) -> str:
        state = await self._materialize_state(state_id, session=session)
        return self._best_context_text(state)

    def _build_admin_caption(
        self,
        *,
        order_id: str,
        user_id: int,
        username: str,
        order_context: str,
    ) -> str:
        lines = [
            "Новая оплата от пользователя",
            f"order_id: {order_id}",
            f"user_id: {user_id}",
            f"username: {safe_username(username)}",
        ]
        context = (order_context or "").strip()
        if context:
            lines.append("")
            lines.append("Контекст заявки:")
            lines.append(context[:1200])
        return "\n".join(lines)

    async def _get_live_rates_rub(self) -> dict[str, float]:
        rates = await self.app_context.rates.get_rates()
        usdt_rub = float(rates.get("usdt", 0.0))
        return {
            "BTC": float(rates.get("btc", 0.0)),
            "LTC": float(rates.get("ltc", 0.0)),
            "XMR": float(rates.get("xmr", 0.0)),
            "USDT": usdt_rub,
            "USDTTRC": usdt_rub,
            "USDTBEP": usdt_rub,
        }

    def _effective_requisites_for_state(self, session: UserSession | None, state_id: str) -> str:
        settings = self.app_context.settings
        if settings.requisites_mode == "single":
            return settings.requisites_value

        selected_method = self._selected_payment_method(session)
        if selected_method:
            _, value = settings.method_requisites(selected_method)
            if value.strip():
                return value

        state = self.catalog.states.get(state_id) or {}
        text_blob = "\n".join(
            [
                str(state.get("text") or ""),
                str(state.get("text_html") or ""),
                str(state.get("text_markdown") or ""),
            ]
        ).lower()
        matches: list[str] = []
        for method in settings.payment_methods():
            if method.lower() in text_blob:
                matches.append(method)
        if len(matches) == 1:
            _, value = settings.method_requisites(matches[0])
            if value.strip():
                return value

        return settings.requisites_value

    def _effective_bank_for_session(self, session: UserSession | None, state_id: str) -> str:
        settings = self.app_context.settings
        if settings.requisites_mode == "single":
            return settings.requisites_bank

        selected_method = self._selected_payment_method(session)
        if selected_method:
            bank, _ = settings.method_requisites(selected_method)
            if bank.strip():
                return bank

        state = self.catalog.states.get(state_id) or {}
        text_blob = "\n".join(
            [
                str(state.get("text") or ""),
                str(state.get("text_html") or ""),
                str(state.get("text_markdown") or ""),
            ]
        ).lower()
        matches: list[str] = []
        for method in settings.payment_methods():
            if method.lower() in text_blob:
                matches.append(method)

        if len(matches) == 1:
            bank, _ = settings.method_requisites(matches[0])
            if bank.strip():
                return bank

        return settings.requisites_bank

    def _match_payment_method(self, action_text: str, *, state_id: str | None = None) -> str:
        action = (action_text or "").strip().lower()
        if not action:
            return ""
        for method in self.app_context.settings.payment_methods():
            if method.lower() == action:
                return method
        if state_id:
            mapping = self._payment_method_mapping_for_state(state_id)
            for original_action, method in mapping.items():
                if original_action.lower() == action:
                    return method
        return ""

    def _default_payment_method(self) -> str:
        methods = self.app_context.settings.payment_methods()
        if methods:
            return methods[0]
        return "Перевод на карту"


def outgoing_text_from_state(catalog: FlowCatalog, state_id: str) -> str:
    state = catalog.states[state_id]
    return str(state.get("text") or "")


def _parse_decimal(raw: str) -> float | None:
    cleaned = (raw or "").replace("\u00a0", " ").replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned or cleaned.count(".") > 1:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_tg_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    host = (parsed.netloc or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    return host in {"t.me", "telegram.me"}


def _tg_handle(url: str) -> str:
    if not _is_tg_url(url):
        return ""
    parsed = urlparse((url or "").strip())
    path = (parsed.path or "").strip("/")
    if not path:
        return ""
    return path.split("/")[0]


def _infer_links_from_captured_urls(captured_urls: list[str]) -> dict[str, str]:
    ordered_urls: list[str] = []
    seen: set[str] = set()
    for raw in captured_urls:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered_urls.append(value)

    tg_urls = [url for url in ordered_urls if _is_tg_url(url)]
    invite_urls = [url for url in tg_urls if _tg_handle(url).startswith("+")]
    support_urls = [url for url in tg_urls if "support" in url.lower()]
    bot_urls = [
        url
        for url in tg_urls
        if "bot" in _tg_handle(url).lower() and "?start=" not in url.lower()
    ]
    forum_urls = [url for url in ordered_urls if not _is_tg_url(url)]

    inferred: dict[str, str] = {}
    if invite_urls:
        inferred["faq"] = invite_urls[0]
    if len(invite_urls) >= 2:
        inferred["channel"] = invite_urls[1]
    elif invite_urls:
        inferred["channel"] = invite_urls[0]
    if len(invite_urls) >= 3:
        inferred["chat"] = invite_urls[2]
    elif invite_urls:
        inferred["chat"] = invite_urls[0]

    if len(invite_urls) >= 3:
        inferred["reviews"] = invite_urls[2]
    elif forum_urls:
        inferred["reviews"] = forum_urls[0]
    elif invite_urls:
        inferred["reviews"] = invite_urls[0]

    if forum_urls:
        inferred["review_form"] = forum_urls[0]

    if bot_urls:
        inferred["manager"] = bot_urls[0]
    elif support_urls:
        inferred["manager"] = support_urls[0]

    if support_urls:
        inferred["operator"] = support_urls[0]

    if len(forum_urls) >= 2:
        inferred["terms"] = forum_urls[1]
    elif forum_urls:
        inferred["terms"] = forum_urls[0]

    return inferred


def _build_env_links(
    env: dict[str, Any],
    default_operator_url: str,
    *,
    captured_link_aliases: dict[str, tuple[str, ...]] | None = None,
    captured_urls: list[str] | None = None,
) -> dict[str, str]:
    links = dict(DEFAULT_LINKS)
    legacy_values = {str(value).strip() for value in DEFAULT_LINKS.values() if str(value).strip()}

    aliases = captured_link_aliases or {}
    for link_key in DEFAULT_LINKS:
        alias_values = aliases.get(link_key) or ()
        first_alias = ""
        for candidate in alias_values:
            value = str(candidate or "").strip()
            if value:
                first_alias = value
                break
        if first_alias:
            links[link_key] = first_alias

    normalized_operator = default_operator_url.strip()
    if normalized_operator:
        current_operator = str(links.get("operator") or "").strip()
        if not current_operator or current_operator in legacy_values:
            links["operator"] = normalized_operator

    inferred = _infer_links_from_captured_urls(captured_urls or [])
    for link_key, inferred_value in inferred.items():
        if link_key not in links:
            continue
        current_value = str(links.get(link_key) or "").strip()
        if not current_value or current_value in legacy_values:
            links[link_key] = inferred_value

    for link_key in DEFAULT_LINKS:
        env_key = f"{link_key.upper()}_LINK"
        value = str(env.get(env_key) or "").strip()
        if value:
            links[link_key] = value
    return links


def should_handle_runtime_message(message: Message, raw_state: str | None = None) -> bool:
    if isinstance(raw_state, str) and raw_state.startswith("AdminState:"):
        return False
    text = (message.text or "").strip()
    return not text.startswith("/")


async def amain() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    env_path = project_dir / ".env"
    load_dotenv(env_path, override=True)

    bot_token = (os.getenv("BOT_TOKEN") or "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is empty")

    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )

    env = dotenv_values(env_path)
    admin_ids = parse_admin_ids(str(env.get("ADMIN_IDS") or ""))
    default_commission = parse_non_negative_amount(str(env.get("DEFAULT_COMMISSION_PERCENT") or ""))
    if default_commission is None or default_commission < 0 or default_commission > 50:
        default_commission = 5.0

    settings_store = SettingsStore(
        path=project_dir / "data" / "admin" / "settings.json",
        default_commission=default_commission,
        env_links=_build_env_links(
            env,
            catalog.default_operator_url,
            captured_link_aliases=catalog.link_url_aliases,
            captured_urls=catalog.links,
        ),
    )
    users_store = UsersStore(project_dir / "data" / "admin" / "users.json")
    orders_store = OrdersStore(project_dir / "data" / "admin" / "orders.json")

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        rate_service = RateService(ttl_seconds=30, client=client)

        app_context = AppContext(
            settings=settings_store,
            users=users_store,
            orders=orders_store,
            rates=rate_service,
            admin_ids=admin_ids,
            env_path=env_path,
        )

        runtime = FlowRuntime(
            project_dir=project_dir,
            catalog=catalog,
            app_context=app_context,
        )

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(build_admin_router(app_context))

        @dp.message(CommandStart())
        async def _start(message: Message) -> None:
            await runtime.start(message)

        @dp.callback_query(F.data.startswith("captcha:"))
        async def _captcha_callback(cb: CallbackQuery) -> None:
            await runtime.on_callback(cb)

        @dp.callback_query(F.data.startswith("a:"))
        async def _callback(cb: CallbackQuery) -> None:
            await runtime.on_callback(cb)

        @dp.message(StateFilter(None), should_handle_runtime_message)
        async def _message(message: Message) -> None:
            await runtime.on_message(message)

        bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        await dp.start_polling(bot)


def run() -> None:
    asyncio.run(amain())