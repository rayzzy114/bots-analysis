import re


def parse_admin_ids(raw: str) -> set[int]:
    out: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.add(int(chunk))
        except ValueError:
            continue
    return out


def parse_amount(raw: str) -> float | None:
    cleaned = raw.strip().replace(" ", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if cleaned.count(".") > 1:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if value <= 0:
        return None
    return value


def detect_mode(raw: str, amount: float) -> str:
    text = raw.lower()
    if any(token in text for token in ("руб", "rub", "rur")):
        return "rub"
    if any(token in text for token in ("btc", "ltc", "usdt")):
        return "coin"
    return "rub" if amount >= 1000 else "coin"


def calc_quote(side: str, amount: float, mode: str, rate: float, commission_percent: float) -> dict[str, float]:
    commission = commission_percent / 100.0
    if side == "buy":
        if mode == "rub":
            # For buy flow we keep market equivalent in coin and apply service commission to payment amount.
            amount_coin = amount / rate
            amount_rub = amount * (1 + commission)
        else:
            amount_coin = amount
            amount_rub = amount_coin * rate * (1 + commission)
    else:
        payout_factor = max(0.01, 1 - commission)
        if mode == "rub":
            amount_rub = amount
            amount_coin = amount_rub / (rate * payout_factor)
        else:
            amount_coin = amount
            amount_rub = amount_coin * rate * payout_factor
    return {"amount_coin": amount_coin, "amount_rub": amount_rub, "rate": rate}


def fmt_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def fmt_coin(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")
