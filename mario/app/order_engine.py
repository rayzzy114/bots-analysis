from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
from pathlib import Path

from .models import Order, QuoteRecord


def _fmt_amount(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text


def _fmt_rub(value: float) -> str:
    return str(int(round(value)))


def _utc_now() -> datetime:
    return datetime.now(UTC)


UNICODE_ESCAPE_RE = re.compile(r"(?:\\u[0-9A-Fa-f]{4})+")


def _decode_escaped_unicode(text: str) -> str:
    if "\\u" not in text:
        return text

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        try:
            return json.loads(f'"{token}"')
        except Exception:
            return token

    return UNICODE_ESCAPE_RE.sub(repl, text)


class OrderEngine:
    def __init__(self, store_path: Path, ttl_seconds: int):
        self.store_path = store_path
        self.ttl_seconds = ttl_seconds
        self._orders: dict[str, Order] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        except Exception:
            self._orders = {}
            self.save()
            return
        if not isinstance(payload, dict):
            self._orders = {}
            self.save()
            return
        raw_orders = payload.get("orders")
        if not isinstance(raw_orders, list):
            self._orders = {}
            self.save()
            return
        for item in raw_orders:
            if not isinstance(item, dict):
                continue
            try:
                order = Order.from_dict(item)
            except Exception:
                continue
            self._orders[order.order_id] = order

    def save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"orders": [order.to_dict() for order in self._orders.values()]}
        self.store_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _new_order_id(self) -> str:
        # Similar style to captured IDs: large numeric strings.
        stamp = int(time.time() * 1000)
        suffix = f"{len(self._orders) % 1000:03d}"
        return f"{stamp}{suffix}"

    def expire_overdue(self) -> None:
        now = _utc_now()
        changed = False
        for order in self._orders.values():
            if order.status in {"paid", "cancelled", "expired"}:
                continue
            try:
                expires_at = datetime.fromisoformat(order.expires_at)
            except Exception:
                order.status = "expired"
                order.updated_at = now.isoformat()
                changed = True
                continue
            if now >= expires_at:
                order.status = "expired"
                order.updated_at = now.isoformat()
                changed = True
        if changed:
            self.save()

    def create_order(
        self,
        *,
        user_id: int,
        operation: str,
        coin: str,
        input_amount: float,
        quote: QuoteRecord,
        payment_method: str,
        wallet_or_requisites: str,
    ) -> Order:
        now = _utc_now()
        expires = now + timedelta(seconds=self.ttl_seconds)
        order = Order(
            order_id=self._new_order_id(),
            user_id=user_id,
            operation=operation,
            coin=coin,
            input_amount=float(input_amount),
            output_amount=float(quote.coin_amount if operation == "buy" else quote.rub_amount),
            pay_amount=float(quote.rub_amount if operation == "buy" else quote.coin_amount),
            net_amount=float(quote.net_amount) if quote.net_amount is not None else None,
            payment_method=payment_method,
            wallet_or_requisites=wallet_or_requisites,
            status="created",
            created_at=now.isoformat(),
            expires_at=expires.isoformat(),
            updated_at=now.isoformat(),
        )
        self._orders[order.order_id] = order
        self.save()
        return order

    def by_id(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def update_status(self, order_id: str, status: str) -> Order | None:
        order = self._orders.get(order_id)
        if not order:
            return None
        order.status = status
        order.updated_at = _utc_now().isoformat()
        self.save()
        return order

    def latest_for_user(self, user_id: int) -> Order | None:
        user_orders = [order for order in self._orders.values() if order.user_id == user_id]
        if not user_orders:
            return None
        user_orders.sort(key=lambda order: order.created_at, reverse=True)
        return user_orders[0]

    def list_for_user(self, user_id: int, *, limit: int = 10) -> list[Order]:
        user_orders = [order for order in self._orders.values() if order.user_id == user_id]
        user_orders.sort(key=lambda order: order.created_at, reverse=True)
        return user_orders[: max(1, int(limit))]

    def render_order_text(
        self,
        template_text: str,
        order: Order,
        *,
        merchant_requisites: str | None = None,
        template_sold_amount_raw: str | None = None,
        template_payout_rub: float | None = None,
        template_requisites_value: str | None = None,
    ) -> str:
        text = _decode_escaped_unicode(template_text)
        coin_lower = order.coin.lower()
        sold_amount = order.pay_amount if order.operation == "sell" else order.output_amount
        payout_amount = order.output_amount if order.operation == "sell" else order.pay_amount
        sold_value = f"{_fmt_amount(sold_amount)} {coin_lower}"
        payout_value = f"{_fmt_rub(payout_amount)} ₽"
        transfer_requisites = (merchant_requisites or order.wallet_or_requisites).strip() or order.wallet_or_requisites

        text = re.sub(
            r"(Заявка №</strong>)\s*<code>\d+</code>",
            rf"\1<code>{order.order_id}</code>",
            text,
            count=1,
        )
        text = re.sub(r"Заявка №\s*\d+", f"Заявка №{order.order_id}", text, count=1)

        if template_sold_amount_raw:
            text = text.replace(str(template_sold_amount_raw), sold_value)
        if template_payout_rub is not None:
            template_payout_value = f"{_fmt_rub(float(template_payout_rub))} ₽"
            text = text.replace(template_payout_value, payout_value)
        if template_requisites_value:
            text = text.replace(str(template_requisites_value), transfer_requisites)

        def _replace_sbp(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            return f"{prefix}<code>{order.wallet_or_requisites}</code>" if "<code>" in match.group(0) else f"{prefix}{order.wallet_or_requisites}"

        text = re.sub(
            r"(?P<prefix>📲СБП реквизиты(?:</strong>)?:\s*)(?:<code>)?[^\s<\n]+(?:</code>)?",
            _replace_sbp,
            text,
            count=1,
        )

        text = re.sub(
            r"(Реквизиты для перевода\s*[^:\n<]+(?:</strong>)?:\s*)(?:<code>)?[^\s<\n]+(?:</code>)?",
            lambda m: f"{m.group(1)}<code>{transfer_requisites}</code>"
            if "<code>" in m.group(0)
            else f"{m.group(1)}{transfer_requisites}",
            text,
            count=1,
        )

        text = re.sub(
            r"(?P<prefix>Заявка действительна(?:</strong>)?:\s*)\d+\s*минут",
            r"\g<prefix>15 минут",
            text,
            count=1,
        )
        return text

    def render_buy_order_text(
        self,
        order: Order,
        *,
        merchant_requisites: str | None = None,
    ) -> tuple[str, str]:
        coin_lower = order.coin.lower()
        coin_amount = _fmt_amount(order.output_amount)
        pay_rub = _fmt_rub(order.pay_amount)
        payout_address = order.wallet_or_requisites
        transfer_requisites = (merchant_requisites or order.wallet_or_requisites).strip() or order.wallet_or_requisites

        plain = (
            f"✅Заявка №{order.order_id}\n\n"
            f"Покупаете: {coin_amount} {coin_lower}\n"
            f"📩Адрес зачисления: {payout_address}\n\n"
            "Ваш ранг: 👶, скидка 0.0 %\n\n"
            f"💵К оплате: {pay_rub} ₽\n"
            f"Реквизиты для перевода ₽:\n\n"
            f"{transfer_requisites}\n\n"
            "⏳Заявка действительна: 15 минут\n\n"
            "☑️После успешного перевода денег по указанному кошельку нажмите на кнопку Я оплатил(а)\n"
            "или же вы можете отменить данную заявку, нажав на кнопку Отменить заявку."
        )
        html = (
            f"✅<strong>Заявка №</strong><code>{order.order_id}</code>\n\n"
            f"<strong>Покупаете</strong>: {coin_amount} {coin_lower}\n"
            f"<strong>📩Адрес зачисления</strong>: <code>{payout_address}</code>\n\n"
            "Ваш ранг: 👶, скидка 0.0 %\n\n"
            f"💵<strong>К оплате</strong>: <code>{pay_rub} ₽</code>\n"
            "<strong>Реквизиты для перевода ₽:</strong>\n\n"
            f"<code>{transfer_requisites}</code>\n\n"
            "⏳<strong>Заявка действительна</strong>: 15 минут\n\n"
            "☑️После успешного перевода денег по указанному кошельку нажмите на кнопку <strong>Я оплатил(а)</strong>\n"
            "или же вы можете отменить данную заявку, нажав на кнопку <strong>Отменить заявку</strong>."
        )
        return plain, html

    def render_status_text(self, order: Order) -> str:
        if order.status == "paid":
            return "Реквизиты найдены."
        if order.status == "cancelled":
            return "❗️ Заявка была отменена."
        if order.status == "expired":
            return "Время на оплату вышло."
        if order.status == "searching":
            return "⏳Поиск реквизита. Ожидание до 5 минут."
        return ""
