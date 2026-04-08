import random
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import MAX_BTC, MAX_XMR, MIN_BTC, MIN_XMR
from utils.escape_html import escape_html
from utils.valute import rate_manager

router = Router()

CRYPTO_CONFIG = {
    "btc": {
        "name": "BTC",
        "max_amount": MAX_BTC,
        "min_amount": MIN_BTC,
        "buy_handler": "buy_btc_standard",
        "back_handler": "back_to_buy_btc",
        "display_name": "Bitcoin"
    },
    "xmr": {
        "name": "XMR",
        "max_amount": MAX_XMR,
        "min_amount": MIN_XMR,
        "buy_handler": "buy_xmr_standard",
        "back_handler": "back_to_buy_xmr",
        "display_name": "Monero (XMR)"
    }
}

async def show_payment_methods(
    callback: CallbackQuery,
    crypto_type: str,
    config: dict[str, Any],
    edit: bool = True
):
    crypto_config = CRYPTO_CONFIG.get(crypto_type)
    if not crypto_config:
        return

    max_amount = crypto_config["max_amount"]

    if crypto_type == "btc":
        current_rate = rate_manager.get_btc_to_rub_rate()
    else:
        current_rate = rate_manager.get_xmr_to_rub_rate()

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Банковская карта", callback_data=f"pay_with_card_{crypto_type}")
    kb.button(text="📱 СБП", callback_data=f"pay_with_sbp_{crypto_type}")
    kb.button(text="📱 SIM (Мобильная связь)", callback_data=f"pay_with_sim_{crypto_type}")
    kb.button(text="🏢 Внутрибанк", callback_data=f"pay_with_inbank_{crypto_type}")

    kb.button(text="⬅️Назад", callback_data=crypto_config["back_handler"])
    kb.adjust(1)

    time_send_next_block = random.randint(6, 10)

    text = (
        f"💸Текущий курс: {current_rate:.0f} RUB\n"
        f"❇️Доступно для покупки: {max_amount} {crypto_config['name']}\n"
        f"🕒 До отправки следующего блока {time_send_next_block} минут.\n\n"
        f"Выберите способ оплаты:"
    )

    if edit:
        await callback.message.edit_text(escape_html(text), reply_markup=kb.as_markup())
    else:
        await callback.message.answer(escape_html(text), reply_markup=kb.as_markup())

async def get_crypto_config(crypto_type: str) -> dict[str, Any]:
    return CRYPTO_CONFIG.get(crypto_type, {})
