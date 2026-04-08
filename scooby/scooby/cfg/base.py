import os

from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")

# Contact Information
OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "@scooby_op")
OPERATOR_URL = os.getenv("OPERATOR_URL", "https://t.me/scooby_op")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+88804720472")
WEBSITE_URL = os.getenv("WEBSITE_URL", "https://scoobychange.com")
GAMES_CHAT_URL = os.getenv("GAMES_CHAT_URL", "http://t.me/+NYmLiwnMcfM0ZWJl")
REVIEWS_USERNAME = os.getenv("REVIEWS_USERNAME", "@scoobychange")
REVIEWS_URL = os.getenv("REVIEWS_URL", "https://t.me/scoobychange")
SMM_USERNAME = os.getenv("SMM_USERNAME", "@ScoobySMM")
SMM_URL = os.getenv("SMM_URL", "https://t.me/ScoobySMM")
HELP_USERNAME = os.getenv("HELP_USERNAME", "@scoobyhelp")
HELP_URL = os.getenv("HELP_URL", "https://t.me/scoobyhelp")

# Product Name
NAME_PRODUCT = os.getenv("NAME_PRODUCT", "*SCOOBYCHANGE*")
