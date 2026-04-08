import pytest
import asyncio
from app.utils import parse_amount

@pytest.mark.parametrize("raw, expected_value, expected_currency", [
    ("1000", 1000.0, None),
    ("1000 руб", 1000.0, "RUB"),
    ("0.01 btc", 0.01, "BTC"),
    ("1.000,50", 1000.50, None),
    ("1,000.50", 1000.50, None),
    ("500 LTC", 500.0, "LTC"),
    ("0,005 eth", 0.005, "ETH"),
    ("INVALID", None, None),
])
def test_parse_amount(raw, expected_value, expected_currency):
    result = parse_amount(raw)
    if expected_value is None:
        assert result is None
    else:
        assert result.value == expected_value
        assert result.currency == expected_currency
