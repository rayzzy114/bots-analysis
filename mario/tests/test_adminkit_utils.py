from __future__ import annotations

import pytest

from app.adminkit.utils import parse_amount

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 0.0),
        ("2,5", 2.5),
        ("2.5", 2.5),
        ("2,5%", 2.5),
        ("1 234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1.234,56", 1234.56),
    ],
)
def test_parse_amount_accepts_valid_formats(raw: str, expected: float) -> None:
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "-1",
        "- 1",
        "−1",
        "—1",
        "abc",
        "1.2.3",
    ],
)
def test_parse_amount_rejects_invalid_formats(raw: str) -> None:
    assert parse_amount(raw) is None
