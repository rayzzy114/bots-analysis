import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PARSE_MODE = "HTML"

requisites = os.getenv("requisites")
bank = os.getenv("bank")
operator = os.getenv("operator")
rates = os.getenv("rates")
sell_btc = os.getenv("sell_btc")
news_channel = os.getenv("news_channel")
work_operator = os.getenv("work_operator")
operator2 = os.getenv("operator2")
operator3 = os.getenv("operator3")

ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

LTC_RATE_USD = float(os.getenv("LTC_RATE_USD", "70.09"))
LTC_RATE_RUB = float(os.getenv("LTC_RATE_RUB", "6650.20"))

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS