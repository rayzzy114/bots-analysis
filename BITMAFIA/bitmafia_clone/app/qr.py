from __future__ import annotations

from pathlib import Path

import qrcode

CRYPTO_QR_KEYS = {"btc", "ltc", "usdt_trc20", "usdt_bsc", "eth", "trx", "xmr", "ton"}


def qr_dir(project_dir: Path) -> Path:
    return project_dir / "data" / "admin" / "qr"


def qr_path(project_dir: Path, wallet_key: str) -> Path:
    return qr_dir(project_dir) / f"{wallet_key}.png"


def generate_wallet_qr(project_dir: Path, wallet_key: str, wallet_value: str) -> Path | None:
    key = (wallet_key or "").strip().lower()
    value = (wallet_value or "").strip()
    if key not in CRYPTO_QR_KEYS or not value:
        return None

    out = qr_path(project_dir, key)
    out.parent.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(out)
    return out
