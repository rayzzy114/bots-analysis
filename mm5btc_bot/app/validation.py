from __future__ import annotations

from hashlib import sha256

_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {ch: idx for idx, ch in enumerate(_BASE58_ALPHABET)}

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_INDEX = {ch: idx for idx, ch in enumerate(_BECH32_CHARSET)}
_BECH32_CONST = 1
_BECH32M_CONST = 0x2BC830A3


def _double_sha256(data: bytes) -> bytes:
    return sha256(sha256(data).digest()).digest()


def _decode_base58(value: str) -> bytes | None:
    total = 0
    for char in value:
        digit = _BASE58_INDEX.get(char)
        if digit is None:
            return None
        total = total * 58 + digit

    decoded = total.to_bytes((total.bit_length() + 7) // 8, "big") if total else b""
    leading_zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * leading_zeroes + decoded


def _validate_base58check(value: str) -> bool:
    decoded = _decode_base58(value)
    if decoded is None or len(decoded) < 4:
        return False
    payload, checksum = decoded[:-4], decoded[-4:]
    return _double_sha256(payload)[:4] == checksum


def _bech32_polymod(values: list[int]) -> int:
    generator = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for value in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ value
        for index, item in enumerate(generator):
            if (top >> index) & 1:
                chk ^= item
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(ch) >> 5 for ch in hrp] + [0] + [ord(ch) & 31 for ch in hrp]


def _convertbits(data: list[int], from_bits: int, to_bits: int, pad: bool) -> list[int] | None:
    acc = 0
    bits = 0
    result: list[int] = []
    max_value = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1

    for value in data:
        if value < 0 or value >> from_bits:
            return None
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((acc >> bits) & max_value)

    if pad:
        if bits:
            result.append((acc << (to_bits - bits)) & max_value)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & max_value):
        return None

    return result


def _validate_bech32(value: str) -> bool:
    if not value or len(value) < 8 or len(value) > 90:
        return False
    if value.lower() != value and value.upper() != value:
        return False

    raw = value.lower()
    separator = raw.rfind("1")
    if separator < 1 or separator + 7 > len(raw):
        return False

    hrp = raw[:separator]
    if hrp not in {"bc", "tb"}:
        return False

    data: list[int] = []
    for char in raw[separator + 1 :]:
        digit = _BECH32_INDEX.get(char)
        if digit is None:
            return False
        data.append(digit)

    polymod = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    if polymod == _BECH32_CONST:
        spec = "bech32"
    elif polymod == _BECH32M_CONST:
        spec = "bech32m"
    else:
        return False

    witness = data[:-6]
    if not witness:
        return False

    version = witness[0]
    if version > 16:
        return False

    program = _convertbits(witness[1:], 5, 8, False)
    if program is None:
        return False

    program_len = len(program)
    if version == 0:
        return spec == "bech32" and program_len in {20, 32}
    return spec == "bech32m" and 2 <= program_len <= 40


def is_valid_btc_address(value: str) -> bool:
    raw = value.strip()
    if not raw:
        return False

    lowered = raw.lower()
    if lowered.startswith(("bc1", "tb1")):
        return _validate_bech32(raw)

    if lowered.startswith(("1", "3")):
        return 26 <= len(raw) <= 35 and _validate_base58check(raw)

    return False
