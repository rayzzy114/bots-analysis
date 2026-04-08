import pytest
from core.utils import CurrencyParser

def test_currency_parser_valid_btc():
    res = CurrencyParser.parse("100 BTC")
    assert res.is_valid
    assert res.amount == 100.0
    assert res.currency == "BTC"

def test_currency_parser_valid_rub_decimal():
    res = CurrencyParser.parse("1000,5 RUB")
    assert res.is_valid
    assert res.amount == 1000.5
    assert res.currency == "RUB"

def test_currency_parser_invalid_format():
    res = CurrencyParser.parse("invalid")
    assert not res.is_valid
    assert "Неверный формат" in res.error

def test_currency_parser_negative_amount():
    res = CurrencyParser.parse("-10 BTC")
    assert not res.is_valid
    assert "больше нуля" in res.error

def test_currency_parser_zero_amount():
    res = CurrencyParser.parse("0 BTC")
    assert not res.is_valid
    assert "больше нуля" in res.error
