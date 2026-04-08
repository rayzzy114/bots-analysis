from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .models import QuoteRecord
from .replay_calc import ReplayCalculator

NUMBER_RE = re.compile(r"[-+]?\d[\d\s.,]*")

COIN_RATE_KEYS: dict[str, str] = {
    "BTC": "btc",
    "LTC": "ltc",
    "XMR": "xmr",
    "USDT": "usdt",
    "TRX": "trx",
    "ETH": "eth",
    "SOL": "sol",
}

COIN_LABELS: dict[str, str] = {
    "BTC": "Bitcoin",
    "LTC": "Litecoin",
    "XMR": "Monero(XMR)",
    "USDT": "USDT(trc20)",
    "TRX": "Tron(TRX)",
    "ETH": "Ethereum",
    "SOL": "Solana",
}

SELL_PAYOUT_RATIO = 0.8


def parse_amount(value: str) -> float | None:
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
        parsed = float(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def fmt_coin(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")


def fmt_rub(value: float) -> str:
    return str(int(round(value)))


@dataclass(frozen=True)
class LiveQuote:
    state_id: str
    operation: str
    coin: str
    coin_amount: float
    rub_amount: float
    net_amount: float | None
    promo_before: float
    promo_after: float

    @property
    def coin_label(self) -> str:
        return COIN_LABELS.get(self.coin, self.coin)

    def quote_text(self) -> str:
        if self.operation == "buy":
            lines = [
                f"Сумма к получению: {fmt_coin(self.coin_amount)} {self.coin_label}",
                f"Сумма к оплате: {fmt_rub(self.rub_amount)} ₽",
            ]
            if self.net_amount is not None:
                lines.append(f"Сумма к зачислению: {fmt_rub(self.net_amount)} ₽")
            return "\n".join(lines)
        return (
            f"Сумма к получению: {fmt_rub(self.rub_amount)} ₽\n"
            f"Сумма к оплате: {fmt_coin(self.coin_amount)} {self.coin.lower()}"
        )

    def promo_text_html(self) -> str:
        return (
            f"<strong>🕹Ты покупаешь {self.coin_label}</strong>: {fmt_coin(self.coin_amount)}\n"
            f"<strong>Тебе нужно будет оплатить</strong>: "
            f"<del>{fmt_rub(self.promo_before)}</del> {fmt_rub(self.promo_after)}\n"
            "🔥 Я дарю тебе промокод: <strong>PERVAYA_SDELKA</strong>, по которому будет скидка 20% от комиссии\n\n"
            "👨‍🔧 <strong>Хочешь применить промо</strong> как скидку?"
        )

    def promo_text_plain(self) -> str:
        return (
            f"🕹Ты покупаешь {self.coin_label}: {fmt_coin(self.coin_amount)}\n"
            f"Тебе нужно будет оплатить: {fmt_rub(self.promo_before)} {fmt_rub(self.promo_after)}\n"
            "🔥 Я дарю тебе промокод: PERVAYA_SDELKA, по которому будет скидка 20% от комиссии\n\n"
            "👨‍🔧 Хочешь применить промо как скидку?"
        )


def _choose_input_kind(template: QuoteRecord, amount: float) -> str:
    dist_coin = abs(amount - template.coin_amount) / max(template.coin_amount, 1e-6)
    dist_rub = abs(amount - template.rub_amount) / max(template.rub_amount, 1.0)
    return "coin" if dist_coin <= dist_rub else "rub"


def _fallback_rate(coin: str, template: QuoteRecord) -> float:
    if template.coin_amount <= 0:
        return 0.0
    return template.rub_amount / template.coin_amount


def build_live_quote(
    calc: ReplayCalculator,
    *,
    operation: str,
    coin: str,
    user_input: str,
    rates: dict[str, float],
    commission_percent: float,
    input_kind_hint: Literal["coin", "rub"] | None = None,
) -> LiveQuote | None:
    template = calc.nearest_quote(operation, coin, user_input)
    if not template:
        return None
    amount = parse_amount(user_input)
    if amount is None:
        return None

    rate_key = COIN_RATE_KEYS.get(coin, coin.lower())
    rate = float(rates.get(rate_key) or 0.0)
    if rate <= 0:
        rate = _fallback_rate(coin, template)
    if rate <= 0:
        return None

    input_kind = input_kind_hint if input_kind_hint in {"coin", "rub"} else _choose_input_kind(template, amount)
    commission_multiplier = 1.0 + (commission_percent / 100.0)
    applies_commission = operation == "buy" and template.net_amount is not None
    if operation == "buy":
        if input_kind == "coin":
            coin_amount = amount
            base_rub_amount = coin_amount * rate
            if applies_commission:
                rub_amount = base_rub_amount * commission_multiplier
            else:
                rub_amount = base_rub_amount
        else:
            rub_amount = amount
            if applies_commission:
                coin_amount = rub_amount / (rate * commission_multiplier)
            else:
                coin_amount = rub_amount / rate
        net_amount = rub_amount / commission_multiplier if applies_commission else None
    else:
        if input_kind == "coin":
            coin_amount = amount
            rub_amount = coin_amount * rate * SELL_PAYOUT_RATIO
        else:
            rub_amount = amount
            coin_amount = rub_amount / (rate * SELL_PAYOUT_RATIO) if rate > 0 else 0.0

        net_amount = None
        if template.net_amount is not None:
            net_amount = rub_amount * SELL_PAYOUT_RATIO

    # Promo gives 20% discount FROM commission (effective_commission = commission * 0.8).
    # For BUY: user pays base_amount * (1 + commission%). With promo: base_amount * (1 + commission% * 0.8)
    promo_before = rub_amount
    if operation == "buy" and applies_commission:
        # Calculate base amount without commission, then apply reduced commission
        base_amount = rub_amount / commission_multiplier
        reduced_commission = commission_percent * 0.8
        promo_after = base_amount * (1.0 + reduced_commission / 100.0)
    else:
        # For operations without commission or SELL, apply discount to total
        promo_ratio = max(0.0, 1.0 - (commission_percent * 0.8) / 100.0)
        promo_after = promo_before * promo_ratio

    return LiveQuote(
        state_id=template.state_id,
        operation=operation,
        coin=coin,
        coin_amount=coin_amount,
        rub_amount=rub_amount,
        net_amount=net_amount,
        promo_before=promo_before,
        promo_after=promo_after,
    )
