"""Helpers for interpreting user-entered amounts."""


def parse_amount_value(raw_value: str | None) -> tuple[float, bool]:
    """Return (amount, is_crypto) where presence of '.' means crypto."""
    if raw_value is None:
        raise ValueError("Amount is missing")
    clean = raw_value.replace(",", ".").strip()
    is_crypto = "." in clean
    amount = float(clean)
    return amount, is_crypto
