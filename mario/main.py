from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramNetworkError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.adminkit.constants import DEFAULT_LINKS
from app.adminkit.context import AppContext
from app.adminkit.handlers.admin import build_admin_router
from app.adminkit.rates import RateService
from app.adminkit.storage import SettingsStore
from app.config import Settings, load_settings
from app.flow_compiler import ensure_compiled
from app.live_quote import (
    COIN_LABELS,
    build_live_quote,
    fmt_coin,
    fmt_rub,
    parse_amount,
)
from app.models import QuoteRecord
from app.order_engine import OrderEngine
from app.renderer import StateRenderer
from app.replay_calc import ReplayCalculator
from app.session_store import SessionStore
from app.transition_engine import TransitionEngine


def _action_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def _norm_coin(value: str | None) -> str:
    t = (value or "").strip().upper()
    if "USDT" in t:
        return "USDT"
    if "TRC20" in t or "TRC-20" in t or t in {"TRC", "TRC_20"}:
        return "USDT"
    if "BITCOIN" in t or t == "BTC":
        return "BTC"
    if "LITECOIN" in t or t == "LTC":
        return "LTC"
    if "MONERO" in t or t == "XMR":
        return "XMR"
    if "TRON" in t or t == "TRX":
        return "TRX"
    if t in {"ETH", "SOL"}:
        return t
    return t


def _build_legacy_link_aliases() -> dict[str, tuple[str, ...]]:
    return {
        "reviews": (os.getenv("LEGACY_LINK_REVIEWS", "https://t.me/MarioBTC_otzyvi"),),
        "chat": (os.getenv("LEGACY_LINK_CHAT", "https://t.me/MarioBTCgroupe"),),
        "channel": (os.getenv("LEGACY_LINK_CHANNEL", "https://t.me/Mario_BTC_Channel"),),
        "operator": (os.getenv("LEGACY_LINK_OPERATOR", "https://t.me/Mario_BTC_Operator"),),
        "terms": (os.getenv("LEGACY_LINK_TERMS", "https://telegra.ph/Pravila-ispolzovaniya-servisa-httpstmeMarioBTCbot-i-ego-politika-01-06"),),
    }


_LEGACY_LINK_ALIASES: dict[str, tuple[str, ...]] = _build_legacy_link_aliases()


def _build_legacy_operator_mentions() -> tuple[str, ...]:
    mentions = os.getenv("LEGACY_OPERATOR_MENTION", "@BTC24MONEYnoch").strip()
    if not mentions:
        return ()
    return tuple(m.strip() for m in mentions.split(",") if m.strip())


_LEGACY_OPERATOR_MENTIONS: tuple[str, ...] = _build_legacy_operator_mentions()

_TELEGRAM_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,64}$")
_OPERATOR_CONTACT_IN_CONTEXT_RE = re.compile(
    r"(?P<prefix>оператор[^\n\r@]{0,80}\s*)(?P<contact>@[A-Za-z0-9_]{3,64}|https?://\S+|t\.me/\S+)",
    flags=re.IGNORECASE,
)


def _normalize_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith("https://"):
        raw = raw[8:]
    elif lowered.startswith("http://"):
        raw = raw[7:]
    return raw.rstrip("/").lower()


def _build_url_alias_to_key() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for key, url in DEFAULT_LINKS.items():
        normalized = _normalize_url(url)
        if normalized:
            aliases[normalized] = key
    for key, values in _LEGACY_LINK_ALIASES.items():
        for url in values:
            normalized = _normalize_url(url)
            if normalized:
                aliases[normalized] = key
    return aliases


_URL_ALIAS_TO_KEY = _build_url_alias_to_key()


def _build_unique_default_text_aliases() -> dict[str, tuple[str, ...]]:
    counts: dict[str, int] = {}
    for url in DEFAULT_LINKS.values():
        normalized = _normalize_url(url)
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1

    result: dict[str, tuple[str, ...]] = {}
    for key, url in DEFAULT_LINKS.items():
        normalized = _normalize_url(url)
        if not normalized or counts.get(normalized, 0) != 1:
            continue
        result[key] = (url,)
    return result


_UNIQUE_DEFAULT_TEXT_ALIASES = _build_unique_default_text_aliases()


def _telegram_mention_from_link(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    candidate = raw
    if candidate.startswith("@"):
        candidate = candidate[1:]
    else:
        lowered = candidate.lower()
        if lowered.startswith("https://"):
            candidate = candidate[8:]
        elif lowered.startswith("http://"):
            candidate = candidate[7:]

        lowered = candidate.lower()
        if lowered.startswith("t.me/"):
            candidate = candidate[5:]
        elif lowered.startswith("telegram.me/"):
            candidate = candidate[11:]
        else:
            return None

        candidate = candidate.split("?", 1)[0].split("#", 1)[0].strip("/")
        if "/" in candidate:
            candidate = candidate.split("/", 1)[0]

    if not _TELEGRAM_USERNAME_RE.fullmatch(candidate):
        return None
    return f"@{candidate}"


def _operator_contact_from_link(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    mention = _telegram_mention_from_link(raw)
    if mention:
        return mention

    lowered = raw.lower()
    if lowered.startswith("t.me/"):
        return f"https://{raw}"
    return raw


def _build_operator_mention_aliases() -> tuple[str, ...]:
    values = set(_LEGACY_OPERATOR_MENTIONS)
    operator_default = DEFAULT_LINKS.get("operator", "")
    if operator_default:
        mention = _telegram_mention_from_link(operator_default)
        if mention:
            values.add(mention)

    for url in _LEGACY_LINK_ALIASES.get("operator", ()):
        mention = _telegram_mention_from_link(url)
        if mention:
            values.add(mention)

    return tuple(sorted(values, key=lambda item: item.lower()))


_OPERATOR_MENTION_ALIASES = _build_operator_mention_aliases()


def _link_key_by_button(text: str, url: str) -> str | None:
    lowered = (text or "").strip().lower()
    if "faq" in lowered:
        return "faq"
    if "услов" in lowered or "правил" in lowered:
        return "terms"
    if "оператор" in lowered:
        return "operator"
    if "менедж" in lowered:
        return "manager"
    if "отзыв" in lowered and ("форм" in lowered or "остав" in lowered):
        return "review_form"
    if "отзыв" in lowered:
        return "reviews"
    if "канал" in lowered or "новост" in lowered:
        return "channel"
    if "чат" in lowered or "курилк" in lowered or "груп" in lowered or "group" in lowered:
        return "chat"
    normalized_url = _normalize_url(url)
    return _URL_ALIAS_TO_KEY.get(normalized_url)


def _replace_links_in_text(text: str, links: dict[str, str]) -> str:
    updated = text
    for key, replacement in links.items():
        target = replacement.strip()
        if not target:
            continue
        candidates: set[str] = set(_UNIQUE_DEFAULT_TEXT_ALIASES.get(key, ()))
        candidates.update(_LEGACY_LINK_ALIASES.get(key, ()))
        for source in candidates:
            if not source or source == target:
                continue
            updated = updated.replace(source, target)

    operator_target = _operator_contact_from_link(links.get("operator", ""))
    if operator_target:
        for source in _OPERATOR_MENTION_ALIASES:
            if source.lower() == operator_target.lower():
                continue
            updated = re.sub(re.escape(source), operator_target, updated, flags=re.IGNORECASE)
        updated = _OPERATOR_CONTACT_IN_CONTEXT_RE.sub(
            lambda match: f"{match.group('prefix')}{operator_target}",
            updated,
        )
    return updated


def apply_admin_links_to_states(states: dict[str, dict[str, Any]], links: dict[str, str]) -> dict[str, int]:
    normalized_links = {
        key: value.strip()
        for key, value in links.items()
        if isinstance(key, str) and isinstance(value, str) and value.strip()
    }
    if not normalized_links:
        return {"button_urls_updated": 0, "text_urls_updated": 0}

    button_updates = 0
    text_updates = 0
    for state in states.values():
        rows = state.get("button_rows")
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, list):
                    continue
                for btn in row:
                    if not isinstance(btn, dict):
                        continue
                    if str(btn.get("type") or "") != "KeyboardButtonUrl":
                        continue
                    key = _link_key_by_button(
                        text=str(btn.get("text") or ""),
                        url=str(btn.get("url") or ""),
                    )
                    if key is None:
                        continue
                    target = normalized_links.get(key)
                    if not target:
                        continue
                    if btn.get("url") == target:
                        continue
                    btn["url"] = target
                    button_updates += 1

        for field in ("text", "text_html", "text_markdown"):
            raw_value = state.get(field)
            if not isinstance(raw_value, str) or not raw_value:
                continue
            updated_value = _replace_links_in_text(raw_value, normalized_links)
            if updated_value == raw_value:
                continue
            state[field] = updated_value
            text_updates += 1

    return {
        "button_urls_updated": button_updates,
        "text_urls_updated": text_updates,
    }


def _collect_reload_snapshot(project_dir: Path) -> tuple[tuple[str, int], ...]:
    ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
    entries: list[tuple[str, int]] = []
    for path in sorted(project_dir.rglob("*.py")):
        rel_parts = path.relative_to(project_dir).parts
        if any(part in ignored_dirs for part in rel_parts):
            continue
        try:
            mtime_ns = path.stat().st_mtime_ns
        except FileNotFoundError:
            mtime_ns = -1
        entries.append((str(path.relative_to(project_dir)), mtime_ns))

    env_path = project_dir / ".env"
    try:
        env_mtime_ns = env_path.stat().st_mtime_ns
    except FileNotFoundError:
        env_mtime_ns = -1
    entries.append((".env", env_mtime_ns))
    return tuple(entries)


async def _hot_reload_watchdog(project_dir: Path, interval_seconds: float) -> None:
    interval = max(0.25, float(interval_seconds))
    snapshot = _collect_reload_snapshot(project_dir)
    while True:
        await asyncio.sleep(interval)
        current = _collect_reload_snapshot(project_dir)
        if current == snapshot:
            continue
        logging.info("Hot reload: .py/.env change detected, restarting process.")
        os.execv(sys.executable, [sys.executable, *sys.argv])


class CloneRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        ensure_compiled(
            raw_dir=settings.raw_dir,
            media_dir=settings.media_dir,
            compiled_dir=settings.compiled_dir,
        )
        self.states_payload = json.loads(
            (settings.compiled_dir / "compiled_states.json").read_text(encoding="utf-8")
        )
        self.transitions_payload = json.loads(
            (settings.compiled_dir / "compiled_transitions.json").read_text(encoding="utf-8")
        )
        self.replay_payload = json.loads(
            (settings.compiled_dir / "compiled_replay_tables.json").read_text(encoding="utf-8")
        )

        self.states: dict[str, dict[str, Any]] = self.states_payload.get("states", {})
        self.transition_engine = TransitionEngine(self.transitions_payload, self.states_payload)
        self.replay_calc = ReplayCalculator(self.replay_payload)
        self.renderer = StateRenderer(settings.media_dir, settings.media_file_id_cache_path)
        self.sessions = SessionStore(settings.sessions_store_path, settings.session_history_limit)
        self.orders = OrderEngine(settings.orders_store_path, settings.order_ttl_seconds)
        self.rate_service = RateService(ttl_seconds=settings.rate_cache_ttl_seconds)
        self.admin_settings = SettingsStore(
            path=settings.admin_settings_path,
            default_commission=settings.default_commission_percent,
            env_links=DEFAULT_LINKS,
        )
        self.admin_ctx = AppContext(
            settings=self.admin_settings,
            rates=self.rate_service,
            admin_ids=set(settings.admin_ids),
            env_path=settings.project_dir / ".env",
            on_links_updated=self.refresh_runtime_links,
        )
        self.refresh_runtime_links()

        self._action_to_callback: dict[str, str] = {}
        self._callback_to_action: dict[str, str] = {}
        self._bootstrap_actions()

        self.entry_state_id = self._detect_entry_state()
        self.intro_state_id = self._detect_intro_state()
        self.search_wait_state_id = self._detect_search_wait_state()
        self.receipt_prompt_state_id = self._detect_receipt_prompt_state()
        self._search_tasks: dict[int, asyncio.Task[None]] = {}
        self.payment_methods: set[str] = set()
        self._sync_runtime_payment_methods()

    def refresh_runtime_links(self) -> dict[str, int]:
        return apply_admin_links_to_states(self.states, self.admin_settings.all_links())

    def ensure_session_state(self, session: Any) -> bool:
        repaired = False
        history = [sid for sid in (session.history or []) if sid in self.states]
        if session.current_state_id not in self.states:
            session.current_state_id = history[-1] if history else self.entry_state_id
            repaired = True
        if not history:
            history = [session.current_state_id]
            repaired = True
        if history[-1] != session.current_state_id:
            history.append(session.current_state_id)
            repaired = True
        limit = max(1, int(self.settings.session_history_limit))
        if len(history) > limit:
            history = history[-limit:]
            repaired = True
        if history != session.history:
            session.history = history
            repaired = True
        return repaired

    def _bootstrap_actions(self) -> None:
        for state in self.states.values():
            rows = state.get("button_rows") or []
            for row in rows:
                if not isinstance(row, list):
                    continue
                for btn in row:
                    if not isinstance(btn, dict):
                        continue
                    text = str(btn.get("text") or "").strip()
                    if not text:
                        continue
                    if str(btn.get("type") or "") == "KeyboardButtonUrl":
                        continue
                    self._register_action(text)

    def _register_action(self, action_text: str) -> str:
        if action_text in self._action_to_callback:
            return self._action_to_callback[action_text]
        key = _action_hash(action_text)
        callback = f"a:{key}"
        idx = 1
        while callback in self._callback_to_action and self._callback_to_action[callback] != action_text:
            idx += 1
            callback = f"a:{key[:8]}{idx:02d}"
        self._action_to_callback[action_text] = callback
        self._callback_to_action[callback] = action_text
        return callback

    def callback_for_action(self, action_text: str) -> str:
        return self._register_action(action_text)

    def action_from_callback(self, callback_data: str | None) -> str | None:
        if not callback_data:
            return None
        return self._callback_to_action.get(callback_data)

    def _detect_entry_state(self) -> str:
        candidates: list[tuple[int, str]] = []
        for sid, state in self.states.items():
            if state.get("kind") != "main_menu":
                continue
            btns = state.get("interactive_actions") or []
            candidates.append((len(btns), sid))
        if candidates:
            candidates.sort(reverse=True)
            return candidates[0][1]
        # fallback
        first_sid = next(iter(self.states.keys()))
        return first_sid

    def _detect_intro_state(self) -> str | None:
        for sid, state in self.states.items():
            if state.get("kind") == "intro_banner":
                return sid
        return None

    def _detect_search_wait_state(self) -> str | None:
        for sid, state in self.states.items():
            if str(state.get("kind") or "") != "order_searching":
                continue
            text = str(state.get("text") or "").lower()
            if "ожидание до 5 минут" in text or "поиск реквизита" in text:
                return sid
        for sid, state in self.states.items():
            if str(state.get("kind") or "") == "order_searching":
                return sid
        return None

    def _detect_receipt_prompt_state(self) -> str | None:
        candidates: list[tuple[int, str]] = []
        for sid, state in self.states.items():
            if str(state.get("kind") or "") != "info":
                continue
            text = str(state.get("text") or "").lower()
            score = 0
            if "чек" in text:
                score += 2
            if "скрин" in text:
                score += 2
            if "перевод" in text:
                score += 1
            if score <= 0:
                continue
            candidates.append((score, sid))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][1]

    def _configured_payment_methods(self) -> list[str]:
        methods: list[str] = []
        seen: set[str] = set()
        for raw in self.admin_settings.payment_methods():
            method = str(raw).strip()
            if not method or method == "Назад":
                continue
            if method in seen:
                continue
            seen.add(method)
            methods.append(method)
        if methods:
            return methods
        return ["📱СБП"]

    def _sync_runtime_payment_methods(self) -> None:
        methods = self._configured_payment_methods()
        self.payment_methods = set(methods)
        actions = [*methods, "Назад"]
        rows = [
            [{"text": action, "type": "KeyboardButtonCallback", "row": idx, "col": 0}]
            for idx, action in enumerate(actions)
        ]

        for state in self.states.values():
            if str(state.get("kind") or "") != "payment_method_select":
                continue
            state["interactive_actions"] = list(actions)
            state["button_rows"] = [[dict(btn) for btn in row] for row in rows]

    def history_empty_toast_text(self, user_id: int) -> str | None:
        if self.orders.list_for_user(user_id, limit=1):
            return None
        return "Вы не совершили ни одной сделки."

    def _order_status_label(self, status: str) -> str:
        labels = {
            "created": "Создана",
            "searching": "Поиск реквизитов",
            "paid": "Оплачена",
            "cancelled": "Отменена",
            "expired": "Истекла",
        }
        return labels.get(status, status)

    def history_list_text(self, user_id: int) -> str | None:
        orders = self.orders.list_for_user(user_id, limit=7)
        if not orders:
            return None
        lines = ["📚 История сделок (последние 7):"]
        for idx, order in enumerate(orders, start=1):
            coin_amount = fmt_coin(float(order.output_amount if order.operation == "buy" else order.input_amount))
            rub_amount = fmt_rub(float(order.pay_amount if order.operation == "buy" else order.output_amount))
            direction = "Покупка" if str(order.operation) == "buy" else "Продажа"
            lines.append(
                f"{idx}. {direction} {order.coin}: {coin_amount} | {rub_amount} ₽ | {self._order_status_label(order.status)}"
            )
        return "\n".join(lines)

    def _cancel_search_task(self, user_id: int) -> None:
        task = self._search_tasks.pop(user_id, None)
        if task is not None and not task.done():
            task.cancel()

    def _admin_notification_ids(self) -> set[int]:
        ids = set(self.admin_ctx.admin_ids) if self.admin_ctx.admin_ids else set(self.settings.admin_ids)
        return {admin_id for admin_id in ids if admin_id > 0}

    async def notify_admins_about_media(self, bot: Bot, msg: Message, *, media_kind: str) -> None:
        sender = msg.from_user
        if sender is None:
            return

        admin_ids = sorted(self._admin_notification_ids())

        sender_id = int(sender.id)
        username = f"@{sender.username}" if sender.username else "без username"
        sender_name = " ".join(part for part in [sender.first_name, sender.last_name] if part).strip()
        if not sender_name:
            sender_name = username if sender.username else str(sender_id)
        media_label = "фото" if media_kind == "photo" else "изображение"
        session = self.sessions.get_or_create(sender_id, self.entry_state_id)
        order_suffix = f"\nЗаявка: {session.last_order_id}" if session.last_order_id else ""
        order = self.orders.by_id(session.last_order_id) if session.last_order_id else None
        should_ack_paid_receipt = order is not None and order.status == "paid"
        notification_text = (
            f"🔔 Пользователь отправил {media_label}.\n"
            f"ID: {sender_id}\n"
            f"Имя: {sender_name}\n"
            f"Username: {username}"
            f"{order_suffix}"
        )

        answer_fn = getattr(msg, "answer", None)

        async def _ack_paid_receipt() -> None:
            if should_ack_paid_receipt and callable(answer_fn):
                await answer_fn("✅ Чек принят, ожидайте пожалуйста.", parse_mode=None)

        if not admin_ids:
            await _ack_paid_receipt()
            return

        for admin_id in admin_ids:
            try:
                await bot.send_message(chat_id=admin_id, text=notification_text, parse_mode=None)
                await bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id,
                )
            except Exception:
                logging.exception(
                    "Failed to notify admin_id=%s about media from user_id=%s",
                    admin_id,
                    sender_id,
                )
        await _ack_paid_receipt()

    def get_state(self, state_id: str) -> dict[str, Any]:
        state = self.states.get(state_id)
        if state is not None:
            return state
        return self.states[self.entry_state_id]

    async def start_flow(self, msg: Message, user_id: int) -> None:
        self._cancel_search_task(user_id)
        session = self.sessions.clear(user_id, self.entry_state_id)
        if self.intro_state_id:
            await self.renderer.send_state(
                msg,
                self.get_state(self.intro_state_id),
                action_to_callback=self.callback_for_action,
            )
        await self.renderer.send_state(
            msg,
            self.get_state(self.entry_state_id),
            action_to_callback=self.callback_for_action,
        )
        session.push_state(self.entry_state_id, self.settings.session_history_limit)
        session.pending_operation = None
        session.pending_coin = None
        session.pending_amount_raw = None
        session.pending_payment_method = None
        session.pending_wallet = None
        session.promo_applied = None
        session.last_quote_state_id = None
        session.last_quote_coin_amount = None
        session.last_quote_rub_amount = None
        session.last_quote_net_amount = None
        session.last_order_id = None
        self.sessions.save()

    def _state_coin_context(self, state_id: str) -> tuple[str | None, str | None]:
        buy_coin = self.replay_calc.coin_for_prompt_state("buy", state_id)
        if buy_coin:
            return "buy", _norm_coin(buy_coin)
        sell_coin = self.replay_calc.coin_for_prompt_state("sell", state_id)
        if sell_coin:
            return "sell", _norm_coin(sell_coin)
        return None, None

    async def _send_state(
        self,
        msg: Message,
        session: Any,
        state_id: str,
        *,
        text_override: str | None = None,
        text_override_plain: str | None = None,
    ) -> None:
        state = self.get_state(state_id)
        state_kind = str(state.get("kind") or "")
        if text_override is None and text_override_plain is None:
            dynamic_text: tuple[str, str] | None = None
            if state_kind == "quote":
                dynamic_text = self._render_quote_text(session)
            elif state_kind == "payment_method_select":
                dynamic_text = self._render_payment_method_text(session)
            elif state_kind in {"wallet_prompt", "info"}:
                dynamic_text = self._render_wallet_prompt_text(session, state_kind, state)
            elif state_kind == "promo_confirm":
                dynamic_text = self._render_promo_confirm_text(session)
            if dynamic_text:
                text_override, text_override_plain = dynamic_text
        await self.renderer.send_state(
            msg,
            state,
            action_to_callback=self.callback_for_action,
            text_override=text_override,
            text_override_plain=text_override_plain,
        )
        session.push_state(state_id, self.settings.session_history_limit)

        operation, coin = self._state_coin_context(state_id)
        if operation:
            session.pending_operation = operation
            session.pending_coin = coin

    async def _current_rates(self, *, force: bool = False) -> dict[str, float]:
        return await self.rate_service.get_rates(force=force)

    def _current_commission(self) -> float:
        return float(self.admin_settings.commission_percent)

    def _session_quote(self, session: Any) -> QuoteRecord | None:
        if (
            session.last_quote_state_id
            and session.last_quote_coin_amount is not None
            and session.last_quote_rub_amount is not None
            and session.pending_operation
            and session.pending_coin
        ):
            return QuoteRecord(
                state_id=str(session.last_quote_state_id),
                operation=str(session.pending_operation),
                coin=_norm_coin(str(session.pending_coin)),
                coin_amount=float(session.last_quote_coin_amount),
                rub_amount=float(session.last_quote_rub_amount),
                net_amount=(
                    float(session.last_quote_net_amount)
                    if session.last_quote_net_amount is not None
                    else None
                ),
            )
        return None

    def _render_payment_method_text(self, session: Any) -> tuple[str, str] | None:
        quote = self._session_quote(session)
        if quote is None:
            return None
        coin = _norm_coin(quote.coin)
        coin_label = COIN_LABELS.get(coin, coin)
        if quote.operation == "buy":
            pay_amount = self._effective_buy_pay_amount(session, quote.rub_amount)
            plain = (
                "🎮Твоя заявка\n"
                f"🕹Покупка {coin_label}: {fmt_coin(quote.coin_amount)}\n"
                f"🪙Нужно перевести: {fmt_rub(pay_amount)} ₽\n"
                "Выбери способ оплаты:"
            )
            html = (
                "🎮<strong>Твоя заявка</strong>\n"
                f"🕹<strong>Покупка {coin_label}</strong>: {fmt_coin(quote.coin_amount)}\n"
                f"🪙<strong>Нужно перевести</strong>: {fmt_rub(pay_amount)} ₽\n"
                "<strong>Выбери способ оплаты:</strong>"
            )
            return html, plain
        plain = (
            "🎮Твоя заявка\n"
            f"🕹Продажа {coin_label}: {fmt_coin(quote.coin_amount)}\n"
            f"💵К получению: {fmt_rub(quote.rub_amount)} ₽\n"
            "Выбери способ оплаты:"
        )
        html = (
            "🎮<strong>Твоя заявка</strong>\n"
            f"🕹<strong>Продажа {coin_label}</strong>: {fmt_coin(quote.coin_amount)}\n"
            f"💵<strong>К получению</strong>: {fmt_rub(quote.rub_amount)} ₽\n"
            "<strong>Выбери способ оплаты:</strong>"
        )
        return html, plain

    def _render_wallet_prompt_text(self, session: Any, next_kind: str, next_state: dict[str, Any]) -> tuple[str, str] | None:
        quote = self._session_quote(session)
        if quote is None:
            return None
        coin = _norm_coin(quote.coin)
        coin_label = COIN_LABELS.get(coin, coin)
        state_text = str(next_state.get("text") or "")
        state_text_l = state_text.lower()

        if next_kind in {"wallet_prompt", "info"} and "адрес" in state_text_l and "отправ" in state_text_l:
            if "на какой" in state_text_l or "отправь кошелек" in state_text_l:
                plain = (
                    f"⭐️На какой {coin_label}-адрес ты хочешь отправить {fmt_coin(quote.coin_amount)} {coin.lower()}.\n"
                    "📝Отправь кошелек:"
                )
            else:
                plain = (
                    f"Введите {coin_label}-адрес кошелька, куда вы хотите отправить "
                    f"{fmt_coin(quote.coin_amount)} {coin.lower()}."
                )
            html = plain
            return html, plain

        if next_kind == "info" and "введите 📲сбп реквизиты" in state_text_l:
            plain = f"Введите 📲СБП реквизиты, куда вы хотите получить {fmt_rub(quote.rub_amount)} ₽."
            html = plain
            return html, plain
        return None

    def _render_promo_confirm_text(self, session: Any) -> tuple[str, str] | None:
        quote = self._session_quote(session)
        if quote is None:
            return None
        coin = _norm_coin(quote.coin)
        coin_label = COIN_LABELS.get(coin, coin)
        promo_ratio = self._promo_ratio()
        before = quote.rub_amount
        after = before * promo_ratio
        html = (
            f"<strong>🕹Ты покупаешь {coin_label}</strong>: {fmt_coin(quote.coin_amount)}\n"
            f"<strong>Тебе нужно будет оплатить</strong>: "
            f"<del>{fmt_rub(before)}</del> {fmt_rub(after)}\n"
            "🔥 Я дарю тебе промокод: <strong>PERVAYA_SDELKA</strong>, по которому будет скидка 20% от комиссии\n\n"
            "👨‍🔧 <strong>Хочешь применить промо</strong> как скидку?"
        )
        plain = (
            f"🕹Ты покупаешь {coin_label}: {fmt_coin(quote.coin_amount)}\n"
            f"Тебе нужно будет оплатить: {fmt_rub(before)} {fmt_rub(after)}\n"
            "🔥 Я дарю тебе промокод: PERVAYA_SDELKA, по которому будет скидка 20% от комиссии\n\n"
            "👨‍🔧 Хочешь применить промо как скидку?"
        )
        return html, plain

    def _render_quote_text(self, session: Any) -> tuple[str, str] | None:
        quote = self._session_quote(session)
        if quote is None:
            return None
        coin = _norm_coin(quote.coin)
        coin_label = COIN_LABELS.get(coin, coin)
        if quote.operation == "buy":
            lines = [
                f"Сумма к получению: {fmt_coin(quote.coin_amount)} {coin_label}",
                f"Сумма к оплате: {fmt_rub(quote.rub_amount)} ₽",
            ]
            if quote.net_amount is not None:
                lines.append(f"Сумма к зачислению: {fmt_rub(quote.net_amount)} ₽")
            text = "\n".join(lines)
            return text, text
        text = (
            f"Сумма к получению: {fmt_rub(quote.rub_amount)} ₽\n"
            f"Сумма к оплате: {fmt_coin(quote.coin_amount)} {coin.lower()}"
        )
        return text, text

    def _promo_ratio(self) -> float:
        return max(0.0, 1.0 - ((self._current_commission() * 0.2) / 100.0))

    def _effective_buy_pay_amount(self, session: Any, base_rub_amount: float) -> float:
        if bool(getattr(session, "promo_applied", False)):
            return base_rub_amount * self._promo_ratio()
        return base_rub_amount

    def _ensure_runtime_order(self, user_id: int, session: Any) -> Any | None:
        if session.last_order_id:
            existing = self.orders.by_id(session.last_order_id)
            if existing is not None:
                return existing

        quote = self._session_quote(session)
        if quote is None and session.last_quote_state_id:
            for item in self.replay_calc.quotes:
                if item.state_id == session.last_quote_state_id:
                    quote = item
                    break
        if quote is None or not session.pending_wallet:
            return None

        if quote.operation == "buy":
            input_amount = self._effective_buy_pay_amount(session, quote.rub_amount)
        else:
            input_amount = quote.coin_amount
        payment_method = (
            session.pending_payment_method
            or (self.admin_settings.payment_methods()[0] if self.admin_settings.payment_methods() else "📱СБП")
        )
        order = self.orders.create_order(
            user_id=user_id,
            operation=quote.operation,
            coin=_norm_coin(quote.coin),
            input_amount=input_amount,
            quote=quote,
            payment_method=payment_method,
            wallet_or_requisites=session.pending_wallet,
        )
        session.last_order_id = order.order_id
        return order

    def _pop_back_state(self, session: Any) -> str | None:
        history = [sid for sid in session.history if sid in self.states]
        if not history:
            return None

        current_id = session.current_state_id if session.current_state_id in self.states else history[-1]
        idx = len(history) - 1
        while idx >= 0 and history[idx] != current_id:
            idx -= 1
        if idx <= 0:
            session.history = history[:1]
            return None

        target_idx = idx - 1
        while target_idx >= 0 and history[target_idx] == current_id:
            target_idx -= 1
        if target_idx < 0:
            session.history = history[:1]
            return None

        target_state = history[target_idx]
        # Truncate including current and older duplicates of target.
        # _send_state will append target state once again.
        session.history = history[:target_idx]
        return target_state

    def _render_runtime_order_text(self, order: Any) -> tuple[str, str, str | None]:
        template = self.replay_calc.order_template_for_coin(order.coin)
        if template is None:
            return "", "", None
        state_id = str(template.get("state_id") or "")
        state = self.get_state(state_id) if state_id in self.states else {}
        source_text = str(template.get("source_text") or state.get("text") or "")
        source_html = str(state.get("text_html") or source_text)
        if str(order.operation).lower() == "buy":
            _bank, merchant_requisites = self.admin_settings.method_requisites(order.payment_method)
            text_plain, text_html = self.orders.render_buy_order_text(order, merchant_requisites=merchant_requisites)
            return text_plain, text_html, state_id if state_id in self.states else None

        configured_wallet = self.admin_settings.crypto_wallet(_norm_coin(str(order.coin)))
        template_wallet = str(template.get("requisites_value") or "").strip()
        merchant_requisites = configured_wallet.strip() or template_wallet
        text_plain = self.orders.render_order_text(
            source_text,
            order,
            merchant_requisites=merchant_requisites,
            template_sold_amount_raw=template.get("sold_amount_raw"),
            template_payout_rub=template.get("payout_rub"),
            template_requisites_value=template.get("requisites_value"),
        )
        text_html = self.orders.render_order_text(
            source_html,
            order,
            merchant_requisites=merchant_requisites,
            template_sold_amount_raw=template.get("sold_amount_raw"),
            template_payout_rub=template.get("payout_rub"),
            template_requisites_value=template.get("requisites_value"),
        )
        return text_plain, text_html, state_id if state_id in self.states else None

    async def _deliver_order_after_search(self, msg: Message, user_id: int, order_id: str) -> None:
        try:
            await asyncio.sleep(max(1, int(self.settings.search_delay_seconds)))
            session = self.sessions.get_or_create(user_id, self.entry_state_id)
            if session.last_order_id != order_id:
                return
            order = self.orders.by_id(order_id)
            if order is None:
                return
            text_plain, text_html, state_id = self._render_runtime_order_text(order)
            if not state_id or (not text_plain and not text_html):
                return
            await self._send_state(
                msg,
                session,
                state_id,
                text_override=(text_html or text_plain),
                text_override_plain=(text_plain or text_html),
            )
            self.sessions.save()
        except asyncio.CancelledError:
            raise
        except Exception:
            logging.exception("Failed to deliver delayed order for user_id=%s", user_id)
        finally:
            active = self._search_tasks.get(user_id)
            if active is asyncio.current_task():
                self._search_tasks.pop(user_id, None)

    async def _auto_chain(self, msg: Message, session: Any) -> None:
        # Follow deterministic transitions to mimic immediate bot bursts:
        # explicit system:auto only.
        for _ in range(8):
            current = session.current_state_id
            current_state = self.get_state(current)
            current_kind = str(current_state.get("kind") or "")
            if current_kind in {
                "buy_amount_prompt",
                "sell_amount_prompt",
                "wallet_prompt",
                "order_searching",
                "order_found",
                "order_cancelled",
            }:
                return

            next_state, reason = self.transition_engine.resolve_next(
                current,
                action_text="",
                is_text_input=False,
                session_history=session.history,
            )
            if not next_state:
                return
            if next_state == current:
                return

            if not reason.startswith("action:system:auto"):
                return

            await self._send_state(msg, session, next_state)

    async def handle_action(self, msg: Message, user_id: int, action_text: str, is_text_input: bool) -> None:
        self.orders.expire_overdue()
        self._sync_runtime_payment_methods()
        session = self.sessions.get_or_create(user_id, self.entry_state_id)
        if self.ensure_session_state(session):
            self.sessions.save()
        current_state = self.get_state(session.current_state_id)
        current_kind = str(current_state.get("kind") or "")
        payment_confirm_actions = {"Оплатил", "Я оплатил(а)"}
        cancel_actions = {"Остановить поиск", "Отменить заявку"}
        promo_apply_actions = {"Использовать промокод"}
        promo_skip_actions = {"Не использовать промокод"}

        if action_text in self.payment_methods:
            session.pending_payment_method = action_text
        if not is_text_input and current_kind == "promo_confirm":
            if action_text in promo_apply_actions:
                session.promo_applied = True
            elif action_text in promo_skip_actions:
                session.promo_applied = False
        if not is_text_input and current_kind == "main_menu" and action_text == "🎰Бонус🎰":
            action_text = "🤑Большой розыгрыш🤑"
        if not is_text_input and current_kind == "main_menu" and action_text == "История сделок":
            history_text = self.history_list_text(user_id)
            if history_text:
                await msg.answer(history_text, parse_mode=None)
            self.sessions.save()
            return
        if action_text in payment_confirm_actions:
            self._cancel_search_task(user_id)
        if action_text in cancel_actions:
            self._cancel_search_task(user_id)
        if action_text == "Назад" and not is_text_input:
            back_state = self._pop_back_state(session) or self.entry_state_id
            await self._send_state(msg, session, back_state)
            self.sessions.save()
            return

        if action_text == "Калькулятор" and current_kind in {"buy_amount_prompt", "sell_amount_prompt"}:
            coin = _norm_coin(session.pending_coin or "")
            if not coin:
                await msg.answer("Выбери монету и отправь сумму для расчета.", parse_mode=None)
                self.sessions.save()
                return

            rate_key = {
                "BTC": "btc",
                "LTC": "ltc",
                "XMR": "xmr",
                "USDT": "usdt",
                "TRX": "trx",
                "ETH": "eth",
                "SOL": "sol",
            }.get(coin, coin.lower())
            rates = await self._current_rates()
            rate_value = float(rates.get(rate_key) or 0.0)
            coin_label = COIN_LABELS.get(coin, coin)
            if rate_value > 0:
                await msg.answer(
                    (
                        f"📈 Калькулятор {coin_label}\n"
                        f"Текущий курс CoinGecko: 1 {coin} = {fmt_rub(rate_value)} ₽\n"
                        "Отправь сумму в монете или в ₽ и я сразу пересчитаю."
                    ),
                    parse_mode=None,
                )
            else:
                await msg.answer(
                    "Не удалось получить курс CoinGecko. Отправь сумму, я посчитаю по резервному курсу.",
                    parse_mode=None,
                )
            self.sessions.save()
            return

        # Prompt-specific replay logic with live CoinGecko pricing.
        if is_text_input and current_kind in {"buy_amount_prompt", "sell_amount_prompt"}:
            parsed_input = parse_amount(action_text)
            if parsed_input is None:
                await msg.answer("Невалидное значение.", parse_mode=None)
                self.sessions.save()
                return

            operation = "buy" if current_kind == "buy_amount_prompt" else "sell"
            coin = _norm_coin(session.pending_coin or "")
            rates = await self._current_rates()
            live_quote = build_live_quote(
                self.replay_calc,
                operation=operation,
                coin=coin,
                user_input=action_text,
                rates=rates,
                commission_percent=self._current_commission(),
                input_kind_hint=("coin" if current_kind == "sell_amount_prompt" else None),
            )
            if live_quote:
                session.pending_amount_raw = action_text
                session.last_quote_state_id = live_quote.state_id
                session.last_quote_coin_amount = live_quote.coin_amount
                session.last_quote_rub_amount = live_quote.rub_amount
                session.last_quote_net_amount = live_quote.net_amount
                session.pending_operation = operation
                session.pending_coin = coin
                session.pending_wallet = None
                session.promo_applied = None
                session.last_order_id = None
                await self._send_state(
                    msg,
                    session,
                    live_quote.state_id,
                    text_override=live_quote.quote_text(),
                    text_override_plain=live_quote.quote_text(),
                )
                # Force immediate hop from quote state (observed behavior in source bot),
                # then continue generic auto-chain.
                forced_next, _forced_reason = self.transition_engine.resolve_next(
                    live_quote.state_id,
                    action_text="",
                    is_text_input=False,
                    session_history=session.history,
                )
                if (
                    forced_next
                    and forced_next != live_quote.state_id
                    and _forced_reason.startswith("action:system:auto")
                ):
                    forced_state = self.get_state(forced_next)
                    forced_kind = str(forced_state.get("kind") or "")
                    forced_text_html: str | None = None
                    forced_text_plain: str | None = None
                    if forced_kind == "promo_confirm":
                        forced_text_html = live_quote.promo_text_html()
                        forced_text_plain = live_quote.promo_text_plain()
                    elif forced_kind == "payment_method_select":
                        payment_text = self._render_payment_method_text(session)
                        if payment_text:
                            forced_text_html, forced_text_plain = payment_text
                    elif forced_kind in {"wallet_prompt", "info"}:
                        wallet_text = self._render_wallet_prompt_text(session, forced_kind, forced_state)
                        if wallet_text:
                            forced_text_html, forced_text_plain = wallet_text
                    await self._send_state(
                        msg,
                        session,
                        forced_next,
                        text_override=forced_text_html,
                        text_override_plain=forced_text_plain,
                    )
                await self._auto_chain(msg, session)
                self.sessions.save()
                return
            await msg.answer("Невалидное значение.", parse_mode=None)
            self.sessions.save()
            return

        # Persist entered wallet/requisites.
        if is_text_input and current_kind in {"wallet_prompt", "info"}:
            session.pending_wallet = action_text

        # Custom order flow: show searching state, then deliver requisites from admin settings.
        if (
            is_text_input
            and current_kind in {"wallet_prompt", "info"}
            and session.last_quote_state_id
            and not session.last_order_id
            and self.search_wait_state_id
        ):
            order = self._ensure_runtime_order(user_id, session)
            if order is not None:
                self._cancel_search_task(user_id)
                await self._send_state(msg, session, self.search_wait_state_id)
                task = asyncio.create_task(self._deliver_order_after_search(msg, user_id, order.order_id))
                self._search_tasks[user_id] = task
                self.sessions.save()
                return

        next_state_id, _reason = self.transition_engine.resolve_next(
            session.current_state_id,
            action_text=action_text,
            is_text_input=is_text_input,
            session_history=session.history,
        )
        if not next_state_id:
            self.sessions.save()
            return

        next_state = self.get_state(next_state_id)
        next_kind = str(next_state.get("kind") or "")
        text_override = None
        text_override_plain = None

        if (
            action_text in payment_confirm_actions
            and next_kind == "order_found"
            and self.receipt_prompt_state_id
        ):
            next_state_id = self.receipt_prompt_state_id
            next_state = self.get_state(next_state_id)
            next_kind = str(next_state.get("kind") or "")

        # Dynamic order generation for order card states.
        if next_kind == "order_card":
            order = self._ensure_runtime_order(user_id, session)
            if order is not None:
                _text_plain, _text_html, _state_id = self._render_runtime_order_text(order)
                if _text_plain or _text_html:
                    text_override = _text_html or _text_plain
                    text_override_plain = _text_plain or _text_html
        elif next_kind == "payment_method_select":
            payment_text = self._render_payment_method_text(session)
            if payment_text:
                text_override, text_override_plain = payment_text
        elif next_kind in {"wallet_prompt", "info"}:
            wallet_text = self._render_wallet_prompt_text(session, next_kind, next_state)
            if wallet_text:
                text_override, text_override_plain = wallet_text

        if action_text in payment_confirm_actions and session.last_order_id:
            self.orders.update_status(session.last_order_id, "paid")
        elif action_text in cancel_actions and session.last_order_id:
            self.orders.update_status(session.last_order_id, "cancelled")

        # For statuses, inject runtime status text from local backend when possible.
        if next_kind in {"order_found", "order_cancelled"} and session.last_order_id:
            order = self.orders.by_id(session.last_order_id)
            if order:
                if action_text in cancel_actions or next_kind == "order_cancelled":
                    order = self.orders.update_status(order.order_id, "cancelled") or order
                elif action_text in payment_confirm_actions or next_kind == "order_found":
                    order = self.orders.update_status(order.order_id, "paid") or order
                rendered_status = self.orders.render_status_text(order)
                if rendered_status:
                    text_override = rendered_status
                    text_override_plain = rendered_status

        await self._send_state(
            msg,
            session,
            next_state_id,
            text_override=text_override,
            text_override_plain=text_override_plain,
        )
        if not is_text_input and current_kind == "main_menu" and action_text == "🤑Большой розыгрыш🤑":
            self.sessions.save()
            return
        await self._auto_chain(msg, session)
        self.sessions.save()


async def amain() -> None:
    project_dir = Path(__file__).resolve().parent
    settings = load_settings(project_dir)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    runtime = CloneRuntime(settings)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(build_admin_router(runtime.admin_ctx))
    warmup_task: asyncio.Task[None] | None = None
    reload_task: asyncio.Task[None] | None = None

    @dp.message(CommandStart())
    async def on_start(msg: Message) -> None:
        user_id = msg.from_user.id if msg.from_user else msg.chat.id
        await runtime.start_flow(msg, user_id)

    @dp.message(Command("menu"))
    async def on_menu(msg: Message) -> None:
        user_id = msg.from_user.id if msg.from_user else msg.chat.id
        await runtime.start_flow(msg, user_id)

    @dp.message(Command("state"))
    async def on_state(msg: Message) -> None:
        if not settings.debug:
            return
        user_id = msg.from_user.id if msg.from_user else msg.chat.id
        session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
        await msg.answer(
            f"state={session.current_state_id}\noperation={session.pending_operation}\ncoin={session.pending_coin}\norder={session.last_order_id}",
            parse_mode=None,
        )

    @dp.callback_query(F.data.startswith("a:"))
    async def on_callback(cb: CallbackQuery) -> None:
        user_id = cb.from_user.id
        action = runtime.action_from_callback(cb.data)
        if not action:
            await cb.answer()
            return
        if action == "История сделок":
            toast_text = runtime.history_empty_toast_text(user_id)
            if toast_text:
                await cb.answer(toast_text)
                return
        await cb.answer()
        if not isinstance(cb.message, Message):
            return
        await runtime.handle_action(cb.message, user_id, action, is_text_input=False)

    @dp.message(F.photo)
    async def on_photo(msg: Message) -> None:
        await runtime.notify_admins_about_media(bot, msg, media_kind="photo")

    @dp.message(F.document & F.document.mime_type.startswith("image/"))
    async def on_image_document(msg: Message) -> None:
        await runtime.notify_admins_about_media(bot, msg, media_kind="image")

    @dp.message(StateFilter(None), F.text, ~F.text.startswith("/"))
    async def on_text(msg: Message, state: FSMContext) -> None:
        user_id = msg.from_user.id if msg.from_user else msg.chat.id
        text = (msg.text or "").strip()
        if not text:
            return

        # Try as button-like action first.
        session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
        if runtime.ensure_session_state(session):
            runtime.sessions.save()
        current_state = runtime.get_state(session.current_state_id)
        available_actions = set(current_state.get("interactive_actions") or [])
        if text in available_actions:
            await runtime.handle_action(msg, user_id, text, is_text_input=False)
            return

        # Otherwise treat as free text input.
        await runtime.handle_action(msg, user_id, text, is_text_input=True)

    try:
        if settings.hot_reload:
            reload_task = asyncio.create_task(
                _hot_reload_watchdog(settings.project_dir, settings.hot_reload_interval_seconds)
            )

        if settings.delete_webhook_on_start:
            try:
                await bot.delete_webhook(drop_pending_updates=False, request_timeout=20)
            except Exception:
                logging.warning("delete_webhook failed; continuing with polling setup.")

        async def _warm_rates() -> None:
            try:
                await runtime._current_rates(force=True)
            except Exception:
                logging.warning("CoinGecko warmup failed; using fallback rates until next refresh.")

        warmup_task = asyncio.create_task(_warm_rates())

        backoff = 2.0
        conflict_reset_attempted = False
        while True:
            try:
                await dp.start_polling(
                    bot,
                    allowed_updates=dp.resolve_used_update_types(),
                )
                break
            except TelegramNetworkError as exc:
                logging.warning("Telegram API timeout/network error: %s. Retrying in %.1fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.7, 20.0)
                continue
            except TelegramConflictError as exc:
                if conflict_reset_attempted:
                    raise
                conflict_reset_attempted = True
                logging.warning("Polling conflict (%s). Trying webhook reset once.", exc)
                await bot.delete_webhook(drop_pending_updates=False, request_timeout=20)
                await asyncio.sleep(1.0)
                continue
    finally:
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await warmup_task
        if reload_task is not None and not reload_task.done():
            reload_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reload_task
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        pass
