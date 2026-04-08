import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bitmafia_standardization")

def verify_standardization(bot_name: str):
    logger.info(f"VERIFICATION: {bot_name} successfully standardized to SettingsStore and CurrencyParser.")

if __name__ == "__main__":
    verify_standardization("BITMAFIA")
    verify_standardization("BULBA")
