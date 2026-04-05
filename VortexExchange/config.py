import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME")

ADMIN_IDS = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

REVIEWS_LINK = os.getenv("REVIEWS_LINK")
NEWS_LINK = os.getenv("NEWS_LINK")
OPERATOR_LINK = os.getenv("OPERATOR_LINK")
SKUPKA = os.getenv("SKUPKA")

PARSE_MODE = "HTML"

MIN_XMR = float(os.getenv("MIN_XMR", "0.01"))
MAX_XMR = float(os.getenv("MAX_XMR", "2.0"))

MIN_BTC = float(os.getenv("MIN_BTC", "0.0002"))
MAX_BTC = float(os.getenv("MAX_BTC", "0.025"))