from __future__ import annotations

import pytest

from app.replay_calc import ReplayCalculator

pytestmark = pytest.mark.unit


def test_nearest_quote_and_promo_selection() -> None:
    payload = {
        "prompt_states": {"buy": {"BTC": "s1"}, "sell": {"BTC": "s2"}},
        "quotes": [
            {
                "state_id": "q1",
                "operation": "buy",
                "coin": "BTC",
                "coin_amount": 0.001,
                "rub_amount": 8000,
                "net_amount": 5000,
            },
            {
                "state_id": "q2",
                "operation": "buy",
                "coin": "BTC",
                "coin_amount": 0.002,
                "rub_amount": 16000,
                "net_amount": 10000,
            },
        ],
        "promos": [
            {
                "state_id": "p1",
                "coin": "BTC",
                "coin_amount": 0.001,
                "pay_before": 8000,
                "pay_after": 7800,
            },
            {
                "state_id": "p2",
                "coin": "BTC",
                "coin_amount": 0.002,
                "pay_before": 16000,
                "pay_after": 15600,
            },
        ],
        "order_templates": [],
    }

    calc = ReplayCalculator(payload)
    quote = calc.nearest_quote("buy", "BTC", "8100")
    assert quote is not None
    assert quote.state_id == "q1"

    promo = calc.promo_for_quote(quote)
    assert promo is not None
    assert promo.state_id == "p1"


def test_nearest_quote_maps_trc20_to_usdt() -> None:
    payload = {
        "prompt_states": {"buy": {"USDT": "s1"}, "sell": {}},
        "quotes": [
            {
                "state_id": "q_usdt",
                "operation": "buy",
                "coin": "TRC20",
                "coin_amount": 100.0,
                "rub_amount": 8751.0,
                "net_amount": None,
            }
        ],
        "promos": [],
        "order_templates": [],
    }

    calc = ReplayCalculator(payload)
    quote = calc.nearest_quote("buy", "USDT", "100")
    assert quote is not None
    assert quote.state_id == "q_usdt"
