"""Динамика сумм (clone_spec §4): кэшбэк, пример, парсер ввода."""

import pytest

from app.calc import cashback_for, coin_received, parse_amount
from app.rates import calc_example


@pytest.mark.parametrize("rub,expected", [
    (50000, 250), (5000, 25), (90000, 450), (15104, 76), (88434, 443),
])
def test_cashback_floor_half_percent(rub, expected):
    assert cashback_for(rub, 0.5) == expected


def test_coin_received():
    # 50 000 ₽ / курс → ~0.00698 BTC (без комиссии)
    rate = 50000 / 0.00698021
    assert round(coin_received(50000, rate), 8) == pytest.approx(0.00698021, abs=1e-8)


def test_commission_reduces_payout():
    # комиссия 5% уменьшает сумму к получению
    full = coin_received(50000, rate=100, commission_percent=0)
    with_fee = coin_received(50000, rate=100, commission_percent=5)
    assert full == pytest.approx(500.0)
    assert with_fee == pytest.approx(475.0)


def test_build_quote_discount_adds_back():
    from app.calc import build_quote
    q = build_quote("ltc", 50000, rate=100, commission_percent=5,
                    cashback_percent=0.5, discount=50)
    # effective = 50000*0.95 + 50 = 47550 → /100 = 475.5
    assert q.coin_amount == pytest.approx(475.5)


def test_calc_example_always_passes_min():
    # пример в монете * курс >= минимума
    for min_rub, rate in [(795, 7_160_000), (728, 9_700), (48670, 95), (54000, 24_000)]:
        ex = calc_example(min_rub, rate)
        assert float(ex) * rate >= min_rub


def test_parse_decimal_is_coin():
    rub, basis = parse_amount("0.5", "btc", rate=7_000_000, min_rub=795)
    assert basis == "coin"
    assert rub == pytest.approx(3_500_000)


def test_parse_btc_whole_is_rub():
    rub, basis = parse_amount("50000", "btc", rate=7_000_000, min_rub=795)
    assert basis == "rub"
    assert rub == 50000


def test_parse_ltc_small_whole_is_coin():
    # 3 LTC (< min 728) → монета
    rub, basis = parse_amount("3", "ltc", rate=5018, min_rub=728)
    assert basis == "coin"
    assert rub == pytest.approx(3 * 5018)


def test_parse_ltc_large_whole_is_rub():
    rub, basis = parse_amount("15000", "ltc", rate=5018, min_rub=728)
    assert basis == "rub"
    assert rub == 15000


def test_parse_rejects_garbage():
    assert parse_amount("abc", "btc", rate=1, min_rub=1) is None
