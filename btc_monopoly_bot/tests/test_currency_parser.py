import pytest

from app.utils import parse_amount


@pytest.mark.parametrize("raw, expected_value", [
    ("1000", 1000.0),
    ("1.000,50", 1000.50),
    ("1,000.50", 1000.50),
])
def test_parse_amount(raw, expected_value):
    result = parse_amount(raw)
    assert result == expected_value
