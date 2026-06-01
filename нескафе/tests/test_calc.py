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


def test_commission_adds_to_payable_not_coin():
    # комиссия — наценка на «к оплате» (клиент платит больше), монета — чистая
    from app.calc import build_quote
    full = build_quote("ltc", 50000, rate=100, commission_percent=0, cashback_percent=0.5)
    with_fee = build_quote("ltc", 50000, rate=100, commission_percent=5, cashback_percent=0.5)
    assert full.coin_amount == pytest.approx(500.0)      # к получению не меняется
    assert with_fee.coin_amount == pytest.approx(500.0)  # монета та же при любой комиссии
    assert full.payable == pytest.approx(50000)          # без комиссии — базовая сумма
    assert with_fee.payable == pytest.approx(52500)      # 5% наценка на «к оплате»


def test_build_quote_discount_reduces_payable():
    # модель оригинала: скидка («списать монеты») режет «к оплате», не монету.
    from app.calc import build_quote
    q = build_quote("ltc", 15104, rate=15104 / 3, commission_percent=0,
                    cashback_percent=0.5, discount=50)
    assert q.coin_amount == pytest.approx(3.0)   # к получению не меняется скидкой
    assert q.payable == pytest.approx(15054)     # к оплате = 15104 − 50
    assert q.cashback == 76                       # кэшбэк на pre-discount 15104


def test_rub_mode_commission_cuts_coin_not_payable():
    # RUB-режим: «к оплате» = ровно введённое, комиссия вычитается из монеты (битка)
    from app.calc import build_quote
    q = build_quote("btc", 5000, rate=5_000_000, commission_percent=20,
                    cashback_percent=0.5, discount=0, unit="rub")
    assert q.payable == pytest.approx(5000)                      # платит ровно 5000
    assert q.coin_amount == pytest.approx(4000 / 5_000_000)      # 5000·0.8/курс
    assert q.cashback == 25                                      # 0.5% от 5000


def test_coin_mode_commission_adds_to_payable():
    # COIN-режим: получает ровно монету, комиссия наценивает «к оплате»
    from app.calc import build_quote
    q = build_quote("btc", 5000, rate=5_000_000, commission_percent=20,
                    cashback_percent=0.5, discount=0, unit="coin")
    assert q.coin_amount == pytest.approx(5000 / 5_000_000)      # монета чистая
    assert q.payable == pytest.approx(6000)                      # 5000·1.2


def test_commission_is_exactly_n_percent():
    # анти-регресс: комиссия 20% наценивает «к оплате» ровно на 20%, монета — чистая.
    from app.calc import build_quote
    q = build_quote("btc", 1000, rate=100, commission_percent=20,
                    cashback_percent=0.5, discount=0)
    assert q.coin_amount == pytest.approx(10.0)  # 1000 / 100 — без комиссии
    assert q.payable == pytest.approx(1200)      # 1000 * 1.20


def test_burn_does_not_change_coin_for_btc():
    # issue 6: BTC + «списать монеты» — монета считается верно, скидка уходит в оплату.
    from app.calc import build_quote
    rate = 7_000_000
    base = build_quote("btc", 10000, rate=rate, commission_percent=20,
                       cashback_percent=0.5, discount=0)
    burned = build_quote("btc", 10000, rate=rate, commission_percent=20,
                         cashback_percent=0.5, discount=50)
    assert burned.coin_amount == pytest.approx(base.coin_amount)  # монета не меняется
    assert burned.payable == pytest.approx(base.payable - 50)     # оплата меньше на 50


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
