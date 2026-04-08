"""Tests: crypto address validation."""
from __future__ import annotations

import pytest

from app.runtime import _is_valid_address_for_currency, _is_valid_crypto_address


class TestAddressValidation:
    @pytest.mark.parametrize("addr", [
        "bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2",  # BTC bech32
        "bc1qgure5hwehsa9f5p7t92y3z72c5hqq4txlq5px7",
        "1BpEi6DfDAUFd153wiGrvkiooLksmXX3L",  # BTC legacy
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",  # BTC P2SH
        "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe",  # ETH
        "0xAbCd1234567890abcdef1234567890abcdef1234",  # ETH variant
        "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",  # TRX
        "LcSZ2F3Q9sJMXHYGp3Qx9Y2ARhpKF5d1B",  # LTC
    ])
    def test_valid_addresses_accepted(self, addr: str):
        assert _is_valid_crypto_address(addr), f"Should accept: {addr}"

    @pytest.mark.parametrize("text", [
        "hello world",
        "привет",
        "1234",
        "not_an_address",
        "",
        "12345",
        "abc def",
    ])
    def test_invalid_input_rejected(self, text: str):
        assert not _is_valid_crypto_address(text), f"Should reject: {text!r}"

    def test_address_embedded_in_text_detected(self):
        text = "Мой адрес: bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2 пожалуйста"
        assert _is_valid_crypto_address(text)

    def test_short_string_rejected(self):
        assert not _is_valid_crypto_address("bc1short")

    @pytest.mark.parametrize(
        ("currency_title", "addr"),
        [
            ("Чистые BTC", "bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2"),
            ("Ethereum", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"),
            ("Tether ERC-20", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"),
            ("Tether TRC-20", "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"),
            ("Litecoin", "LcSZ2F3Q9sJMXHYGp3Qx9Y2ARhpKF5d1B"),
            (
                "Monero",
                "47Kv7Szy7ePGBgoYtfXCEH2R4peJsmNfEhD8zQ1sEgBRNiN5Xmt"
                "6bp8W96nUZ9Ea1cXrkA2hkESxkSKuJMzH9qkNDHwaLU4",
            ),
        ],
    )
    def test_currency_specific_addresses_accepted(self, currency_title: str, addr: str):
        assert _is_valid_address_for_currency(currency_title, addr)

    @pytest.mark.parametrize(
        ("currency_title", "wrong_addr"),
        [
            ("Tether TRC-20", "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"),
            ("Ethereum", "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"),
            ("Litecoin", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"),
            (
                "Monero",
                "LcSZ2F3Q9sJMXHYGp3Qx9Y2ARhpKF5d1B",
            ),
        ],
    )
    def test_currency_specific_addresses_reject_wrong_network(self, currency_title: str, wrong_addr: str):
        assert not _is_valid_address_for_currency(currency_title, wrong_addr)
