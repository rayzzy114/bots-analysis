import asyncio
import logging
import os
import random
import string
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

load_dotenv()

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_settings = {}
user_states = {}
orders = {}

def get_admins():
    admins_str = os.getenv("ADMINS", "")
    if admins_str:
        return [int(admin_id.strip()) for admin_id in admins_str.split(",") if admin_id.strip().isdigit()]
    return []

def is_admin(user_id):
    return user_id in get_admins()

bank_requisites = {
    'Другой банк': {'card': '2204 3204 2378 0685', 'name': 'Другой банк'},
    'Яндекс': {'card': '2204 3204 2378 0685', 'name': 'Яндекс'},
    'Альфабанк': {'card': '2204 3204 2378 0685', 'name': 'Альфабанк'},
    'Сбербанк': {'card': '2204 3204 2378 0685', 'name': 'Сбербанк'},
    'Озон': {'card': '2204 3204 2378 0685', 'name': 'Ozon C2C'},
    'Т-Банк': {'card': '2204 3204 2378 0685', 'name': 'Т-Банк'}
}

crypto_addresses = {
    'BTC': {
        'Другой банк': {'address': 'bc1qscu39rnafgt6dm0zzjw6fgma03l4pg94f4xhmp'},
        'Яндекс': {'address': 'bc1qscu39rnafgt6dm0zzjw6fgma03l4pg94f4xhmp'},
        'Альфабанк': {'address': 'bc1qscu39rnafgt6dm0zzjw6fgma03l4pg94f4xhmp'},
        'Сбербанк': {'address': 'bc1qscu39rnafgt6dm0zzjw6fgma03l4pg94f4xhmp'},
        'Озон': {'address': 'bc1qscu39rnafgt6dm0zzjw6fgma03l4pg94f4xhmp'},
        'Т-Банк': {'address': 'bc1qscu39rnafgt6dm0zzjw6fgma03l4pg94f4xhmp'}
    },
    'LTC': {
        'Другой банк': {'address': ''},
        'Яндекс': {'address': ''},
        'Альфабанк': {'address': ''},
        'Сбербанк': {'address': ''},
        'Озон': {'address': ''},
        'Т-Банк': {'address': ''}
    },
    'USDT': {
        'Другой банк': {'address': ''},
        'Яндекс': {'address': ''},
        'Альфабанк': {'address': ''},
        'Сбербанк': {'address': ''},
        'Озон': {'address': ''},
        'Т-Банк': {'address': ''}
    }
}

def get_start_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐️ Купить BTC", callback_data="buy_btc"),
            InlineKeyboardButton(text="💳 Продать BTC", callback_data="sell_btc")
        ],
        [
            InlineKeyboardButton(text="🪙 Купить LTC", callback_data="buy_ltc"),
            InlineKeyboardButton(text="💳 Продать LTC", callback_data="sell_ltc")
        ],
        [
            InlineKeyboardButton(text="💵 Купить USDT", callback_data="buy_usdt"),
            InlineKeyboardButton(text="💳 Продать USDT", callback_data="sell_usdt")
        ],
        [
            InlineKeyboardButton(text="👨‍💻 Оператор", url=os.getenv("OPERATOR_LINK", "https://t.me/your_operator_link"))
        ],
        [
            InlineKeyboardButton(text="💬 Чат", url=os.getenv("CHAT_LINK", "https://t.me/your_chat_link"))
        ],
        [
            InlineKeyboardButton(text="⚙️ Настройки профиля", callback_data="profile_settings")
        ]
    ])
    return keyboard

def get_profile_settings_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Изменить режим комиссии", callback_data="change_commission_mode")
        ],
        [
            InlineKeyboardButton(text="🔄 Изменить валюту ввода", callback_data="change_input_currency")
        ],
        [
            InlineKeyboardButton(text="🔄 Изменить зарубежные реквизиты", callback_data="change_foreign_requisites")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_usdt_network_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Tron TRC20", callback_data="usdt_tron")
        ],
        [
            InlineKeyboardButton(text="🔵 Ethereum ERC20", callback_data="usdt_ethereum")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_sell_usdt_network_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Tron TRC20", callback_data="sell_usdt_tron")
        ],
        [
            InlineKeyboardButton(text="🔵 Ethereum ERC20", callback_data="sell_usdt_ethereum")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_bank_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚪ Другой банк", callback_data="bank_other")
        ],
        [
            InlineKeyboardButton(text="🟡 Яндекс", callback_data="bank_yandex")
        ],
        [
            InlineKeyboardButton(text="🔴 Альфабанк", callback_data="bank_alfa")
        ],
        [
            InlineKeyboardButton(text="🟢 Сбербанк", callback_data="bank_sberbank")
        ],
        [
            InlineKeyboardButton(text="🔵 Озон", callback_data="bank_ozon")
        ],
        [
            InlineKeyboardButton(text="🟡 Т-Банк", callback_data="bank_tbank")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_order_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я оплатил", callback_data="order_paid")
        ],
        [
            InlineKeyboardButton(text="📄 Обозреватель адресса ➡️", callback_data="address_explorer")
        ],
        [
            InlineKeyboardButton(text="👨‍💻 Оператор ➡️", url=os.getenv("OPERATOR_LINK", "https://t.me/your_operator_link"))
        ],
        [
            InlineKeyboardButton(text="💬 Чат ➡️", url=os.getenv("CHAT_LINK", "https://t.me/your_chat_link"))
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="order_cancel")
        ]
    ])
    return keyboard

def get_order_waiting_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 Обозреватель адресса ➡️", callback_data="address_explorer")
        ],
        [
            InlineKeyboardButton(text="👨‍💻 Оператор ➡️", url=os.getenv("OPERATOR_LINK", "https://t.me/your_operator_link"))
        ],
        [
            InlineKeyboardButton(text="💬 Чат ➡️", url=os.getenv("CHAT_LINK", "https://t.me/your_chat_link"))
        ]
    ])
    return keyboard

def get_sell_preorder_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📧 Запросить реквизит", callback_data="request_requisites")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_admin_order_keyboard(order_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin_approve_{order_id}")
        ],
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_{order_id}")
        ]
    ])
    return keyboard

def get_admin_panel_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Активные заказы", callback_data="admin_orders")
        ],
        [
            InlineKeyboardButton(text="💳 Управление реквизитами", callback_data="admin_requisites")
        ],
        [
            InlineKeyboardButton(text="🪙 Управление адресами крипты", callback_data="admin_crypto_addresses")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_start")
        ]
    ])
    return keyboard

def get_admin_crypto_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="₿ BTC", callback_data="admin_crypto_btc")
        ],
        [
            InlineKeyboardButton(text="Ł LTC", callback_data="admin_crypto_ltc")
        ],
        [
            InlineKeyboardButton(text="₮ USDT", callback_data="admin_crypto_usdt")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")
        ]
    ])
    return keyboard

def get_admin_crypto_bank_keyboard(crypto_type):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚪ Другой банк", callback_data=f"admin_crypto_{crypto_type.lower()}_other")
        ],
        [
            InlineKeyboardButton(text="🟡 Яндекс", callback_data=f"admin_crypto_{crypto_type.lower()}_yandex")
        ],
        [
            InlineKeyboardButton(text="🔴 Альфабанк", callback_data=f"admin_crypto_{crypto_type.lower()}_alfa")
        ],
        [
            InlineKeyboardButton(text="🟢 Сбербанк", callback_data=f"admin_crypto_{crypto_type.lower()}_sberbank")
        ],
        [
            InlineKeyboardButton(text="🔵 Озон", callback_data=f"admin_crypto_{crypto_type.lower()}_ozon")
        ],
        [
            InlineKeyboardButton(text="🟡 Т-Банк", callback_data=f"admin_crypto_{crypto_type.lower()}_tbank")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_crypto_addresses")
        ]
    ])
    return keyboard

def get_admin_requisites_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚪ Другой банк", callback_data="admin_req_other")
        ],
        [
            InlineKeyboardButton(text="🟡 Яндекс", callback_data="admin_req_yandex")
        ],
        [
            InlineKeyboardButton(text="🔴 Альфабанк", callback_data="admin_req_alfa")
        ],
        [
            InlineKeyboardButton(text="🟢 Сбербанк", callback_data="admin_req_sberbank")
        ],
        [
            InlineKeyboardButton(text="🔵 Озон", callback_data="admin_req_ozon")
        ],
        [
            InlineKeyboardButton(text="🟡 Т-Банк", callback_data="admin_req_tbank")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="admin_panel")
        ]
    ])
    return keyboard

def format_order_text(order_data, status="Зарегистрирован"):
    order_id = order_data.get('order_id', '')
    amount = order_data.get('amount', 0)
    requisites = order_data.get('requisites', '')
    crypto_display = order_data.get('crypto_display', '')
    crypto_symbol = order_data.get('crypto_symbol', 'BTC')
    address = order_data.get('address', '')
    card_details = order_data.get('card_details', '')
    estimated_rate = order_data.get('estimated_rate', 0)
    is_sell = order_data.get('is_sell', False)
    
    if is_sell:
        if status == "Клиент подтвердил оплату":
            text = f"""Заказ № <b>{order_id}</b>

🪙 Отправить: {crypto_display} {crypto_symbol}
📫 На адресс: <code>{address}</code>
📈 По нашему курсу: ~<code>{int(estimated_rate)}</code> руб.

💵 Получите: <code>{int(amount)}</code> руб.
💳 На реквизит: {requisites}

🔄 Статуст: {status}

🔍 Обработчик платежей проверяет вашу оплату, для ускорения вы можете отправь ему чек в формате pdf"""
        else:
            text = f"""Заказ № <b>{order_id}</b>

🪙 Отправить: {crypto_display} {crypto_symbol}
📫 На адресс: <code>{address}</code>
📈 По нашему курсу: ~<code>{int(estimated_rate)}</code> руб.

💵 Получите: <code>{int(amount)}</code> руб.
💳 На реквизит: {requisites}

🔄 Статуст: {status}

⏰ Если не будет оплаты в течении 120 мин., заказ будет отменён автоматически.

⚠️ Идентификация платежа производится по сумме, оплачивайте только точную сумму."""
    else:
        if status == "Клиент подтвердил оплату":
            text = f"""Заказ № <b>{order_id}</b>

💵 Отправить: <code>{int(amount)}</code> руб.
💳 На реквизит: {requisites}

🪙 Получите: {crypto_display} {crypto_symbol}
🌐 На адрес: <code>{address}</code>
📈 По нашему курсу: ~<code>{int(estimated_rate)}</code> руб.

🔄 Статуст: {status}

🔍 Обработчик платежей проверяет вашу оплату, для ускорения вы можете отправь ему чек в формате pdf"""
        else:
            text = f"""Заказ № <b>{order_id}</b>

💵 Отправить: <code>{int(amount)}</code> руб.
💳 На реквизит: {requisites}

🪙 Получите: {crypto_display} {crypto_symbol}
🌐 На адрес: <code>{address}</code>
📈 По нашему курсу: ~<code>{int(estimated_rate)}</code> руб.

🔄 Статуст: {status}

⏰ Если не будет оплаты в течении 30 мин., заказ будет отменён автоматически.

⚠️ Идентификация платежа производится по сумме, оплачивайте только точную сумму.

❗️ После успешной оплаты нажмите кнопку "Я оплатил".
Если исполнитель сделки не закроет платёж, спор будет открыт автоматически."""
    
    return text

def generate_order_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=20))

def get_crypto_rates():
    return {
        'BTC': float(os.getenv("BTC_RATE", "9000000")),
        'LTC': float(os.getenv("LTC_RATE", "100000")),
        'USDT': float(os.getenv("USDT_RATE", "100"))
    }

def calculate_crypto_amount(rub_amount, crypto_type):
    rates = get_crypto_rates()
    rate = rates.get(crypto_type, 9000000)
    amount = rub_amount / rate
    return amount

def get_user_settings(user_id):
    if user_id not in user_settings:
        user_settings[user_id] = {
            'commission_mode': True,
            'input_currency': True,
            'foreign_requisites': True
        }
    return user_settings[user_id]

def get_profile_settings_text(user_id):
    settings = get_user_settings(user_id)
    
    commission_1 = "✅" if not settings['commission_mode'] else "⏺️"
    commission_2 = "✅" if settings['commission_mode'] else "⏺️"
    
    currency_1 = "✅" if settings['input_currency'] else "⏺️"
    currency_2 = "✅" if not settings['input_currency'] else "⏺️"
    
    requisites_1 = "✅" if settings['foreign_requisites'] else "⏺️"
    requisites_2 = "✅" if not settings['foreign_requisites'] else "⏺️"
    
    text = f"""⚙️ Настройки профиля

1️⃣ Выберите, как учитывать комиссию при обмене:

    {commission_1} Включена в сумму
    {commission_2} Добавлена сверху

2️⃣ Выберите, в какой валюте вы хотите указывать сумму:

    {currency_1} Рубль
    {currency_2} Криптовалюта

3️⃣ Выберите, желаете ли вы получать зарубежные реквизиты, если местные не найдены:

    {requisites_1} Вкл.
    {requisites_2} Выкл.

* Способ комиссии используется только при покупке криптовалюты и вводе суммы в рублях"""
    
    return text

@dp.message(Command("start"))
async def cmd_start(message: Message):
    photo = FSInputFile("start.png")
    await message.answer_photo(
        photo=photo,
        reply_markup=get_start_keyboard()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ-панели.")
        return
    
    text = """🔐 Админ-панель

Выберите действие:"""
    
    photo = FSInputFile("start.png")
    await message.answer_photo(
        photo=photo,
        caption=text,
        reply_markup=get_admin_panel_keyboard()
    )

@dp.callback_query(lambda c: c.data == "profile_settings")
async def handle_profile_settings(callback: CallbackQuery):
    text = get_profile_settings_text(callback.from_user.id)
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_profile_settings_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_profile_settings_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "change_commission_mode")
async def handle_change_commission_mode(callback: CallbackQuery):
    settings = get_user_settings(callback.from_user.id)
    settings['commission_mode'] = not settings['commission_mode']
    
    text = get_profile_settings_text(callback.from_user.id)
    
    await callback.message.edit_caption(
        caption=text,
        reply_markup=get_profile_settings_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "change_input_currency")
async def handle_change_input_currency(callback: CallbackQuery):
    settings = get_user_settings(callback.from_user.id)
    settings['input_currency'] = not settings['input_currency']
    
    text = get_profile_settings_text(callback.from_user.id)
    
    await callback.message.edit_caption(
        caption=text,
        reply_markup=get_profile_settings_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "change_foreign_requisites")
async def handle_change_foreign_requisites(callback: CallbackQuery):
    settings = get_user_settings(callback.from_user.id)
    settings['foreign_requisites'] = not settings['foreign_requisites']
    
    text = get_profile_settings_text(callback.from_user.id)
    
    await callback.message.edit_caption(
        caption=text,
        reply_markup=get_profile_settings_keyboard()
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "buy_btc")
async def handle_buy_btc(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'btc_address', 'type': 'buy', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите адрес ВТС.
Например: bc1qaxpgxzurv73...s4cuhw2ctyx32yuju"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "buy_ltc")
async def handle_buy_ltc(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'ltc_address', 'type': 'buy', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """💰 Введите адрес LTC.
Например: ltc1q0qahex5heej53...k7je0hn828ypkt8s0er"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "sell_btc")
async def handle_sell_btc(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'card_details', 'type': 'sell', 'crypto': 'BTC', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите номер карты или телефон СБП с названием банка.
Пожалуйста укажите СБП если есть возможность.
Например: 88002000600 Сбербанк Иванов, 1000200040005000 Альфа"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "sell_ltc")
async def handle_sell_ltc(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'card_details', 'type': 'sell', 'crypto': 'LTC', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите номер карты или телефон СБП с названием банка.
Пожалуйста укажите СБП если есть возможность.
Например: 88002000600 Сбербанк Иванов, 1000200040005000 Альфа"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "buy_usdt")
async def handle_buy_usdt(callback: CallbackQuery):
    text = """🌐 Выберите сеть для USDT"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_usdt_network_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_usdt_network_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "usdt_tron")
async def handle_usdt_tron(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'usdt_address', 'type': 'buy', 'network': 'TRC-20', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите адресс USDT сеть TRC-20.
Например: TU4vEruvZwLL...12EJTPvNr7Pvaa"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "usdt_ethereum")
async def handle_usdt_ethereum(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'usdt_address', 'type': 'buy', 'network': 'ERC-20', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите адресс USDT сеть ERC-20.
Например: 0xdAC17F958D2ee...206994597C13D831ec7"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "sell_usdt")
async def handle_sell_usdt(callback: CallbackQuery):
    text = """🌐 Выберите сеть для USDT"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_sell_usdt_network_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_sell_usdt_network_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "sell_usdt_tron")
async def handle_sell_usdt_tron(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'card_details', 'type': 'sell', 'crypto': 'USDT', 'network': 'TRC-20', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите номер карты или телефон СБП с названием банка.
Пожалуйста укажите СБП если есть возможность.
Например: 88002000600 Сбербанк Иванов, 1000200040005000 Альфа"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data == "sell_usdt_ethereum")
async def handle_sell_usdt_ethereum(callback: CallbackQuery):
    user_states[callback.from_user.id] = {'waiting_for': 'card_details', 'type': 'sell', 'crypto': 'USDT', 'network': 'ERC-20', 'message_id': callback.message.message_id, 'chat_id': callback.message.chat.id}
    text = """✍️ Введите номер карты или телефон СБП с названием банка.
Пожалуйста укажите СБП если есть возможность.
Например: 88002000600 Сбербанк Иванов, 1000200040005000 Альфа"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_back_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_back_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("bank_"))
async def handle_bank_selection(callback: CallbackQuery):
    bank_name = callback.data.replace("bank_", "")
    bank_names = {
        'other': 'Другой банк',
        'yandex': 'Яндекс',
        'alfa': 'Альфабанк',
        'sberbank': 'Сбербанк',
        'ozon': 'Озон',
        'tbank': 'Т-Банк'
    }
    
    user_id = callback.from_user.id
    if user_id in user_states and user_states[user_id].get('waiting_for') == 'bank':
        selected_bank = bank_names.get(bank_name, 'Другой банк')
        user_states[user_id]['bank'] = selected_bank
        
        if user_states[user_id].get('is_sell'):
            user_states[user_id]['bank'] = selected_bank
            user_states[user_id]['waiting_for'] = 'waiting_sell_requisites'
            user_states[user_id]['message_id'] = callback.message.message_id
            user_states[user_id]['chat_id'] = callback.message.chat.id
            
            text = "⏳ Мы подбираем для вас реквизит, пожалуйста подождите"
            
            try:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=None
                )
            except:
                photo = FSInputFile("start.png")
                await callback.message.delete()
                msg = await callback.message.answer_photo(
                    photo=photo,
                    caption=text
                )
                user_states[user_id]['message_id'] = msg.message_id
                user_states[user_id]['chat_id'] = msg.chat.id
            
            await callback.answer()
            
            await asyncio.sleep(random.randint(5, 10))
            
            if user_id in user_states and user_states[user_id].get('waiting_for') == 'waiting_sell_requisites':
                state = user_states[user_id]
                order_id = state.get('order_id', generate_order_id())
                amount = state.get('amount', 0)
                crypto_amount = state.get('crypto_amount', 0)
                crypto_type = state.get('crypto', 'BTC')
                card_details = state.get('card_details', '')
                bank = state.get('bank', 'Другой банк')
                estimated_rate = get_crypto_rates().get(crypto_type, 9000000)
                
                crypto_symbol = crypto_type
                if crypto_type == 'USDT' and 'network' in state:
                    crypto_symbol = f"USDT ({state['network']})"
                
                if crypto_type == 'BTC':
                    crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                elif crypto_type == 'LTC':
                    crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                else:
                    crypto_display = f"{crypto_amount:.2f}".rstrip('0').rstrip('.')
                
                address_data = crypto_addresses.get(crypto_type, {}).get(bank, {'address': ''})
                address = address_data.get('address', '')
                
                req_data = bank_requisites.get(bank, {'card': '', 'name': bank})
                requisites = f"<code>{req_data['card']}</code> || {req_data['name']}"
                
                order_data = {
                    'order_id': order_id,
                    'amount': amount,
                    'requisites': requisites,
                    'crypto_display': crypto_display,
                    'crypto_symbol': crypto_symbol,
                    'address': address,
                    'card_details': card_details,
                    'estimated_rate': estimated_rate,
                    'is_sell': True,
                    'user_id': user_id,
                    'chat_id': state.get('chat_id'),
                    'message_id': state.get('message_id'),
                    'status': 'Зарегистрирован'
                }
                orders[order_id] = order_data
                
                text = format_order_text(order_data, "Зарегистрирован")
                
                user_states[user_id]['waiting_for'] = 'order_active'
                user_states[user_id]['order_id'] = order_id
                
                photo = FSInputFile("start.png")
                
                try:
                    await bot.edit_message_caption(
                        chat_id=state.get('chat_id'),
                        message_id=state.get('message_id'),
                        caption=text,
                        reply_markup=get_order_keyboard()
                    )
                except:
                    await bot.send_photo(
                        chat_id=state.get('chat_id'),
                        photo=photo,
                        caption=text,
                        reply_markup=get_order_keyboard()
                    )
            return
        
        user_states[user_id]['waiting_for'] = 'waiting_requisites'
        user_states[user_id]['message_id'] = callback.message.message_id
        user_states[user_id]['chat_id'] = callback.message.chat.id
        
        text = "⌛ Мы подбираем для вас реквизит, пожалуйста подождите"
        
        try:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=None
            )
        except:
            photo = FSInputFile("start.png")
            await callback.message.delete()
            msg = await callback.message.answer_photo(
                photo=photo,
                caption=text
            )
            user_states[user_id]['message_id'] = msg.message_id
            user_states[user_id]['chat_id'] = msg.chat.id
        
        await callback.answer()
        
        await asyncio.sleep(10)
        
        if user_id in user_states and user_states[user_id].get('waiting_for') == 'waiting_requisites':
            state = user_states[user_id]
            req_data = bank_requisites.get(selected_bank, {'card': '2204 3204 2378 0685', 'name': 'Другой банк'})
            requisites = f"<code>{req_data['card']}</code> || {req_data['name']}"
            order_id = state.get('order_id', generate_order_id())
            amount = state.get('amount', 0)
            crypto_amount = state.get('crypto_amount', 0)
            crypto_type = state.get('crypto', 'BTC')
            address = state.get('address', '')
            card_details = state.get('card_details', '')
            is_sell = state.get('is_sell', False)
            estimated_rate = get_crypto_rates().get(crypto_type, 9000000)
            
            crypto_symbol = crypto_type
            if crypto_type == 'USDT' and 'network' in state:
                crypto_symbol = f"USDT ({state['network']})"
            
            if crypto_type == 'BTC':
                crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
            elif crypto_type == 'LTC':
                crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
            else:
                crypto_display = f"{crypto_amount:.2f}".rstrip('0').rstrip('.')
            
            order_data = {
                'order_id': order_id,
                'amount': amount,
                'requisites': requisites,
                'crypto_display': crypto_display,
                'crypto_symbol': crypto_symbol,
                'address': address,
                'card_details': card_details,
                'estimated_rate': estimated_rate,
                'is_sell': is_sell,
                'user_id': user_id,
                'chat_id': state.get('chat_id'),
                'message_id': state.get('message_id'),
                'status': 'Зарегистрирован'
            }
            orders[order_id] = order_data
            
            text = format_order_text(order_data, "Зарегистрирован")
            
            user_states[user_id]['waiting_for'] = 'order_active'
            user_states[user_id]['order_id'] = order_id
            
            try:
                await bot.edit_message_caption(
                    chat_id=state.get('chat_id'),
                    message_id=state.get('message_id'),
                    caption=text,
                    reply_markup=get_order_keyboard()
                )
            except:
                photo = FSInputFile("start.png")
                msg = await bot.send_photo(
                    chat_id=state.get('chat_id'),
                    photo=photo,
                    caption=text,
                    reply_markup=get_order_keyboard()
                )
                user_states[user_id]['message_id'] = msg.message_id
    else:
        await callback.answer()

@dp.callback_query(lambda c: c.data == "order_paid")
async def handle_order_paid(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in user_states and user_states[user_id].get('waiting_for') == 'order_active':
        order_id = user_states[user_id].get('order_id')
        
        if order_id and order_id in orders:
            orders[order_id]['status'] = 'Клиент подтвердил оплату'
            
            text = format_order_text(orders[order_id], "Клиент подтвердил оплату")
            
            try:
                await callback.message.edit_caption(
                    caption=text,
                    reply_markup=get_order_waiting_keyboard()
                )
            except:
                photo = FSInputFile("start.png")
                await callback.message.delete()
                await callback.message.answer_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=get_order_waiting_keyboard()
                )
            
            for admin_id in get_admins():
                try:
                    admin_text = f"""Новый заказ требует подтверждения:

{text}"""
                    await bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        reply_markup=get_admin_order_keyboard(order_id)
                    )
                except:
                    pass
            
            await callback.answer("Ожидаем подтверждения оплаты от исполнителя.")
        else:
            await callback.answer("Заказ не найден.")
    else:
        await callback.answer("Заказ не найден.")
    
@dp.callback_query(lambda c: c.data == "request_requisites")
async def handle_request_requisites(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in user_states and user_states[user_id].get('waiting_for') == 'sell_preorder':
        user_states[user_id]['waiting_for'] = 'bank'
        
        text = """👇 Выберите банк с которого будете оплачивать"""
        
        try:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=get_bank_keyboard()
            )
        except:
            photo = FSInputFile("start.png")
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=get_bank_keyboard()
            )
        await callback.answer()
    else:
        await callback.answer()

@dp.callback_query(lambda c: c.data == "address_explorer")
async def handle_address_explorer(callback: CallbackQuery):
    await callback.answer("Функция в разработке.")
    
@dp.callback_query(lambda c: c.data == "admin_panel")
async def handle_admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    text = """🔐 Админ-панель

Выберите действие:"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_panel_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_panel_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_orders")
async def handle_admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    active_orders = [order for order in orders.values() if order.get('status') == 'Клиент подтвердил оплату']
    
    if not active_orders:
        text = "📋 Активные заказы\n\nНет заказов, ожидающих подтверждения."
    else:
        text = f"📋 Активные заказы\n\nНайдено заказов: {len(active_orders)}\n\nИспользуйте кнопки в уведомлениях для подтверждения/отклонения."
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_panel_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_panel_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_crypto_addresses")
async def handle_admin_crypto_addresses(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    text = """🪙 Управление адресами криптовалюты

Выберите криптовалюту:"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_crypto_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_crypto_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_crypto_") and c.data.split("_")[2] in ["btc", "ltc", "usdt"])
async def handle_admin_crypto_select(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    crypto_type = callback.data.split("_")[2].upper()
    
    text = f"""🪙 Управление адресами {crypto_type}

Выберите банк для редактирования адреса:"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_crypto_bank_keyboard(crypto_type)
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_crypto_bank_keyboard(crypto_type)
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_crypto_") and any(x in c.data for x in ["_btc_", "_ltc_", "_usdt_"]))
async def handle_admin_crypto_bank_select(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    parts = callback.data.split("_")
    crypto_type = parts[2].upper()
    bank_key = parts[3]
    
    bank_names = {
        'other': 'Другой банк',
        'yandex': 'Яндекс',
        'alfa': 'Альфабанк',
        'sberbank': 'Сбербанк',
        'ozon': 'Озон',
        'tbank': 'Т-Банк'
    }
    
    bank_name = bank_names.get(bank_key, 'Другой банк')
    current_data = crypto_addresses.get(crypto_type, {}).get(bank_name, {'address': ''})
    current_address = current_data.get('address', '')
    
    text = f"""🪙 Редактирование адреса {crypto_type}

Банк: {bank_name}
Текущий адрес: <code>{current_address if current_address else 'не задан'}</code>

Отправьте новый адрес в следующем сообщении."""
    
    user_states[callback.from_user.id] = {
        'waiting_for': 'admin_crypto_address',
        'crypto_type': crypto_type,
        'bank_name': bank_name,
        'message_id': callback.message.message_id,
        'chat_id': callback.message.chat.id
    }
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_crypto_bank_keyboard(crypto_type)
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_crypto_bank_keyboard(crypto_type)
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_requisites")
async def handle_admin_requisites(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    text = """💳 Управление реквизитами

Выберите банк для изменения реквизитов:"""
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_requisites_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_requisites_keyboard()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_req_"))
async def handle_admin_requisite_edit(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    bank_key = callback.data.replace("admin_req_", "")
    bank_names = {
        'other': 'Другой банк',
        'yandex': 'Яндекс',
        'alfa': 'Альфабанк',
        'sberbank': 'Сбербанк',
        'ozon': 'Озон',
        'tbank': 'Т-Банк'
    }
    
    bank_name = bank_names.get(bank_key, 'Другой банк')
    current_req = bank_requisites.get(bank_name, {'card': '', 'name': ''})
    current_requisites = f"<code>{current_req['card']}</code> || {current_req['name']}"
    
    text = f"""💳 Редактирование реквизитов

Банк: {bank_name}
Текущие реквизиты: {current_requisites}

Отправьте новые реквизиты в формате:
Номер карты || Название банка
(например: 2204 3204 2378 0685 || Сбербанк)"""
    
    user_states[callback.from_user.id] = {
        'waiting_for': 'admin_requisites',
        'bank_name': bank_name,
        'message_id': callback.message.message_id,
        'chat_id': callback.message.chat.id
    }
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_admin_requisites_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        msg = await callback.message.answer_photo(
            photo=photo,
            caption=text,
            reply_markup=get_admin_requisites_keyboard()
        )
        user_states[callback.from_user.id]['message_id'] = msg.message_id
        user_states[callback.from_user.id]['chat_id'] = msg.chat.id
    
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("admin_") and c.data.split("_")[1] in ["approve", "reject"])
async def handle_admin_action(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.")
        return
    
    action = callback.data.split("_")[1]
    order_id = callback.data.split("_", 2)[2] if len(callback.data.split("_")) > 2 else None
    
    if not order_id or order_id not in orders:
        await callback.answer("Заказ не найден.")
        return
    
    order_data = orders[order_id]
    
    if action == "approve":
        order_data['status'] = 'Оплата подтверждена'
        text = format_order_text(order_data, "Оплата подтверждена")
        
        try:
            await bot.edit_message_caption(
                chat_id=order_data['chat_id'],
                message_id=order_data['message_id'],
                caption=text,
                reply_markup=get_order_waiting_keyboard()
            )
        except:
            pass
        
        await callback.message.edit_text(f"✅ Заказ {order_id} подтвержден.")
        await callback.answer("Оплата подтверждена.")
        
    elif action == "reject":
        order_data['status'] = 'Оплата отклонена'
        text = format_order_text(order_data, "Оплата отклонена")
        
        try:
            await bot.edit_message_caption(
                chat_id=order_data['chat_id'],
                message_id=order_data['message_id'],
                caption=text,
                reply_markup=get_order_waiting_keyboard()
            )
        except:
            pass
        
        await callback.message.edit_text(f"❌ Заказ {order_id} отклонен.")
        await callback.answer("Оплата отклонена.")

def get_canceled_order_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👨‍💻 Оператор", url=os.getenv("OPERATOR_LINK", "https://t.me/your_operator_link"))
        ]
    ])
    return keyboard

@dp.callback_query(lambda c: c.data == "order_cancel")
async def handle_order_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    order_data = None
    
    if user_id in user_states:
        order_id = user_states[user_id].get('order_id')
        if order_id and order_id in orders:
            order_data = orders[order_id]
            orders[order_id]['status'] = 'Отменён'
            del orders[order_id]
        del user_states[user_id]
    
    if order_data:
        crypto_display = order_data.get('crypto_display', '')
        crypto_symbol = order_data.get('crypto_symbol', 'BTC')
        amount = order_data.get('amount', 0)
        order_id = order_data.get('order_id', '')
        
        text = f"""Заказ № <b>{order_id}</b> отменён

🪙 Отправить: {crypto_display} {crypto_symbol}

💵 Получите: <code>{int(amount)}</code> руб.

❌ Заказ не был оплачен

👨‍💻 Если вы оплатили заказ после отмены, свяжитесь с оператором, если возможно мы постаремся решить вашу проблему

🔄 Для создания нового заказа, вызовите новое меню /menu"""
        
        photo = FSInputFile("start.png")
        
        try:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=get_canceled_order_keyboard()
            )
        except:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=get_canceled_order_keyboard()
            )
    else:
        try:
            await callback.message.edit_caption(
                caption=None,
                reply_markup=get_start_keyboard()
            )
        except:
            photo = FSInputFile("start.png")
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=photo,
                reply_markup=get_start_keyboard()
            )
    
    await callback.answer("Заказ отменен.")

@dp.callback_query(lambda c: c.data == "back_to_start")
async def handle_back_to_start(callback: CallbackQuery):
    if callback.from_user.id in user_states:
        del user_states[callback.from_user.id]
    try:
        await callback.message.edit_caption(
            caption=None,
            reply_markup=get_start_keyboard()
        )
    except:
        photo = FSInputFile("start.png")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            reply_markup=get_start_keyboard()
        )
    await callback.answer()

@dp.message()
async def handle_text_message(message: Message):
    user_id = message.from_user.id
    
    if is_admin(user_id) and user_id in user_states:
        state = user_states[user_id]
        
        if state.get('waiting_for') == 'admin_crypto_address':
            new_address = message.text.strip()
            crypto_type = state.get('crypto_type')
            bank_name = state.get('bank_name')
            
            if crypto_type and bank_name:
                if crypto_type not in crypto_addresses:
                    crypto_addresses[crypto_type] = {}
                if bank_name not in crypto_addresses[crypto_type]:
                    crypto_addresses[crypto_type][bank_name] = {'address': ''}
                
                crypto_addresses[crypto_type][bank_name]['address'] = new_address
                
                await message.delete()
                
                text = f"""🪙 Редактирование адреса {crypto_type}

Банк: {bank_name}
Новый адрес: <code>{new_address}</code>

✅ Адрес успешно обновлен!"""
                
                try:
                    await bot.edit_message_caption(
                        chat_id=state.get('chat_id'),
                        message_id=state.get('message_id'),
                        caption=text,
                        reply_markup=get_admin_crypto_bank_keyboard(crypto_type)
                    )
                except:
                    photo = FSInputFile("start.png")
                    await message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=get_admin_crypto_bank_keyboard(crypto_type)
                    )
                
                del user_states[user_id]
                return
        
        if state.get('waiting_for') == 'admin_requisites':
            new_requisites = message.text.strip()
            bank_name = state.get('bank_name')
            
            if bank_name:
                if ' || ' in new_requisites:
                    parts = new_requisites.split(' || ', 1)
                    card = parts[0].strip()
                    name = parts[1].strip() if len(parts) > 1 else bank_name
                    bank_requisites[bank_name] = {'card': card, 'name': name}
                    formatted_req = f"<code>{card}</code> || {name}"
                else:
                    bank_requisites[bank_name] = {'card': new_requisites, 'name': bank_name}
                    formatted_req = f"<code>{new_requisites}</code> || {bank_name}"
                
                await message.delete()
                
                text = f"""💳 Редактирование реквизитов

Банк: {bank_name}
Новые реквизиты: {formatted_req}

✅ Реквизиты успешно обновлены!"""
                
                try:
                    await bot.edit_message_caption(
                        chat_id=state.get('chat_id'),
                        message_id=state.get('message_id'),
                        caption=text,
                        reply_markup=get_admin_requisites_keyboard()
                    )
                except:
                    photo = FSInputFile("start.png")
                    await message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=get_admin_requisites_keyboard()
                    )
                
                del user_states[user_id]
                return
    
    if user_id in user_states:
        state = user_states[user_id]
        
        if state['waiting_for'] == 'card_details' and state.get('type') == 'sell':
            card_details = message.text.strip()
            await message.delete()
            
            crypto_type = state.get('crypto', 'BTC')
            crypto_name = crypto_type
            if crypto_type == 'USDT' and 'network' in state:
                crypto_name = f"USDT ({state['network']})"
            
            text = f"""✍️ Введите количество {crypto_name}.
Например: 0.001"""
            
            user_states[user_id] = {'waiting_for': 'sell_amount', 'card_details': card_details, 'type': 'sell', 'crypto': crypto_type, 'message_id': state.get('message_id'), 'chat_id': state.get('chat_id')}
            if 'network' in state:
                user_states[user_id]['network'] = state['network']
            
            try:
                await bot.edit_message_caption(
                    chat_id=state.get('chat_id'),
                    message_id=state.get('message_id'),
                    caption=text,
                    reply_markup=get_back_keyboard()
                )
            except:
                photo = FSInputFile("start.png")
                msg = await message.answer_photo(
                    photo=photo,
                    caption=text,
                    reply_markup=get_back_keyboard()
                )
                user_states[user_id]['message_id'] = msg.message_id
                user_states[user_id]['chat_id'] = msg.chat.id
            return
        
        if state['waiting_for'] in ['btc_address', 'ltc_address', 'usdt_address']:
            address = message.text.strip()
            await message.delete()
            
            if state['type'] == 'buy':
                settings = get_user_settings(user_id)
                crypto_type = state['waiting_for'].replace('_address', '').upper()
                
                if settings['input_currency']:
                    text = f"""✍️ Введите количество сумму в рублях.
Например: 5000"""
                else:
                    crypto_name = crypto_type
                    if crypto_type == 'USDT' and 'network' in state:
                        crypto_name = f"USDT ({state['network']})"
                    text = f"""✍️ Введите количество {crypto_name}.
Например: 0.001"""
                
                user_states[user_id] = {'waiting_for': 'amount', 'address': address, 'type': 'buy', 'crypto': crypto_type, 'message_id': state.get('message_id'), 'chat_id': state.get('chat_id')}
                if 'network' in state:
                    user_states[user_id]['network'] = state['network']
                
                try:
                    await bot.edit_message_caption(
                        chat_id=state.get('chat_id'),
                        message_id=state.get('message_id'),
                        caption=text,
                        reply_markup=get_back_keyboard()
                    )
                except:
                    photo = FSInputFile("start.png")
                    msg = await message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=get_back_keyboard()
                    )
                    user_states[user_id]['message_id'] = msg.message_id
                    user_states[user_id]['chat_id'] = msg.chat.id
                return
        
        elif state['waiting_for'] == 'sell_amount':
            try:
                crypto_amount = float(message.text.strip().replace(',', '.').replace(' ', ''))
                await message.delete()
                
                if crypto_amount <= 0:
                    await message.answer("Сумма должна быть больше нуля.")
                    return
                
                crypto_type = state.get('crypto', 'BTC')
                rates = get_crypto_rates()
                rate = rates.get(crypto_type, 9000000)
                
                rub_amount = crypto_amount * rate
                if rub_amount < 1500:
                    min_crypto = 1500 / rate
                    if crypto_type == 'BTC':
                        min_display = f"{min_crypto:.8f}".rstrip('0').rstrip('.')
                    elif crypto_type == 'LTC':
                        min_display = f"{min_crypto:.6f}".rstrip('0').rstrip('.')
                    else:
                        min_display = f"{min_crypto:.2f}".rstrip('0').rstrip('.')
                    await message.answer(f"Минимальная сумма платежа: {min_display} {crypto_type} (эквивалент 1500 руб.)")
                    return
                
                order_id = generate_order_id()
                card_details = state.get('card_details', '')
                
                crypto_symbol = crypto_type
                if crypto_type == 'USDT' and 'network' in state:
                    crypto_symbol = f"USDT ({state['network']})"
                
                if crypto_type == 'BTC':
                    crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                elif crypto_type == 'LTC':
                    crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                else:
                    crypto_display = f"{crypto_amount:.2f}".rstrip('0').rstrip('.')
                
                estimated_rate = get_crypto_rates().get(crypto_type, 9000000)
                
                text = f"""Предзаказ № <b>{order_id}</b>

🪙 Отправить: {crypto_display} {crypto_symbol}
📫 На адресс: после запроса
📈 По нашему курсу: ~<code>{int(estimated_rate)}</code> руб.

💵 Получите: <code>{int(rub_amount)}</code> руб.
💳 На карту: <code>{card_details}</code>

⏰ Предрасчёт действителен 5 мин.

❗️ Запрашивайте реквизит непосредственно перед оплатой."""
                
                user_states[user_id] = {'waiting_for': 'sell_preorder', 'order_id': order_id, 'amount': rub_amount, 'crypto_amount': crypto_amount, 'crypto': crypto_type, 'card_details': card_details, 'message_id': state.get('message_id'), 'chat_id': state.get('chat_id'), 'is_sell': True}
                if 'network' in state:
                    user_states[user_id]['network'] = state['network']
                
                try:
                    await bot.edit_message_caption(
                        chat_id=state.get('chat_id'),
                        message_id=state.get('message_id'),
                        caption=text,
                        reply_markup=get_sell_preorder_keyboard()
                    )
                except:
                    photo = FSInputFile("start.png")
                    msg = await message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=get_sell_preorder_keyboard()
                    )
                    user_states[user_id]['message_id'] = msg.message_id
                    user_states[user_id]['chat_id'] = msg.chat.id
                return
            except ValueError:
                await message.delete()
                await message.answer("Пожалуйста, введите корректную сумму.")
                return
        
        elif state['waiting_for'] == 'amount':
            try:
                input_value = float(message.text.strip().replace(',', '.').replace(' ', ''))
                await message.delete()
                
                if input_value <= 0:
                    await message.answer("Сумма должна быть больше нуля.")
                    return
                
                settings = get_user_settings(user_id)
                crypto_type = state.get('crypto', 'BTC')
                rates = get_crypto_rates()
                rate = rates.get(crypto_type, 9000000)
                
                if settings['input_currency']:
                    rub_amount = input_value
                    if rub_amount < 1500:
                        await message.answer("Минимальная сумма платежа: 1500 руб.")
                        return
                    crypto_amount = calculate_crypto_amount(rub_amount, crypto_type)
                else:
                    crypto_amount = input_value
                    rub_amount = crypto_amount * rate
                    if rub_amount < 1500:
                        min_crypto = 1500 / rate
                        if crypto_type == 'BTC':
                            min_display = f"{min_crypto:.8f}".rstrip('0').rstrip('.')
                        elif crypto_type == 'LTC':
                            min_display = f"{min_crypto:.6f}".rstrip('0').rstrip('.')
                        else:
                            min_display = f"{min_crypto:.2f}".rstrip('0').rstrip('.')
                        await message.answer(f"Минимальная сумма платежа: {min_display} {crypto_type}")
                        return
                
                if settings['commission_mode'] and settings['input_currency']:
                    rub_amount_with_commission = rub_amount * 1.01
                else:
                    rub_amount_with_commission = rub_amount
                
                order_id = generate_order_id()
                address = state.get('address', '')
                
                crypto_symbol = crypto_type
                if crypto_type == 'USDT' and 'network' in state:
                    crypto_symbol = f"USDT ({state['network']})"
                
                estimated_rate = get_crypto_rates().get(crypto_type, 9000000)
                
                if crypto_type == 'BTC':
                    crypto_display = f"{crypto_amount:.8f}".rstrip('0').rstrip('.')
                elif crypto_type == 'LTC':
                    crypto_display = f"{crypto_amount:.6f}".rstrip('0').rstrip('.')
                else:
                    crypto_display = f"{crypto_amount:.2f}".rstrip('0').rstrip('.')
                
                text = f"""Предзаказ № <b>{order_id}</b>

💵 Отправить: <code>{int(rub_amount_with_commission)}</code> руб.
💳 На карту: после запроса

🪙 Получите: {crypto_display} {crypto_symbol}
📫 На адресс: <code>{address}</code>
📈 По нашему курсу: ~<code>{int(estimated_rate)}</code> руб.

⏰ Предрасчёт действителен 5 мин.

❗️ Запрашивайте реквизит непосредственно перед оплатой.

👇 Выберите банк с которого будете оплачивать"""
                
                user_states[user_id] = {'waiting_for': 'bank', 'order_id': order_id, 'amount': rub_amount_with_commission, 'crypto_amount': crypto_amount, 'crypto': crypto_type, 'address': address, 'message_id': state.get('message_id'), 'chat_id': state.get('chat_id')}
                if 'network' in state:
                    user_states[user_id]['network'] = state['network']
                
                try:
                    await bot.edit_message_caption(
                        chat_id=state.get('chat_id'),
                        message_id=state.get('message_id'),
                        caption=text,
                        reply_markup=get_bank_keyboard()
                    )
                except:
                    photo = FSInputFile("start.png")
                    msg = await message.answer_photo(
                        photo=photo,
                        caption=text,
                        reply_markup=get_bank_keyboard()
                    )
                    user_states[user_id]['message_id'] = msg.message_id
                    user_states[user_id]['chat_id'] = msg.chat.id
                return
            except ValueError:
                await message.delete()
                await message.answer("Пожалуйста, введите корректную сумму.")
                return
    
    await message.delete()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

