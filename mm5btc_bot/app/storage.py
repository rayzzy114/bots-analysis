from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any

import qrcode
from PIL import Image


QR_TARGET_SIZE = 250


def build_wallet_qr_png_bytes(wallet: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(wallet.strip())
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white").convert("L")
    if image.size != (QR_TARGET_SIZE, QR_TARGET_SIZE):
        image = image.resize((QR_TARGET_SIZE, QR_TARGET_SIZE), Image.Resampling.NEAREST)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class JsonStore:
    def __init__(self, path: Path, defaults: dict[str, Any]):
        self.path = path
        self.defaults = defaults
        self.lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2), encoding="utf-8")

    def read(self) -> dict[str, Any]:
        with self.lock:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            merged = {**self.defaults, **(data if isinstance(data, dict) else {})}
            return merged

    def write(self, data: dict[str, Any]) -> None:
        with self.lock:
            self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class SettingsStore:
    def __init__(self, path: Path):
        self.store = JsonStore(
            path,
            {
                "fee_percent": 4.5,
                "fee_fixed_btc": 0.0007,
                "deposit_btc_address": "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7",
                "site_url": "https://mixermoney.it.com",
                "tor_url": "http://mixereztksljzma2owmv6hmsrci322lsje6m3svicoddk3xbgvhd2fid.onion/",
                "order_min_btc": 0.003,
                "order_max_btc": 50.0,
            },
        )

    def get(self) -> dict[str, Any]:
        return self.store.read()

    def set_fee(self, value: float) -> None:
        data = self.store.read()
        data["fee_percent"] = float(value)
        self.store.write(data)

    def set_deposit_address(self, wallet: str) -> None:
        data = self.store.read()
        data["deposit_btc_address"] = wallet.strip()
        self.store.write(data)

    def set_site_url(self, url: str) -> None:
        data = self.store.read()
        data["site_url"] = url.strip()
        self.store.write(data)

    def set_tor_url(self, url: str) -> None:
        data = self.store.read()
        data["tor_url"] = url.strip()
        self.store.write(data)


def calc_mixer_fee(deposit_btc: float, fee_percent: float, fee_fixed_btc: float) -> tuple[float, float]:
    """
    Calculate mixer fee and net BTC to receive.

    For a Bitcoin mixer:
    - User deposits X BTC
    - Fee = (X * fee_percent / 100) + fee_fixed_btc
    - User receives X - Fee BTC

    Returns (fee_amount, net_btc_to_receive).
    """
    percent_fee = deposit_btc * (fee_percent / 100)
    total_fee = percent_fee + fee_fixed_btc
    net_btc = deposit_btc - total_fee
    return total_fee, max(net_btc, 0)


class RuntimeStore:
    def __init__(self, path: Path):
        self.store = JsonStore(path, {"next_order_id": 24})

    def next_order_id(self) -> int:
        data = self.store.read()
        current = int(data.get("next_order_id", 24))
        data["next_order_id"] = current + 1
        self.store.write(data)
        return current
