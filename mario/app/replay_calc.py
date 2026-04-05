from __future__ import annotations

import re
from typing import Any

from .models import PromoRecord, QuoteRecord

NUMBER_RE = re.compile(r"[-+]?\d[\d\s.,]*")


def _parse_amount(value: str) -> float | None:
    if not value:
        return None
    match = NUMBER_RE.search(value)
    if not match:
        return None
    raw = match.group(0).replace(" ", "")
    if raw.count(",") and raw.count("."):
        raw = raw.replace(",", "")
    elif raw.count(","):
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _norm_coin(value: str) -> str:
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
    if t == "ETH":
        return "ETH"
    if t == "SOL":
        return "SOL"
    return t


class ReplayCalculator:
    def __init__(self, replay_payload: dict[str, Any]):
        self.prompt_states = replay_payload.get("prompt_states", {})
        self.quotes: list[QuoteRecord] = [
            QuoteRecord(
                state_id=str(row["state_id"]),
                operation=str(row["operation"]),
                coin=_norm_coin(str(row["coin"])),
                coin_amount=float(row["coin_amount"]),
                rub_amount=float(row["rub_amount"]),
                net_amount=float(row["net_amount"]) if row.get("net_amount") is not None else None,
            )
            for row in replay_payload.get("quotes", [])
            if isinstance(row, dict)
        ]
        self.promos: list[PromoRecord] = [
            PromoRecord(
                state_id=str(row["state_id"]),
                coin=_norm_coin(str(row["coin"])),
                coin_amount=float(row["coin_amount"]),
                pay_before=float(row["pay_before"]),
                pay_after=float(row["pay_after"]),
            )
            for row in replay_payload.get("promos", [])
            if isinstance(row, dict)
        ]
        self.order_templates: list[dict[str, Any]] = [
            row for row in replay_payload.get("order_templates", []) if isinstance(row, dict)
        ]

    def coin_for_prompt_state(self, operation: str, state_id: str) -> str | None:
        op_map = self.prompt_states.get(operation, {})
        for coin, sid in op_map.items():
            if sid == state_id:
                return _norm_coin(coin)
        return None

    def nearest_quote(
        self,
        operation: str,
        coin: str,
        user_input: str,
    ) -> QuoteRecord | None:
        amount = _parse_amount(user_input)
        if amount is None:
            return None
        coin_norm = _norm_coin(coin)
        candidates = [
            quote
            for quote in self.quotes
            if quote.operation == operation and _norm_coin(quote.coin) == coin_norm
        ]
        if not candidates:
            return None

        def score(quote: QuoteRecord) -> float:
            # Input can be either coin amount or rub amount.
            dist_coin = abs(amount - quote.coin_amount) / max(quote.coin_amount, 1e-6)
            dist_rub = abs(amount - quote.rub_amount) / max(quote.rub_amount, 1.0)
            return min(dist_coin, dist_rub)

        return min(candidates, key=score)

    def promo_for_quote(self, quote: QuoteRecord) -> PromoRecord | None:
        candidates = [promo for promo in self.promos if _norm_coin(promo.coin) == _norm_coin(quote.coin)]
        if not candidates:
            return None

        def score(promo: PromoRecord) -> float:
            dist_coin = abs(promo.coin_amount - quote.coin_amount) / max(quote.coin_amount, 1e-6)
            dist_pay = abs(promo.pay_before - quote.rub_amount) / max(quote.rub_amount, 1.0)
            return dist_coin + dist_pay

        return min(candidates, key=score)

    def order_template_for_coin(self, coin: str) -> dict[str, Any] | None:
        coin_norm = _norm_coin(coin)
        candidates = [row for row in self.order_templates if _norm_coin(str(row.get("coin", ""))) == coin_norm]
        if not candidates:
            return self.order_templates[0] if self.order_templates else None
        # Prefer templates with full action set.
        candidates.sort(key=lambda row: len(row.get("buttons") or []), reverse=True)
        return candidates[0]
