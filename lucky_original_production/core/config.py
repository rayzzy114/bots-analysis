import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Config:
    BASE_DIR = BASE_DIR
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    DB_PATH = os.path.join(BASE_DIR, "botik.db")
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")

    WEB_ADMIN_USERNAME = os.getenv("WEB_ADMIN_USERNAME")
    WEB_ADMIN_PASSWORD = os.getenv("WEB_ADMIN_PASSWORD")
    SECRET_KEY = os.getenv("SECRET_KEY")

    ADMIN_ID_RAW = os.getenv("ADMIN_ID", "0")
    ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else 0

    # Commission settings
    COMMISSION_BUY = float(os.getenv("COMMISSION_BUY", "20"))  # 20% commission
    NETWORK_FEE = float(os.getenv("NETWORK_FEE", "95"))  # 95 RUB network fee

    # CoinGecko API
    COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

    @classmethod
    def validate(cls):
        if not all([cls.BOT_TOKEN, cls.ADMIN_ID_RAW]):
            raise ValueError("Missing critical environment variables (BOT_TOKEN or ADMIN_ID)! Check your .env file.")


# Module-level exports for backwards compatibility and direct imports
COMMISSION_BUY = Config.COMMISSION_BUY
NETWORK_FEE = Config.NETWORK_FEE
COINGECKO_API_URL = Config.COINGECKO_API_URL
