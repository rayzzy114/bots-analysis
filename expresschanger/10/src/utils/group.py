import logging
import os

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]


def admin_order_buttons(order_id: str):
    buttons = [
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"admin_accept_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_message_to_channel(bot: Bot, data: dict, sale: bool = False):
    username = data["username"]
    currency = data["currency"].upper()
    value_crypto = data["value_crypto"]
    value_rub = data["value_rub"]
    unit = data["unit"]

    action_text = "продажу" if sale else "покупку"

    text = f"""📢 Новый запрос на {action_text}

👤 Пользователь: {username}
💰 Сумма: {value_crypto:.8f} {currency} (~ {int(value_rub)} RUB)
💳 Оплата указана в: {unit}
"""

    if "priority" in data:
        priority_text = "VIP" if data["priority"] == "vip" else "Обычный"
        text += f"⭐ Приоритет: {priority_text}\n"
        if "final_sum" in data:
            text += f"💎 Итоговая сумма: {data['final_sum']} RUB\n"

    if "order_id" in data:
        text += f"📜 ID заявки: {data['order_id']}\n"

    if "payment_method_index" in data:
        from src.db.settings import get_payment_methods
        methods = await get_payment_methods()
        method_index = data.get("payment_method_index", 0)
        if 0 <= method_index < len(methods):
            method_name = methods[method_index]["name"]
        else:
            method_name = "Неизвестный метод"
        text += f"💳 Метод оплаты: {method_name}\n"
    elif "method_name" in data:
        text += f"💳 Метод оплаты: {data['method_name']}\n"

    if "wallet" in data:
        text += f"💳 Кошелек: <code>{data['wallet']}</code>\n"

    order_id = data.get("order_id")
    keyboard = admin_order_buttons(order_id) if order_id else None

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, reply_markup=keyboard)
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения админу {admin_id}: {e}")


async def send_receipt_to_admins(bot: Bot, order_id: str, order_data: dict, receipt_file_id: str, receipt_type: str):
    receipt_type_text = "Фото" if receipt_type == "photo" else "PDF"
    text = f"📜 ID заявки: {order_id}\n📸 {receipt_type_text}"

    keyboard = admin_order_buttons(order_id) if order_id else None

    for admin_id in ADMIN_IDS:
        try:
            if receipt_type == "photo":
                await bot.send_photo(chat_id=admin_id, photo=receipt_file_id, caption=text, reply_markup=keyboard)
            elif receipt_type == "document":
                await bot.send_document(chat_id=admin_id, document=receipt_file_id, caption=text, reply_markup=keyboard)
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения админу {admin_id}: {e}")

