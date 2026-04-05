from __future__ import annotations

from io import BytesIO

from PIL import Image

from app.storage import build_wallet_qr_png_bytes


def test_wallet_qr_bytes_are_png_and_change_with_wallet() -> None:
    first_wallet = "bc1qfirstwallet000000000000000000000000000000000000000"
    second_wallet = "bc1qsecondwallet00000000000000000000000000000000000000"

    first = build_wallet_qr_png_bytes(first_wallet)
    second = build_wallet_qr_png_bytes(second_wallet)

    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    assert second.startswith(b"\x89PNG\r\n\x1a\n")
    assert first != second

    first_image = Image.open(BytesIO(first))
    second_image = Image.open(BytesIO(second))
    assert first_image.size == (250, 250)
    assert second_image.size == (250, 250)
