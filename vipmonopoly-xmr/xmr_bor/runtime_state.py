"""Runtime state manager for dynamic configuration updates without restart."""
import os

from dotenv import load_dotenv


class RuntimeState:
    """Singleton state manager for runtime-updatable configuration."""

    def __init__(self):
        self.reload()

    def reload(self):
        """Reload all values from .env file."""
        load_dotenv(override=True)

        # Admin IDs
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        self.admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]

        # Links that can be updated via admin panel
        self.operator = os.getenv("operator", "")
        self.operator2 = os.getenv("operator2", "")
        self.operator3 = os.getenv("operator3", "")
        self.rates = os.getenv("rates", "")
        self.sell_btc = os.getenv("sell_btc", "")
        self.news_channel = os.getenv("news_channel", "")
        self.work_operator = os.getenv("work_operator", "")

        # Rates
        self.XMR_RATE_USD = float(os.getenv("XMR_RATE_USD", "70.09"))
        self.XMR_RATE_RUB = float(os.getenv("XMR_RATE_RUB", "6650.20"))
        self.LTC_RATE_USD = float(os.getenv("LTC_RATE_USD", "70.09"))
        self.LTC_RATE_RUB = float(os.getenv("LTC_RATE_RUB", "6650.20"))
        self.BTC_RATE_USD = float(os.getenv("BTC_RATE_USD", "45000.0"))
        self.BTC_RATE_RUB = float(os.getenv("BTC_RATE_RUB", "4500000.0"))


# Global singleton instance
_runtime_state = RuntimeState()


def get_runtime_state() -> RuntimeState:
    """Get the global runtime state instance."""
    return _runtime_state
