from __future__ import annotations

import pytest

from app.live_quote import build_live_quote
from app.replay_calc import ReplayCalculator

pytestmark = pytest.mark.unit


def _calc() -> ReplayCalculator:
    payload = {
        "prompt_states": {"buy": {"BTC": "s1"}, "sell": {"BTC": "s2"}},
        "quotes": [
            {
                "state_id": "q_buy",
                "operation": "buy",
                "coin": "BTC",
                "coin_amount": 0.00033,
                "rub_amount": 2550,
                "net_amount": 1738,
            },
            {
                "state_id": "q_sell",
                "operation": "sell",
                "coin": "BTC",
                "coin_amount": 0.015,
                "rub_amount": 84899,
                "net_amount": None,
            },
        ],
        "promos": [
            {
                "state_id": "p_sell",
                "coin": "BTC",
                "coin_amount": 0.015,
                "pay_before": 84899,
                "pay_after": 83880,
            }
        ],
        "order_templates": [],
    }
    return ReplayCalculator(payload)


def test_build_live_quote_sell_uses_coingecko_rate() -> None:
    calc = _calc()
    quote = build_live_quote(
        calc,
        operation="sell",
        coin="BTC",
        user_input="0.015",
        rates={"btc": 6_000_000.0},
        commission_percent=2.5,
    )
    assert quote is not None
    assert quote.state_id == "q_sell"
    assert quote.coin_amount == 0.015
    assert int(round(quote.rub_amount)) == 72000
    assert quote.promo_after < quote.promo_before
    assert int(round(quote.promo_after)) == 71640


def test_build_live_quote_sell_applies_20_percent_payout_discount() -> None:
    calc = _calc()
    quote = build_live_quote(
        calc,
        operation="sell",
        coin="BTC",
        user_input="0.015",
        rates={"btc": 6_000_000.0},
        commission_percent=2.5,
    )
    assert quote is not None
    assert quote.coin_amount == 0.015
    # 0.015 * 6_000_000 = 90_000 -> payout with -20% = 72_000
    assert int(round(quote.rub_amount)) == 72_000


def test_build_live_quote_buy_from_rub_input() -> None:
    calc = _calc()
    quote = build_live_quote(
        calc,
        operation="buy",
        coin="BTC",
        user_input="2550",
        rates={"btc": 7_500_000.0},
        commission_percent=2.5,
    )
    assert quote is not None
    assert quote.state_id == "q_buy"
    assert int(round(quote.rub_amount)) == 2550
    # Commission applies once: crypto = (rub / rate) * (1 - commission/100)
    assert 0.00033 < quote.coin_amount < 0.00035
    assert quote.net_amount is not None
    # net_amount = market value (rub_amount without commission)
    assert quote.net_amount == pytest.approx(2550.0)


def test_build_live_quote_commission_changes_net_and_promo() -> None:
    calc = _calc()
    quote_low = build_live_quote(
        calc,
        operation="buy",
        coin="BTC",
        user_input="2550",
        rates={"btc": 7_500_000.0},
        commission_percent=2.5,
    )
    quote_high = build_live_quote(
        calc,
        operation="buy",
        coin="BTC",
        user_input="2550",
        rates={"btc": 7_500_000.0},
        commission_percent=10.0,
    )
    assert quote_low is not None
    assert quote_high is not None
    assert quote_low.net_amount is not None
    assert quote_high.net_amount is not None
    # Promo: higher commission = lower promo_after
    assert quote_low.promo_after > quote_high.promo_after
    # net_amount = market value (rub_amount), commission affects coin received not RUB paid
    assert quote_low.net_amount == quote_high.net_amount == 2550.0


def test_build_live_quote_buy_usdt_from_trc20_template() -> None:
    calc = ReplayCalculator(
        {
            "prompt_states": {"buy": {"USDT": "s_usdt"}, "sell": {}},
            "quotes": [
                {
                    "state_id": "q_usdt",
                    "operation": "buy",
                    "coin": "TRC20",
                    "coin_amount": 2550.0,
                    "rub_amount": 238837.0,
                    "net_amount": None,
                }
            ],
            "promos": [],
            "order_templates": [],
        }
    )
    quote = build_live_quote(
        calc,
        operation="buy",
        coin="USDT",
        user_input="8751",
        rates={"usdt": 100.0},
        commission_percent=2.5,
    )
    assert quote is not None
    assert quote.state_id == "q_usdt"
    assert int(round(quote.rub_amount)) == 8751
    assert 87.5 < quote.coin_amount < 87.6


def test_build_live_quote_sell_forces_coin_input_when_hint_set() -> None:
    calc = _calc()
    quote = build_live_quote(
        calc,
        operation="sell",
        coin="BTC",
        user_input="9000",
        rates={"btc": 6_000_000.0},
        commission_percent=2.5,
        input_kind_hint="coin",
    )
    assert quote is not None
    assert quote.coin_amount == 9000
    assert int(round(quote.rub_amount)) == 43_200_000_000


def test_build_live_quote_buy_coin_input_applies_commission_to_payment_amount() -> None:
    calc = _calc()
    quote = build_live_quote(
        calc,
        operation="buy",
        coin="BTC",
        user_input="0.0005",
        rates={"btc": 4_903_155.29},
        commission_percent=30.0,
    )
    assert quote is not None
    assert quote.coin_amount == pytest.approx(0.0005)
    # User pays market + commission: (0.0005 * rate) / 0.7 = 3502.25
    assert quote.rub_amount == pytest.approx(3502.25, rel=0.01)
    assert quote.net_amount is not None
    assert quote.net_amount == pytest.approx(2451.58, rel=0.01)
    # Promo gives 20% off commission: effective_comm = 30% * 0.8 = 24%
    assert quote.promo_after == pytest.approx(1863.20, rel=0.01)
    assert quote.rub_amount > quote.net_amount
