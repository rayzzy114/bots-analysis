from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import os
from dotenv import load_dotenv

load_dotenv()

OPERATOR_USERNAME = os.getenv("OPERATOR_USERNAME", "@expresschanger_support_bot")


def home_button():
    buttons = [
        [InlineKeyboardButton(text="👨‍💻 Оператор", url=f"https://t.me/{OPERATOR_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton(text="🚀 Главное меню", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

