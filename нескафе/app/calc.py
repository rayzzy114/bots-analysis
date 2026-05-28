"""Расчёт сумм обмена и парсинг ввода (clone_spec.md §4).

- Кэшбэк = cashback_percent% от RUB-суммы, округление вниз.
- «К получению» (монета) = RUB / курс.
- Парсер ввода различает монету/рубли по наличию десятичного разделителя и
  эвристике по величине (см. parse_amount).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Quote:
    coin: str
    rub: float
    coin_amount: float
    cashback: int
    discount: int = 0


def cashback_for(rub: float, cashback_percent: float) -> int:
    """Кэшбэк = cashback_percent% от RUB-суммы, округление ВВЕРХ.

    Примеры из записи (clone_spec §4) совпадают с ceil, а не floor:
    50000→250, 5000→25, 90000→450, 15104→76, 88434→443.
    """
    return int(math.ceil(rub * cashback_percent / 100.0))


def coin_received(rub: float, rate: float, commission_percent: float = 0.0) -> float:
    """Сумма к получению в монете.

    Комиссия сервиса уменьшает выдаваемую сумму: пользователь платит `rub`,
    а получает монету за вычетом комиссии по рыночному курсу.
    Скидка (списанные бонусы) увеличивает эффективную сумму обратно.
    """
    if rate <= 0:
        return 0.0
    effective_rub = rub * (1 - commission_percent / 100.0)
    return effective_rub / rate


def build_quote(
    coin: str, rub: float, rate: float, commission_percent: float,
    cashback_percent: float, discount: int = 0,
) -> Quote:
    # скидка (бонусы) компенсирует часть комиссии: добавляем её обратно к сумме
    effective_rub = rub * (1 - commission_percent / 100.0) + discount
    return Quote(
        coin=coin,
        rub=rub,
        coin_amount=effective_rub / rate if rate > 0 else 0.0,
        cashback=cashback_for(rub, cashback_percent),
        discount=discount,
    )


def render_calc(data: dict, settings) -> tuple[str, object]:
    """Текст + клавиатура калькулятора по текущему состоянию FSM-data."""
    from . import constants as const
    from . import keyboards as kb
    from . import renderer, texts

    coin = data["coin"]
    rate = float(data.get("rate", 0))
    rub = float(data.get("rub", 0))
    burn = bool(data.get("burn", False))
    mode = data.get("mode", "default")
    min_rub = settings.min_rub(coin)

    discount = int(data.get("bonus_available", settings.start_bonus)) if burn else 0
    if rub > 0:
        quote = build_quote(coin, rub, rate, settings.commission_percent,
                            settings.cashback_percent, discount)
        cashback = quote.cashback
        coin_amount = renderer.fmt_coin(quote.coin_amount)
    else:
        cashback = 0
        coin_amount = "_"
    rub_str = renderer.fmt_rub_space(rub) if rub > 0 else "0"

    text = renderer.render(
        texts.CALC_BODY, settings,
        coin_emoji=const.COINS[coin]["emoji"], coin_amount=coin_amount,
        ticker=const.COINS[coin]["ticker"], rub=rub_str, cashback=cashback, discount=discount,
    )
    if mode == "pad":
        markup = kb.kb_calc_pad(coin)
    else:
        markup = kb.kb_calc_default(coin, str(int(min_rub)), burn)
    return text, markup


def parse_amount(text: str, coin: str, rate: float, min_rub: float) -> tuple[float, str] | None:
    """Парсит ввод пользователя в RUB.

    Возвращает (rub, basis) где basis ∈ {"rub","coin"}, или None если не число.
    Эвристика (§4):
      - любой ввод с '.'/',' → монета;
      - BTC: целое → RUB, дробное → монета;
      - LTC/XMR/USDT: целое < min → монета, ≥ min → RUB.
    """
    raw = text.strip().replace(" ", "")
    is_decimal = ("." in raw) or ("," in raw)
    raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0:
        return None

    if is_decimal:
        # дробь всегда трактуется как монета
        return value * rate, "coin"

    # целое число
    if coin == "btc":
        # у BTC целое — это рубли (0.00x — монета, но это уже дробь)
        return value, "rub"
    # LTC/XMR/USDT
    if value < min_rub:
        return value * rate, "coin"
    return value, "rub"
