import os

from dotenv import load_dotenv

load_dotenv()


def _parse_int_list(raw: str) -> list[int]:
    values: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            values.append(int(chunk))
        except ValueError:
            continue
    return values


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


TOKEN = _required_env("BOT_TOKEN")

CRYPTO_COSH = {
    "LTC": "ltc1q84a983hllesy2kncpkvyq02r2lvmp5lrn8976c",
    "BTC": "ltc1q84a983hllesy2kncpkvyq02r2lvmp5lrn8976c",
    "USDT-TRC20": "ltc1q84a983hllesy2kncpkvyq02r2lvmp5lrn8976c",
    "XMR": "ltc1q84a983hllesy2kncpkvyq02r2lvmp5lrn8976c",
}
ADMIN_CHAT_IDS = _parse_int_list(_required_env("ADMIN_IDS"))
PAYMENT_FILE = "payment_details.json"
CRYPTO_FILE = "crypto_cosh.json"
CONTACT_FILE = "contact_buttons.json"


PAYMENT_DETAILS = {
    "card": {"bank": "Карта РФ", "requisites": "4276 00XX XXXX XX12"},
    "spb": {"bank": "СПБ", "requisites": "+7 900 123 45 67"},
    "alfa": {"bank": "Альфа-Банк", "requisites": "4081 23XX XXXX XX56"},
    "sber": {"bank": "Сбербанк", "requisites": "5469 38XX XXXX XX89"},
    "ozon": {"bank": "OZON Банк", "requisites": "2200 70XX XXXX XX44"},
    "tbank": {"bank": "Т-Банк", "requisites": "5536 91XX XXXX XX77"},
    "sber_qr": {"bank": "Сбер QR", "requisites": "QR будет отправлен позже"},
    "sim": {"bank": "SIM-перевод", "requisites": "+7 901 234 56 78"},
}
