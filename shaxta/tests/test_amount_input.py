import unittest

from utils.amount_input import parse_amount_value


class TestAmountInput(unittest.TestCase):
    def test_dot_means_crypto(self) -> None:
        amount, is_crypto = parse_amount_value("0.001")
        self.assertEqual(amount, 0.001)
        self.assertTrue(is_crypto)

    def test_no_dot_means_rub(self) -> None:
        amount, is_crypto = parse_amount_value("1500")
        self.assertEqual(amount, 1500.0)
        self.assertFalse(is_crypto)

    def test_comma_is_normalized_to_dot(self) -> None:
        amount, is_crypto = parse_amount_value("0,01")
        self.assertEqual(amount, 0.01)
        self.assertTrue(is_crypto)
