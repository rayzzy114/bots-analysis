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
    rub: float            # «брутто» RUB-эквивалент ввода (до вычета скидки/комиссии)
    coin_amount: float    # «к получению» (монета) — чистая конвертация rub/курс
    cashback: int
    discount: int = 0
    payable: float = 0.0  # «к оплате» — см. build_quote (зависит от режима ввода)


def cashback_for(rub: float, cashback_percent: float) -> int:
    """Кэшбэк = cashback_percent% от RUB-суммы, округление ВВЕРХ.

    Примеры из записи (clone_spec §4) совпадают с ceil, а не floor:
    50000→250, 5000→25, 90000→450, 15104→76, 88434→443.
    Считается на pre-discount RUB (LTC: 15104→кэшбэк 76 при скидке 50).
    """
    return int(math.ceil(rub * cashback_percent / 100.0))


def coin_received(rub: float, rate: float) -> float:
    """Сумма к получению в монете = RUB / курс — чистая конвертация.

    Комиссия монету НЕ трогает (решение пользователя — она режет «к оплате»).
    Скидка (бонусы) на «к получению» тоже не влияет.
    """
    if rate <= 0:
        return 0.0
    return rub / rate


def build_quote(
    coin: str, rub: float, rate: float, commission_percent: float,
    cashback_percent: float, discount: int = 0, unit: str = "coin",
) -> Quote:
    """Расчёт сумм. Комиссия «съедает» ту сторону, которую пользователь НЕ вводил.

    rub — брутто RUB-эквивалент ввода (в COIN-режиме = монета×курс, в RUB-режиме = рубли).
      • COIN-режим (ввёл монету): получает ровно монету, комиссия НАЦЕНИВАЕТ «к оплате»
          к получению = rub/курс;  к оплате = rub·(1+комиссия%) − discount
      • RUB-режим (ввёл рубли): платит ровно введённое, комиссия ВЫЧИТАЕТСЯ из монеты
          к получению = rub·(1−комиссия%)/курс;  к оплате = rub − discount
      • кэшбэк = ⌈«к оплате до скидки»·кэшбэк%⌉ — как в оригинале (0.5% от суммы оплаты).
    """
    c = commission_percent / 100.0
    if unit == "rub":
        coin_amount = (rub * (1 - c)) / rate if rate > 0 else 0.0
        payable_gross = rub
    else:
        coin_amount = coin_received(rub, rate)
        payable_gross = rub * (1 + c)
    return Quote(
        coin=coin,
        rub=rub,
        coin_amount=coin_amount,
        cashback=cashback_for(payable_gross, cashback_percent),
        discount=discount,
        payable=max(0.0, payable_gross - discount),
    )


def render_calc(data: dict, settings) -> tuple[str, object]:
    """Текст + клавиатура калькулятора по текущему состоянию FSM-data."""
    from . import constants as const
    from . import keyboards as kb
    from . import renderer, texts

    coin = data["coin"]
    rate = float(data.get("rate", 0))
    gross_rub = float(data.get("rub", 0))   # брутто RUB-эквивалент ввода
    burn = bool(data.get("burn", False))
    mode = data.get("mode", "default")
    unit = data.get("unit", "coin")
    min_rub = settings.min_rub(coin)
    bonus = int(data.get("bonus_available", settings.start_bonus))

    discount = bonus if burn else 0
    if gross_rub > 0:
        # Авторасчёт с комиссией: «к получению» = монета 1:1 (чистая конвертация),
        # «к оплате» уже включает наценку-комиссию, как в оригинале (0.0005 BTC → 3522 RUB).
        # Скидка («списать монеты») режет «к оплате».
        quote = build_quote(coin, gross_rub, rate, settings.commission_percent,
                            cashback_percent=settings.cashback_percent, discount=discount,
                            unit=unit)
        cashback = quote.cashback
        coin_amount = renderer.fmt_coin(quote.coin_amount, coin)
        payable_str = renderer.fmt_rub_space(quote.payable)
    else:
        cashback = 0
        coin_amount = "_"
        payable_str = "0"

    text = renderer.render(
        texts.CALC_BODY, settings,
        coin_emoji=const.COINS[coin]["emoji"], coin_amount=coin_amount,
        ticker=const.COINS[coin]["ticker"], rub=payable_str, cashback=cashback, discount=discount,
    )
    if mode == "pad":
        markup = kb.kb_calc_pad(coin, burn, unit)
    else:
        markup = kb.kb_calc_default(coin, str(int(min_rub)), burn, bonus, unit)
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
