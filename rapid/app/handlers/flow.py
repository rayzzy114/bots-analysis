from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from html import escape
import logging
import random
import re
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from ..constants import COINS, FALLBACK_RATES, LINK_RESOLUTION_RULES
from ..context import AppContext
from ..flow_catalog import CapturedFlow
from ..keyboards import kb_admin_order_confirm
from ..storage import OrderData
from ..states import UserState
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, fmt_money, parse_amount, safe_username

START_MEDIA_STATE = "5ed3a8e2dd8e162af03029a68049022a"
WELCOME_STATE = "390d06fac1d19a492ff5bf3658fd7b7b"
INSTRUCTION_STATE = "d8179509e955f0642f5eee47106d56f2"
EXCHANGE_MEDIA_STATE = "f8d30f846a410482317b659f91acf8c2"
OPERATIONS_STATE = "f73aa46fb5fb87104fd72f1f612019b1"
BUY_COIN_STATE = "fb7f39a4c9ddb6f73c145c48f620c7df"
SELL_DISABLED_STATE = "ebb021aeb1944a9ee69b8bd26cfb2c0c"
CONTACTS_STATE = "f926cdaa54b21656b0bcd756aa7816d1"
PARTNERS_STATE = "f8f12d4782ec3a1e8252f64f009f009c"
CABINET_STATE = "33550d4a0bf5a22db75c777eb13a4ee1"
HISTORY_STATE = "3c81e8134349069fe23d897cc244a625"
INVALID_AMOUNT_STATE = "8c18dfa923776b23d869f4a80eede9b1"
INVALID_WALLET_STATE = "3f854859483210f0258ce4066c5d8d90"

WALLET_PROMPT_TEMPLATE_STATE = "0d3fcaa213fb05de855d32e167dc44e7"
METHOD_PROMPT_TEMPLATE_STATE = "c3b6c60472b1b04888ca68d23b6cc296"
CONFIRM_TEMPLATE_STATE = "b868d8d3fd4f618a097e96656fe1f153"
ORDER_WAIT_TEMPLATE_STATE = "b1598d5b51303a3d46b9f1db19302c5f"
ORDER_CANCEL_TEMPLATE_STATE = "8a853240e7713dbd4e1119cf48a91905"
OTHER_COINS_INFO_STATE = "f8f12d4782ec3a1e8252f64f009f009c"

COIN_PROMPT_STATES = {
    "BTC": "ac92e28a05d99490c186f643ec57f6d9",
    "LTC": "7ecc30e7c7c14b1e7a7a2de95ad40c49",
    "ETH": "84908c7f4117a9405f3419fb4496043b",
    "SOL": "7ef49a46b384bbd48ced4333baeae942",
    "USDT": "bd053d13b9f5cd022294170b554d642b",
}

COIN_KEYS = {
    "BTC": "btc",
    "LTC": "ltc",
    "ETH": "eth",
    "SOL": "sol",
    "USDT": "usdt",
}

SAMPLE_BTC_WALLET = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
SAMPLE_LTC_WALLET = "ltc1qg82h9m6k9n9f3q2w8f8l2m7f9h7n4k3s2x1d0c"
PAYMENT_CONFIRMED_ACTION = "Я оплатил"

BOLD_LINE_PREFIXES = (
    "Ваша заявка",
    "от ",
    "до ",
    "🔸 Введите сумму",
    "🔸 Или введите сумму",
    "🔸 Выберите способ оплаты!",
    "🔸Для оплаты по Вашей заявке",
    "🎈 Используйте",
    "✅ Чтобы продолжить",
    "🔁 Если вы допустили ошибку",
    "❗️ Нажав кнопку",
    "⚠️ Подбираем для Вас реквизиты",
    "❗️ Если Вы хотите отменить заявку",
    "❌ Вы самостоятельно отменили данную заявку!",
    "✅ Чтобы создать новую",
    "❗В данном разделе",
    "🤝 Вы можете написать",
    "✅ Чтобы не упускать",
    "⚠️ Оплатите или отмените предыдущую заявку",
)

BOLD_EXACT_LINES = {
    "👀 Проверьте и подтвердите Ваши данные!",
    "🔹Укажите кошелек!",
    "🔸Укажите кошелек!",
    "🔸 Укажите кошелек!",
}

LABEL_ONLY_BOLD_PREFIXES = (
    "Операция:",
    "Валюта:",
    "Кол-во:",
    "Кошелек:",
    "Способ оплаты:",
    "Вы получите:",
    "Ваш кошелек:",
)

CURRENCY_TOKEN_PATTERN = re.compile(r"\b(BTC|RUB|USDT|ETH|SOL|LTC)\b")
RUBLE_WORD_PATTERN = re.compile(r"\b(Руб(?:ль|ля|лей)?)\b", re.IGNORECASE)
NUMBER_TOKEN_PATTERN = re.compile(r"(?<!\w)(\d[\d\s.,]*\d|\d)(?!\w)")
logger = logging.getLogger(__name__)

def _normalize_lookup_value(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def build_link_key_resolver(
    rules: Mapping[str, Mapping[str, tuple[str, ...]]] = LINK_RESOLUTION_RULES,
) -> Callable[[str, str], str | None]:
    text_rules: list[tuple[str, str]] = []
    source_url_map: dict[str, str] = {}

    for link_key, rule in rules.items():
        for token in rule.get("text_contains", ()):
            normalized = _normalize_lookup_value(str(token))
            if normalized:
                text_rules.append((normalized, link_key))
        for source_url in rule.get("source_urls", ()):
            normalized_url = str(source_url).strip()
            if normalized_url:
                source_url_map[normalized_url] = link_key
    text_rules.sort(key=lambda item: len(item[0]), reverse=True)

    def resolve_link_key(button_text: str, original_url: str) -> str | None:
        normalized_text = _normalize_lookup_value(button_text)
        if normalized_text:
            for token, link_key in text_rules:
                if token in normalized_text:
                    return link_key
        return source_url_map.get(original_url.strip())

    return resolve_link_key


def build_button_url_resolver(
    link_source: Mapping[str, str] | Callable[[str], str],
    link_key_resolver: Callable[[str, str], str | None] | None = None,
) -> Callable[[str, str], str]:
    resolve_link_key = link_key_resolver or build_link_key_resolver()

    def get_link(key: str) -> str:
        if callable(link_source):
            value = link_source(key)
        else:
            value = link_source.get(key, "")
        return str(value or "").strip()

    def resolve(button_text: str, original_url: str) -> str:
        resolved_key = resolve_link_key(button_text, original_url)
        if resolved_key is None:
            return original_url
        override_url = get_link(resolved_key)
        return override_url or original_url

    return resolve


def apply_runtime_text_links_to_text(
    text: str,
    text_links: list[str],
    link_key_resolver: Callable[[str, str], str | None],
    url_resolver: Callable[[str, str], str],
) -> str:
    if not text_links:
        return text

    rendered = text
    for original_url in text_links:
        source_url = original_url.strip()
        if not source_url:
            continue
        link_key = link_key_resolver("", source_url)
        runtime_url = url_resolver("", source_url).strip() or source_url
        if runtime_url.startswith("t.me/"):
            runtime_url = "https://" + runtime_url
        escaped_runtime_url = escape(runtime_url, quote=True)

        if link_key == "terms":
            replaced, count = re.subn(
                r"(условиями сделки)",
                rf'<a href="{escaped_runtime_url}">\1</a>',
                rendered,
                count=1,
                flags=re.IGNORECASE,
            )
            if count:
                rendered = replaced
            continue

        escaped_source = escape(source_url, quote=False)
        text_variants = [
            escaped_source,
            NUMBER_TOKEN_PATTERN.sub(r"<b>\1</b>", escaped_source),
        ]
        for source_variant in text_variants:
            if source_variant not in rendered:
                continue
            rendered = rendered.replace(
                source_variant,
                f'<a href="{escaped_runtime_url}">{source_variant}</a>',
                1,
            )
            break

    return rendered


def _kb_order_pending(order_id: str, cancel_action_text: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=PAYMENT_CONFIRMED_ACTION, callback_data=f"order:paid:{order_id}")],
            [InlineKeyboardButton(text=cancel_action_text, callback_data=f"order:cancel:{order_id}")],
        ]
    )


def _build_requisites_text(order_id: str, order: OrderData) -> str:
    amount_rub = fmt_money(order["amount_rub"])
    amount_coin = fmt_coin(order["coin_amount"])
    bank = escape(order["bank"], quote=False)
    requisites = escape(order["requisites"], quote=False)
    coin_symbol = escape(order["coin_symbol"], quote=False)
    payment_method = escape(order["payment_method"], quote=False)
    wallet = escape(order["wallet"], quote=False)
    return (
        f"<b>Ваша заявка: № {order_id}</b>\n\n"
        "<b>🔴 НЕВЕРНАЯ / НЕСВОЕВРЕМЕННАЯ ОПЛАТА ВЛЕЧЕТ ЗА СОБОЙ "
        "НЕОБРАТИМУЮ ПОТЕРЮ СРЕДСТВ!</b>\n\n"
        f"<b>⚠️ Для завершения сделки оплатите {amount_rub} RUB (Рублей) "
        "в течение 15 минут на счёт RAPID EXCHANGE! ⬇️</b>\n\n"
        f"<b>{bank}:</b>\n"
        f"{requisites}\n\n"
        f"<b>Вы получите: {amount_coin} {coin_symbol}</b>\n"
        f"<b>Способ оплаты: {payment_method}</b>\n"
        f"<b>Ваш кошелек: {wallet}</b>\n\n"
        "✅ После оплаты нажмите\n"
        "\"Я оплатил\" и ожидайте ответ от бота!\n\n"
        "❌ Если Вы хотите отменить заявку, нажмите \"Отмена\"!"
    )


async def send_requisites_after_delay(
    *,
    ctx: AppContext,
    bot: Bot,
    order_id: str,
    cancel_action_text: str,
    delay_seconds: int = 15,
    max_attempts: int = 3,
    retry_base_delay_seconds: int = 2,
) -> None:
    await asyncio.sleep(delay_seconds)
    safe_attempts = max(1, max_attempts)
    safe_base_delay = max(1, retry_base_delay_seconds)

    for attempt in range(1, safe_attempts + 1):
        order = ctx.orders.get_order(order_id)
        if order is None:
            return
        if order["status"] != "pending_payment" or order["requisites_sent"]:
            return

        text = _build_requisites_text(order_id, order)
        try:
            await bot.send_message(
                chat_id=order["user_id"],
                text=text,
                reply_markup=_kb_order_pending(order_id, cancel_action_text),
            )
            ctx.orders.mark_requisites_sent(order_id)
            return
        except Exception:
            logger.exception(
                "Failed to send requisites for order %s (attempt %s/%s)",
                order_id,
                attempt,
                safe_attempts,
            )
            if attempt >= safe_attempts:
                return
            backoff_seconds = safe_base_delay * (2 ** (attempt - 1))
            await asyncio.sleep(backoff_seconds)


def schedule_pending_requisites_recovery(
    *,
    ctx: AppContext,
    bot: Bot,
    flow_file: str,
    supports_inline_queries: bool = False,
    delay_seconds: int = 15,
) -> int:
    flow = CapturedFlow(Path(flow_file), supports_inline_queries=supports_inline_queries)
    wait_rows = flow.state(ORDER_WAIT_TEMPLATE_STATE).get("button_rows", [])
    cancel_action_text = (
        str(wait_rows[0][0]["text"])
        if wait_rows and wait_rows[0] and isinstance(wait_rows[0][0], dict)
        else "Отмена"
    )

    scheduled = 0
    for order in ctx.orders.data.values():
        if order["status"] != "pending_payment" or order["requisites_sent"]:
            continue
        asyncio.create_task(
            send_requisites_after_delay(
                ctx=ctx,
                bot=bot,
                order_id=order["order_id"],
                cancel_action_text=cancel_action_text,
                delay_seconds=delay_seconds,
            )
        )
        scheduled += 1
    return scheduled


def build_flow_router(
    ctx: AppContext,
    assets_dir: str,
    flow_file: str,
    supports_inline_queries: bool = False,
) -> Router:
    router = Router(name="rapid-flow")
    assets_path = Path(assets_dir)
    link_key_resolver = build_link_key_resolver()
    url_resolver = build_button_url_resolver(
        ctx.settings.link,
        link_key_resolver=link_key_resolver,
    )
    flow = CapturedFlow(
        Path(flow_file),
        supports_inline_queries=supports_inline_queries,
        url_resolver=url_resolver,
    )

    main_rows = flow.state(START_MEDIA_STATE).get("button_rows", [])
    menu_exchange = str(main_rows[0][0]["text"])
    menu_contacts = str(main_rows[0][1]["text"])
    menu_history = str(main_rows[1][0]["text"])
    menu_cabinet = str(main_rows[1][1]["text"])
    menu_partners = str(main_rows[2][0]["text"])
    menu_help = str(main_rows[2][1]["text"])

    op_rows = flow.state(OPERATIONS_STATE).get("button_rows", [])
    action_buy = str(op_rows[0][0]["text"])
    action_sell = str(op_rows[0][1]["text"])

    buy_rows = flow.state(BUY_COIN_STATE).get("button_rows", [])
    action_other = str(buy_rows[1][2]["text"])

    history_rows = flow.state(HISTORY_STATE).get("button_rows", [])
    action_history_details = str(history_rows[0][0]["text"]) if history_rows else "История сделок"

    confirm_rows = flow.state(CONFIRM_TEMPLATE_STATE).get("button_rows", [])
    action_confirm = str(confirm_rows[0][0]["text"])
    action_bonus = str(confirm_rows[0][1]["text"])
    action_retry = str(confirm_rows[1][0]["text"])

    wait_rows = flow.state(ORDER_WAIT_TEMPLATE_STATE).get("button_rows", [])
    action_cancel_order = str(wait_rows[0][0]["text"])

    calc_button_rows = flow.state(COIN_PROMPT_STATES["BTC"]).get("button_rows", [])
    action_calc = str(calc_button_rows[0][0]["text"])

    method_actions = [
        str(btn.get("text") or "")
        for row in flow.state(METHOD_PROMPT_TEMPLATE_STATE).get("button_rows", [])
        for btn in row
    ]

    def format_rich_text(text: str, state_id: str) -> str:
        def emphasize_inline_tokens(escaped_line: str) -> str:
            line = NUMBER_TOKEN_PATTERN.sub(r"<b>\1</b>", escaped_line)
            line = CURRENCY_TOKEN_PATTERN.sub(r"<b>\1</b>", line)
            line = RUBLE_WORD_PATTERN.sub(r"<b>\1</b>", line)
            return line

        def bold_label_only(escaped_line: str) -> str:
            for prefix in LABEL_ONLY_BOLD_PREFIXES:
                if escaped_line.startswith(prefix):
                    rest = escaped_line[len(prefix) :].lstrip()
                    if rest:
                        return f"<b>{prefix}</b> {emphasize_inline_tokens(rest)}"
                    return f"<b>{prefix}</b>"
            return escaped_line

        lines = text.splitlines()
        rendered: list[str] = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            escaped_line = escape(line, quote=False)
            should_bold = False
            if state_id == WELCOME_STATE and idx == 0 and stripped:
                should_bold = True
            if any(stripped.startswith(prefix) for prefix in BOLD_LINE_PREFIXES):
                should_bold = True
            if stripped in BOLD_EXACT_LINES:
                should_bold = True
            if any(stripped.startswith(prefix) for prefix in LABEL_ONLY_BOLD_PREFIXES):
                rendered.append(bold_label_only(escaped_line))
                continue
            if should_bold:
                rendered.append(f"<b>{escaped_line}</b>")
            else:
                rendered.append(emphasize_inline_tokens(escaped_line))
        return "\n".join(rendered)

    async def send_state(msg: Message, state_id: str) -> None:
        text = flow.text(state_id)
        media_file = flow.media_file(state_id, assets_path)
        reply_markup = flow.reply_keyboard(state_id)
        inline_markup = flow.inline_keyboard(state_id)
        markup = reply_markup or inline_markup
        rich_text = format_rich_text(text, state_id) if text else ""
        rich_text = apply_runtime_text_links_to_text(
            rich_text,
            text_links=flow.text_links(state_id),
            link_key_resolver=link_key_resolver,
            url_resolver=url_resolver,
        )

        if media_file and text:
            await msg.answer_photo(FSInputFile(str(media_file)))
            await msg.answer(rich_text, reply_markup=markup)
            return
        if media_file:
            await msg.answer_photo(FSInputFile(str(media_file)), reply_markup=markup)
            return
        if text:
            await msg.answer(rich_text, reply_markup=markup)

    async def send_text_with_state_buttons(
        msg: Message,
        text: str,
        button_state_id: str,
        text_state_id: str | None = None,
    ) -> None:
        markup = flow.inline_keyboard(button_state_id) or flow.reply_keyboard(button_state_id)
        target_state_id = text_state_id or button_state_id
        rich_text = format_rich_text(text, target_state_id)
        rich_text = apply_runtime_text_links_to_text(
            rich_text,
            text_links=flow.text_links(target_state_id),
            link_key_resolver=link_key_resolver,
            url_resolver=url_resolver,
        )
        await msg.answer(rich_text, reply_markup=markup)

    def replace_line(text: str, prefix: str, value: str) -> str:
        pattern = rf"(?m)^{re.escape(prefix)}.*$"
        return re.sub(pattern, f"{prefix}{value}", text, count=1)

    def build_wallet_prompt(coin_title: str, symbol: str, amount_coin: float) -> str:
        text = flow.text(WALLET_PROMPT_TEMPLATE_STATE)
        text = replace_line(text, "Валюта: ", coin_title)
        text = replace_line(text, "Кол-во: ", f"{fmt_coin(amount_coin)} {symbol}")
        return text

    def build_method_prompt(coin_title: str, symbol: str, amount_coin: float, wallet: str) -> str:
        text = flow.text(METHOD_PROMPT_TEMPLATE_STATE)
        text = replace_line(text, "Валюта: ", coin_title)
        text = replace_line(text, "Кол-во: ", f"{fmt_coin(amount_coin)} {symbol}")
        text = replace_line(text, "Кошелек: ", wallet)
        text = text.replace(SAMPLE_BTC_WALLET, wallet)
        return text

    def build_confirm_prompt(
        coin_title: str,
        symbol: str,
        amount_coin: float,
        wallet: str,
        payment_method: str,
    ) -> str:
        text = flow.text(CONFIRM_TEMPLATE_STATE)
        text = replace_line(text, "Валюта: ", coin_title)
        text = replace_line(text, "Кол-во: ", f"{fmt_coin(amount_coin)} {symbol}")
        text = replace_line(text, "Способ оплаты: ", payment_method)
        text = replace_line(text, "Кошелек: ", wallet)
        text = text.replace(SAMPLE_BTC_WALLET, wallet)
        return text

    def build_wait_prompt(
        order_id: str,
        symbol: str,
        amount_coin: float,
        wallet: str,
        payment_method: str,
    ) -> str:
        text = flow.text(ORDER_WAIT_TEMPLATE_STATE)
        text = re.sub(r"Ваша заявка:\s*№\s*\d+", f"Ваша заявка: № {order_id}", text, count=1)
        text = replace_line(text, "Вы получите: ", f"{fmt_coin(amount_coin)} {symbol}")
        text = replace_line(text, "Способ оплаты: ", payment_method)
        text = replace_line(text, "Ваш кошелек: ", wallet)
        text = text.replace(SAMPLE_LTC_WALLET, wallet)
        return text

    def build_cancel_text(order_id: str) -> str:
        text = flow.text(ORDER_CANCEL_TEMPLATE_STATE)
        return re.sub(r"Ваша заявка:\s*№\s*\d+", f"Ваша заявка: №{order_id}", text, count=1)

    def parse_requisites_candidates(raw_value: str) -> list[str]:
        parsed: list[str] = []
        for chunk in re.split(r"[;\n|]+", raw_value):
            item = chunk.strip()
            if not item:
                continue
            item = re.sub(r"\([^)]*\)", "", item).strip()
            if not item:
                continue
            if re.search(r"[A-Za-zА-Яа-я]", item) and re.search(r"\d", item):
                digits = "".join(re.findall(r"\d+", item))
                if len(digits) >= 10:
                    item = digits
            if item and item not in parsed:
                parsed.append(item)
        if parsed:
            return parsed
        fallback = re.sub(r"\([^)]*\)", "", raw_value).strip()
        return [fallback] if fallback else []

    def pick_order_requisites(payment_method: str) -> tuple[str, str]:
        bank, raw_value = ctx.settings.method_requisites(payment_method)
        candidates = parse_requisites_candidates(raw_value)
        chosen = random.choice(candidates) if candidates else raw_value.strip()
        return bank.strip() or "Реквизиты", chosen

    def is_valid_wallet(coin_key: str, wallet: str) -> bool:
        clean = wallet.strip()
        if not clean:
            return False
        no_spaces = clean.replace(" ", "")
        if coin_key == "btc":
            return bool(re.match(r"^(bc1|[13])[a-zA-HJ-NP-Z0-9]{20,}$", no_spaces))
        if coin_key == "ltc":
            return bool(re.match(r"^(ltc1|[LM3])[a-zA-HJ-NP-Z1-9]{20,}$", no_spaces))
        if coin_key == "eth":
            return bool(re.match(r"^0x[a-fA-F0-9]{40}$", no_spaces))
        if coin_key == "sol":
            return bool(re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", no_spaces))
        if coin_key == "usdt":
            return bool(re.match(r"^T[1-9A-HJ-NP-Za-km-z]{33}$", no_spaces))
        return len(no_spaces) >= 20

    async def notify_admin_new_order(message: Message, order_id: str) -> None:
        order = ctx.orders.get_order(order_id)
        if order is None:
            return
        bot = message.bot
        if bot is None:
            return
        username = escape(safe_username(order["username"]), quote=False)
        safe_order_id = escape(order["order_id"], quote=False)
        safe_wallet = escape(order["wallet"], quote=False)
        safe_coin_symbol = escape(order["coin_symbol"], quote=False)
        safe_payment_method = escape(order["payment_method"], quote=False)
        text = (
            "🆕 Новый заказ!\n\n"
            f"📦 ID заказа: {safe_order_id}\n"
            f"👤 ID: {order['user_id']}\n"
            f"📝 Username: {username}\n"
            "👛 Кошелек:\n"
            f"<code>{safe_wallet}</code>\n\n"
            f"💎 Крипта: {fmt_coin(order['coin_amount'])} {safe_coin_symbol}\n"
            f"💰 Сумма: {fmt_money(order['amount_rub'])} RUB\n"
            f"💳 Способ оплаты: {safe_payment_method}"
        )
        for admin_id in ctx.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=kb_admin_order_confirm(order["order_id"]),
                )
            except Exception:
                continue

    async def notify_admin_paid_order(message: Message, order_id: str) -> None:
        order = ctx.orders.get_order(order_id)
        if order is None:
            return
        bot = message.bot
        if bot is None:
            return
        username = escape(safe_username(order["username"]), quote=False)
        safe_order_id = escape(order["order_id"], quote=False)
        safe_payment_method = escape(order["payment_method"], quote=False)
        text = (
            "💸 ПОЛЬЗОВАТЕЛЬ НАЖАЛ «Я оплатил»\n\n"
            f"📦 ID заказа: {safe_order_id}\n"
            f"👤 ID: {order['user_id']}\n"
            f"📝 Username: {username}\n"
            f"💰 Сумма: {fmt_money(order['amount_rub'])} RUB\n"
            f"💳 Способ оплаты: {safe_payment_method}\n"
            f"🏦 Реквизиты: <code>{escape(order['requisites'], quote=False)}</code>"
        )
        for admin_id in ctx.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=kb_admin_order_confirm(order["order_id"]),
                )
            except Exception:
                continue

    def latest_open_order_id(user_id: int) -> str:
        latest_order_id = ""
        latest_updated_at = -1
        for order in ctx.orders.data.values():
            if order["user_id"] != user_id:
                continue
            if order["status"] not in {"pending_payment", "paid"}:
                continue
            if order["updated_at"] > latest_updated_at:
                latest_updated_at = order["updated_at"]
                latest_order_id = order["order_id"]
        return latest_order_id

    async def send_main_menu(msg: Message) -> None:
        await send_state(msg, START_MEDIA_STATE)
        await send_state(msg, WELCOME_STATE)

    @router.message(Command("start"))
    async def start_cmd(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_main_menu(message)

    @router.message(F.text == menu_exchange)
    async def menu_exchange_open(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_state(message, EXCHANGE_MEDIA_STATE)
        await send_state(message, OPERATIONS_STATE)

    @router.message(F.text == menu_contacts)
    async def menu_contacts_open(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_state(message, CONTACTS_STATE)

    @router.message(F.text == menu_history)
    async def menu_history_open(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_state(message, HISTORY_STATE)

    @router.message(F.text == menu_cabinet)
    async def menu_cabinet_open(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_state(message, CABINET_STATE)

    @router.message(F.text == menu_partners)
    async def menu_partners_open(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_state(message, PARTNERS_STATE)

    @router.message(F.text == menu_help)
    async def menu_help_open(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_state(message, INSTRUCTION_STATE)

    @router.message(UserState.waiting_buy_amount)
    async def buy_amount_input(message: Message, state: FSMContext) -> None:
        amount = parse_amount(message.text or "")
        if amount is None:
            await send_state(message, INVALID_AMOUNT_STATE)
            return
        data = await state.get_data()
        coin_button = str(data.get("coin_button") or "")
        coin_key = COIN_KEYS.get(coin_button)
        if not coin_key:
            await send_state(message, BUY_COIN_STATE)
            return

        rates = await ctx.rates.get_rates()
        rate = float(rates.get(coin_key) or FALLBACK_RATES[coin_key])

        if amount >= 1000:
            amount_rub = amount
            amount_coin = amount / max(rate, 1e-9)
        else:
            amount_coin = amount
            amount_rub = amount * rate

        if amount_rub < 1000 or amount_rub > 150000:
            await send_state(message, INVALID_AMOUNT_STATE)
            return

        symbol = COINS[coin_key]["symbol"]
        coin_title = COINS[coin_key]["title"]
        await state.update_data(
            coin_key=coin_key,
            coin_title=coin_title,
            coin_symbol=symbol,
            amount_coin=amount_coin,
            amount_rub=amount_rub,
        )
        await state.set_state(UserState.waiting_buy_wallet)
        wallet_prompt = build_wallet_prompt(coin_title, symbol, amount_coin)
        await message.answer(format_rich_text(wallet_prompt, WALLET_PROMPT_TEMPLATE_STATE))

    @router.message(UserState.waiting_buy_wallet)
    async def buy_wallet_input(message: Message, state: FSMContext) -> None:
        wallet = (message.text or "").strip()
        data = await state.get_data()
        coin_key = str(data.get("coin_key") or "")
        coin_title = str(data.get("coin_title") or "")
        symbol = str(data.get("coin_symbol") or "")
        amount_coin = float(data.get("amount_coin") or 0.0)
        if not coin_key or not is_valid_wallet(coin_key, wallet):
            await send_state(message, INVALID_WALLET_STATE)
            return

        await state.update_data(wallet=wallet)
        await state.set_state(UserState.waiting_buy_payment_method)
        text = build_method_prompt(coin_title, symbol, amount_coin, wallet)
        await send_text_with_state_buttons(message, text, METHOD_PROMPT_TEMPLATE_STATE)

    @router.message(F.photo | (F.document & F.document.mime_type.startswith("image/")))
    async def forward_client_images(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or ctx.is_admin(user_id):
            return
        if not ctx.admin_ids:
            return
        bot = message.bot
        if bot is None:
            return

        data = await state.get_data()
        order_id = str(data.get("order_id") or "") or latest_open_order_id(user_id)
        username = safe_username((message.from_user.username if message.from_user else "") or "")
        user_caption = (message.caption or "").strip()

        caption_lines = [
            "❗️ Фото от клиента",
            f"👤 ID: {user_id}",
            f"📝 Username: {username}",
        ]
        if order_id:
            caption_lines.append(f"📦 ID заказа: {escape(order_id, quote=False)}")
        if user_caption:
            caption_lines.append(f"💬 Комментарий: {escape(user_caption, quote=False)}")
        admin_caption = "\n".join(caption_lines)
        if len(admin_caption) > 1024:
            admin_caption = admin_caption[:1021] + "..."

        for admin_id in ctx.admin_ids:
            try:
                if message.photo:
                    await bot.send_photo(
                        chat_id=admin_id,
                        photo=message.photo[-1].file_id,
                        caption=admin_caption,
                    )
                elif message.document is not None:
                    await bot.send_document(
                        chat_id=admin_id,
                        document=message.document.file_id,
                        caption=admin_caption,
                    )
            except Exception:
                continue

        await message.answer("✅ Фото получено. Передали оператору.")

    @router.callback_query(F.data.startswith("a:"))
    async def callback_actions(callback: CallbackQuery, state: FSMContext) -> None:
        action = flow.action_from_callback(callback.data)
        msg = callback_message(callback)
        if action is None or msg is None:
            await callback.answer()
            return

        if action == action_history_details:
            await callback.answer()
            await msg.answer("У Вас пока нет сделок.")
            return

        if action == action_buy:
            await state.clear()
            await callback.answer()
            await send_state(msg, EXCHANGE_MEDIA_STATE)
            await send_state(msg, BUY_COIN_STATE)
            return

        if action == action_sell:
            await state.clear()
            await callback.answer()
            await send_state(msg, EXCHANGE_MEDIA_STATE)
            await send_state(msg, SELL_DISABLED_STATE)
            return

        if action in COIN_PROMPT_STATES:
            await callback.answer()
            await state.clear()
            await state.update_data(coin_button=action)
            await state.set_state(UserState.waiting_buy_amount)
            await send_state(msg, COIN_PROMPT_STATES[action])
            return

        if action == action_other:
            await callback.answer()
            await send_state(msg, OTHER_COINS_INFO_STATE)
            return

        if action == action_calc:
            await callback.answer()
            await msg.answer(
                "Укажите количество валюты\nВвод в BTC или RUB",
                reply_markup=ForceReply(selective=True),
            )
            return

        current_state = await state.get_state()
        data = await state.get_data()

        if current_state == UserState.waiting_buy_payment_method.state and action in method_actions:
            await callback.answer()
            coin_title = str(data.get("coin_title") or "")
            symbol = str(data.get("coin_symbol") or "")
            amount_coin = float(data.get("amount_coin") or 0.0)
            wallet = str(data.get("wallet") or "")
            await state.update_data(payment_method=action)
            await state.set_state(UserState.waiting_buy_confirmation)
            text = build_confirm_prompt(
                coin_title=coin_title,
                symbol=symbol,
                amount_coin=amount_coin,
                wallet=wallet,
                payment_method=action,
            )
            await send_text_with_state_buttons(msg, text, CONFIRM_TEMPLATE_STATE)
            return

        if current_state == UserState.waiting_buy_confirmation.state:
            if action == action_bonus:
                await callback.answer("Раздел бонусов временно недоступен", show_alert=True)
                return
            if action == action_retry:
                await callback.answer()
                await state.clear()
                await send_state(msg, BUY_COIN_STATE)
                return
            if action == action_confirm:
                user_id = callback_user_id(callback)
                if user_id is None:
                    await callback.answer("Пользователь не найден", show_alert=True)
                    return
                symbol = str(data.get("coin_symbol") or "")
                amount_coin = float(data.get("amount_coin") or 0.0)
                amount_rub = float(data.get("amount_rub") or 0.0)
                wallet = str(data.get("wallet") or "")
                payment_method = str(data.get("payment_method") or "")
                bank, requisites = pick_order_requisites(payment_method)
                order = ctx.orders.create_order(
                    user_id=user_id,
                    username=(callback.from_user.username if callback.from_user else "") or "",
                    wallet=wallet,
                    coin_symbol=symbol,
                    coin_amount=amount_coin,
                    amount_rub=amount_rub,
                    payment_method=payment_method,
                    bank=bank,
                    requisites=requisites,
                )
                await notify_admin_new_order(msg, order["order_id"])
                await state.update_data(order_id=order["order_id"])
                await state.set_state(UserState.waiting_buy_order_pending)
                await callback.answer()
                wait_text = build_wait_prompt(
                    order_id=order["order_id"],
                    symbol=symbol,
                    amount_coin=amount_coin,
                    wallet=wallet,
                    payment_method=payment_method,
                )
                await send_text_with_state_buttons(msg, wait_text, ORDER_WAIT_TEMPLATE_STATE)
                if msg.bot is not None:
                    asyncio.create_task(
                        send_requisites_after_delay(
                            ctx=ctx,
                            bot=msg.bot,
                            order_id=order["order_id"],
                            cancel_action_text=action_cancel_order,
                        )
                    )
                return

        if current_state == UserState.waiting_buy_order_pending.state and action == action_cancel_order:
            order_id = str(data.get("order_id") or "")
            if not order_id:
                await callback.answer("Заявка не найдена", show_alert=True)
                return
            try:
                await msg.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            cancelled = ctx.orders.mark_cancelled(order_id)
            if cancelled:
                await callback.answer("Заявка отменена")
                cancel_text = build_cancel_text(order_id)
                await msg.answer(format_rich_text(cancel_text, ORDER_CANCEL_TEMPLATE_STATE))
            else:
                await callback.answer("Заявку уже нельзя отменить", show_alert=True)
                await msg.answer("⚠️ Заявка уже в обработке и не может быть отменена.")
            await state.clear()
            await send_main_menu(msg)
            return

        await callback.answer()

    @router.callback_query(F.data.startswith("order:paid:"))
    async def order_paid(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        user_id = callback_user_id(callback)
        if msg is None or user_id is None:
            await callback.answer()
            return
        order_id = (callback.data or "").split(":")[-1]
        order = ctx.orders.get_order(order_id)
        if order is None or order["user_id"] != user_id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        if order["status"] == "paid":
            await callback.answer("Оплата уже отмечена")
            return
        if order["status"] == "confirmed":
            await callback.answer("Заявка уже подтверждена")
            return
        if order["status"] == "cancelled":
            await callback.answer("Заявка отменена", show_alert=True)
            return
        if not ctx.orders.mark_paid(order_id):
            await callback.answer("Не удалось отметить оплату", show_alert=True)
            return
        await state.update_data(order_id=order_id)
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("Оплата отмечена")
        await msg.answer(
            "❗️ Пожалуйста, отправьте скриншот оплаты сюда в чат.\n"
            "⏳ Оплата отмечена. Ожидайте подтверждение оператора."
        )
        await notify_admin_paid_order(msg, order_id)

    @router.callback_query(F.data.startswith("order:cancel:"))
    async def order_cancel_direct(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        user_id = callback_user_id(callback)
        if msg is None or user_id is None:
            await callback.answer()
            return
        order_id = (callback.data or "").split(":")[-1]
        order = ctx.orders.get_order(order_id)
        if order is None or order["user_id"] != user_id:
            await callback.answer("Заявка не найдена", show_alert=True)
            return
        try:
            await msg.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        cancelled = ctx.orders.mark_cancelled(order_id)
        if cancelled:
            await callback.answer("Заявка отменена")
            cancel_text = build_cancel_text(order_id)
            await msg.answer(format_rich_text(cancel_text, ORDER_CANCEL_TEMPLATE_STATE))
        else:
            await callback.answer("Заявку уже нельзя отменить", show_alert=True)
            await msg.answer("⚠️ Заявка уже в обработке и не может быть отменена.")
        await state.clear()
        await send_main_menu(msg)

    return router
