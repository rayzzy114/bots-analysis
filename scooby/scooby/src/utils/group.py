import logging
import os
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ADMIN_IDS = os.getenv("ADMIN_IDS", "").split(",")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS if admin_id.strip()]


def admin_order_buttons(order_id: str):
    """Кнопки для админа по заявке"""
    buttons = [
        [
            InlineKeyboardButton(text="💬 Ответить", callback_data=f"admin_reply_{order_id}"),
            InlineKeyboardButton(text="✅ Принять", callback_data=f"admin_accept_{order_id}")
        ],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{order_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_message_to_channel(bot: Bot, data: dict, sale: bool = False):
    username = data["username"]
    currency = data["currency"].upper()
    value_crypto = data["value_crypto"]
    value_rub = data["value_rub"]
    unit = data["unit"]
    priority = data.get("priority", "normal")
    final_sum = data.get("final_sum", 0)

    action_text = "продажу" if sale else "покупку"

    text = f"""📢 Новый запрос на {action_text}

👤 Пользователь: {username}
💎 <b>Сумма к оплате: {final_sum} RUB</b>
🪙 Получит: {value_crypto:.8f} {currency}
💳 Оплата указана в: {unit}
"""

    # Приоритет (просто указываем VIP или Обычный)
    if priority == "vip":
        text += "💎 VIP Приоритет\n"
    else:
        text += "⭐ Обычный приоритет\n"

    # ID заявки
    if "order_id" in data:
        text += f"📜 ID заявки: {data['order_id']}\n"

    # Метод оплаты
    if "payment_method" in data:
        from src.utils.payment_methods import get_payment_methods
        methods = get_payment_methods()
        method_name = next((m["name"] for m in methods if m["callback"] == data["payment_method"]), data["payment_method"])
        text += f"💳 Метод оплаты: {method_name}\n"

    # Кошелёк
    if "wallet" in data:
        text += f"💳 Кошелёк: <code>{data['wallet']}</code>\n"

    order_id = data.get("order_id")
    keyboard = admin_order_buttons(order_id) if order_id else None

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            logger.error(f"Не удалось отправить сообщение админу {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения админу {admin_id}: {e}")