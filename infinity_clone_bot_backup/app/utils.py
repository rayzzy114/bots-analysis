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


def parse_amount(raw: str) -> float:
    clean = re.sub(r'[^0-9,.]', '', raw)
    if ',' in clean and '.' in clean:
        if clean.rfind(',') > clean.rfind('.'):
            clean = clean.replace('.', '').replace(',', '.')
        else:
            clean = clean.replace(',', '')
    elif ',' in clean:
        clean = clean.replace(',', '.')
    return float(clean)


def fmt_coin(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")
