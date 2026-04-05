import asyncio
import os
import re
import random
from PIL import Image
from captcha.image import ImageCaptcha
import io
import string
from aiogram import Bot, Dispatcher, F
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.types import (
    Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, BotCommand,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardRemove
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import sqlite3
from datetime import datetime, timedelta
from aiogram.types import BufferedInputFile
# ================== ENV ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

BTC_BUY = float(os.getenv("BTC_BUY"))
LTC_BUY = float(os.getenv("LTC_BUY"))
BTC_SELL = float(os.getenv("BTC_SELL"))
LTC_SELL = float(os.getenv("LTC_SELL"))

MIN_RUB = float(os.getenv("MIN_RUB", "1500"))
MIN_BTC = float(os.getenv("MIN_BTC", "0.00014337"))
SUPPORT_USER = os.getenv("SUPPORT_USER")

# Contacts from env

NEWS_URL = os.getenv("NEWS_URL", "https://t.me/news_channel")
REVIEWS_URL = os.getenv("REVIEWS_URL", "https://t.me/reviews_channel")
CHAT_URL = os.getenv("CHAT_URL", "https://t.me/chat_group")
ADMIN_URL = os.getenv("ADMIN_URL", "https://t.me/admin_username")
SITE_URL = os.getenv("SITE_URL", "https://your-site.com")

# ================== STATES ==================
class ExchangeState(StatesGroup):
    choose_direction = State()
    enter_amount = State()

class BuyState(StatesGroup):
    choose_coin = State()
    enter_amount = State()
    enter_wallet = State()
    waiting_proof = State() # <-- новое состояние

# В класс SellState добавь/измени
class SellState(StatesGroup):
    choose_coin = State()
    enter_rub_amount = State()
    choose_payout_method = State()
    enter_requisites = State()      # общий для карты и СБП
    enter_bank_name = State()
    confirm_sell = State()
    confirm_sell_cancel = State()

class PromoState(StatesGroup):
    waiting_promo = State()

class CalculatorState(StatesGroup):
    choose_coin = State()
    enter_rub_amount = State()

class CaptchaState(StatesGroup):
    waiting_captcha = State()
    
class AdminState(StatesGroup):
    choose_requisite_field = State()   # выбор, что менять (карта, СБП и т.д.)
    enter_requisite_value = State()    # ввод нового значения
    change_crypto_address = State()
    broadcast_waiting = State()
    enter_crypto_address = State() # <-- новое состояние
    
    # новые состояния для CRUD реквизитов
    add_bank_name = State()
    add_requisites = State()
    edit_select = State()
    edit_value = State()
    delete_select = State()


class PhoneState(StatesGroup): waiting_phone = State()


# ================== GLOBAL STATE ==================
active_orders = {}      # user_id: message_id
cancel_counts = {}      # user_id: (count, last_cancel_time)
block_until = {}        # user_id: datetime


#=================== бдшка =================
# Создаём БД при запуске бота (один раз)
conn = sqlite3.connect("luck_game.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS luck_attempts (
        user_id INTEGER PRIMARY KEY,
        last_play TIMESTAMP
    )
""")
conn.commit()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS captcha_passed (
        user_id INTEGER PRIMARY KEY,
        passed INTEGER DEFAULT 0
    )
""")
conn.commit()
# ================== BOT ==================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())



#---------------------------Капча--------------------
def generate_captcha():
    captcha_text = ''.join(random.choices(string.digits, k=5))
    image = ImageCaptcha(width=280, height=90)

    image_bytes = io.BytesIO()
    image.write(captcha_text, image_bytes)
    image_bytes.seek(0)

    # ВАЖНО: передаём getvalue(), а не сам BytesIO
    return BufferedInputFile(image_bytes.getvalue(), filename="captcha.png"), captcha_text


####Админка
admin_data = {
    "payment_methods": [
        {"bank_name": "Тинькофф", "requisites": "0000 0000 0000 0000"},
        {"bank_name": "Сбербанк", "requisites": "1111 2222 3333 4444"}
    ],
    "crypto_addresses": {
        "BTC": "bc1qexamplebtcaddress",
        "LTC": "ltc1qexampleltcaddress"
    }
}



admin_main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить реквизиты"), KeyboardButton(text="✏️ Изменить реквизиты")],
        [KeyboardButton(text="🗑 Удалить реквизиты"), KeyboardButton(text="📜 Показать все реквизиты")],
        [KeyboardButton(text="💰 Изменить адрес крипты")],
        [KeyboardButton(text="📢 Рассылка")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)


# Универсальная отмена для всей ветки продажи
@dp.message(
    SellState.choose_coin,
    SellState.enter_rub_amount,
    SellState.choose_payout_method,
    SellState.enter_requisites,
    SellState.enter_bank_name,
    SellState.confirm_sell,
    F.text == "❌ Отмена"
)
async def sell_global_cancel(message: Message, state: FSMContext):
    await state.clear()
    
    # Опционально: удаляем последнее сообщение, чтобы было чище
    try:
        await message.delete()
    except:
        pass
    
    await message.answer(
        "❌ Операция отменена",
        reply_markup=main_keyboard
    )

@dp.message(F.text == "/admin")
async def admin_entry(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return  # тихо игнорируем

    await state.clear()
    await message.answer(
        "<b>Welcome, админ 👑</b>\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard
    )

@dp.message(F.text == "/clear")
async def clear_fsm(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ Состояние сброшено")
    
# Inline-кнопка отмены — можно вынести в отдельную переменную для удобства
cancel_inline = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel_add_requisites")]
    ]
)


@dp.message(F.text == "➕ Добавить реквизиты")
async def admin_add_requisites(message: Message, state: FSMContext):
    await message.answer(
        "Введите название банка:",
        reply_markup=cancel_inline
    )
    await state.set_state(AdminState.add_bank_name)


@dp.message(AdminState.add_bank_name)
async def admin_add_bank(message: Message, state: FSMContext):
    # Сохраняем название банка
    await state.update_data(bank_name=message.text.strip())
    
    await message.answer(
        "Введите реквизиты:",
        reply_markup=cancel_inline  # снова показываем inline-отмену
    )
    await state.set_state(AdminState.add_requisites)


@dp.message(AdminState.add_requisites)
async def admin_save_requisites(message: Message, state: FSMContext):
    data = await state.get_data()
    bank_name = data.get("bank_name", "—")
    requisites = message.text.strip()

    # Добавляем в список
    admin_data["payment_methods"].append({"bank_name": bank_name, "requisites": requisites})

    await message.answer(
        f"✅ Добавлено успешно!\n\n"
        f"🏦 Банк: <b>{bank_name}</b>\n"
        f"💳 Реквизиты: <code>{requisites}</code>",
        reply_markup=admin_main_keyboard
    )
    await state.clear()


# Обработчик inline-кнопки отмены (один на весь процесс добавления)
@dp.callback_query(F.data == "admin_cancel_add_requisites")
async def admin_cancel_add_requisites(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    try:
        # Редактируем текущее сообщение (где пользователь вводил)
        await callback.message.edit_text(
            "❌ Добавление реквизитов отменено",
            reply_markup=None
        )
        # Даём немного времени посмотреть на сообщение
        await asyncio.sleep(1.5)
        await callback.message.delete()
    except Exception:
        # Если не получилось отредактировать/удалить — просто продолжаем
        pass

    await callback.message.answer(
        "Вернулись в админ-меню",
        reply_markup=admin_main_keyboard
    )
    
    await callback.answer("Отменено ✓")

# 1. Кнопка в админ-меню запускает процесс
@dp.message(F.text == "💰 Изменить адрес крипты")
async def admin_edit_crypto(message: Message, state: FSMContext):
    current = (
        f"₿ BTC: <code>{admin_data['crypto_addresses']['BTC']}</code>\n"
        f"Ł LTC: <code>{admin_data['crypto_addresses']['LTC']}</code>"
    )
    await message.answer(
        f"<b>Текущие адреса:</b>\n\n{current}\n\n"
        f"Выберите валюту для изменения:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="BTC"), KeyboardButton(text="LTC")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await state.set_state(AdminState.change_crypto_address)


# 2. Пользователь выбрал валюту (BTC или LTC)
@dp.message(AdminState.change_crypto_address)
async def crypto_field_selected(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("⬅️ Назад", reply_markup=admin_main_keyboard)
        return

    if message.text in ["BTC", "LTC"]:
        await state.update_data(coin=message.text)
        await message.answer(
            f"Введите новый адрес для {message.text}:",
            reply_markup=cancel_keyboard   # ← здесь должна быть клавиатура отмены
        )
        await state.set_state(AdminState.enter_crypto_address)
    else:
        await message.answer("Выберите BTC или LTC")


# 3. Пользователь ввёл новый адрес → сохраняем
@dp.message(AdminState.enter_crypto_address)
async def crypto_address_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    coin = data.get("coin")
    address = message.text.strip()

    # Самое важное место — здесь происходит изменение
    admin_data["crypto_addresses"][coin] = address

    await message.answer(
        f"✅ Адрес {coin} обновлён:\n<code>{address}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard
    )
    await state.clear()

@dp.message(F.text == "✏️ Изменить реквизиты")
async def admin_edit_requisites(message: Message, state: FSMContext):
    if not admin_data["payment_methods"]:
        await message.answer("❌ Список реквизитов пуст", reply_markup=admin_main_keyboard)
        return

    text = "\n".join([f"{i+1}. {m['bank_name']} — {m['requisites']}" for i, m in enumerate(admin_data["payment_methods"])])

    cancel_inline = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_cancel_edit")]
        ]
    )

    await message.answer(
        f"Выберите номер реквизита для изменения:\n\n{text}",
        reply_markup=cancel_inline
    )
    await state.set_state(AdminState.edit_select)


@dp.callback_query(F.data == "admin_cancel_edit")
async def admin_inline_cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("❌ Изменение отменено")
        await asyncio.sleep(1.2)
        await callback.message.delete()
    except:
        pass

    await callback.message.answer(
        "Вернулись в админ-меню",
        reply_markup=admin_main_keyboard
    )
    await callback.answer()

@dp.message(AdminState.choose_requisite_field)
async def admin_enter_bank(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
        if idx < 0 or idx >= len(admin_data["payment_methods"]):
            raise ValueError
        await state.update_data(edit_index=idx)
        await message.answer(
            f"Вы выбрали: {admin_data['payment_methods'][idx]['bank_name']} — {admin_data['payment_methods'][idx]['requisites']}\n\nВведите новое название банка:",
            parse_mode="HTML",
            reply_markup=cancel_keyboard
        )
        await state.set_state(AdminState.enter_requisite_value)
    except:
        await message.answer("❌ Введите корректный номер!")


@dp.message(AdminState.enter_requisite_value)
async def admin_enter_requisites(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("edit_index")
    bank_name = message.text.strip()

    await state.update_data(bank_name=bank_name)
    await message.answer(
        f"Название банка обновлено: <b>{bank_name}</b>\nТеперь введите новые реквизиты:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard
    )
    await state.set_state(AdminState.edit_value)


@dp.message(AdminState.edit_value)
async def admin_save_requisites(message: Message, state: FSMContext):
    data = await state.get_data()
    idx = data.get("edit_index")
    bank_name = data.get("bank_name")
    requisites = message.text.strip()

    admin_data["payment_methods"][idx]["bank_name"] = bank_name
    admin_data["payment_methods"][idx]["requisites"] = requisites

    await message.answer(
        f"✅ Обновлено:\n🏦 Банк: <b>{bank_name}</b>\n💳 Реквизиты: <code>{requisites}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard
    )
    await state.clear()

@dp.message(AdminState.delete_select, F.text == "❌ Отмена")
async def admin_delete_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Удаление отменено", reply_markup=admin_main_keyboard)

@dp.message(F.text == "🗑 Удалить реквизиты")
async def admin_delete_requisites(message: Message, state: FSMContext):
    if not admin_data["payment_methods"]:
        await message.answer("❌ Список пуст", reply_markup=admin_main_keyboard)
        return
        
    text = "\n".join([f"{i+1}. {m['bank_name']} — {m['requisites']}" for i, m in enumerate(admin_data["payment_methods"])])

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_cancel_delete")]
        ]
    )

    await message.answer(
        f"Выберите номер для удаления:\n\n{text}",
        reply_markup=kb
    )
    
    await state.set_state(AdminState.delete_select)


@dp.callback_query(F.data == "admin_cancel_delete")
async def admin_cancel_delete(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text("❌ Удаление отменено")
        await asyncio.sleep(1)
        await callback.message.delete()
    except:
        pass
        
    await callback.message.answer(
        "Вернулись в админ-меню",
        reply_markup=admin_main_keyboard
    )
    await callback.answer()

@dp.message(AdminState.delete_select)
async def admin_delete_select(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
        removed = admin_data["payment_methods"].pop(idx)
        await message.answer(f"🗑 Удалено: {removed['bank_name']} — {removed['requisites']}", reply_markup=admin_main_keyboard)
        await state.clear()
    except:
        await message.answer("Введите корректный номер!")

@dp.message(F.text == "📜 Показать все реквизиты")
async def admin_show_requisites(message: Message, state: FSMContext):
    if not admin_data["payment_methods"]:
        await message.answer("❌ Список пуст", reply_markup=admin_main_keyboard)
        return
    text = "\n".join([f"{i+1}. {m['bank_name']} — {m['requisites']}" for i, m in enumerate(admin_data["payment_methods"])])
    await message.answer(f"📜 Все реквизиты:\n\n{text}", reply_markup=admin_main_keyboard)


@dp.message(AdminState.enter_requisite_value)
async def requisites_value_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("field")
    value = message.text.strip()

    admin_data["payment_methods"][field] = value
    await message.answer(f"✅ Обновлено:\n<code>{value}</code>", parse_mode="HTML", reply_markup=admin_main_keyboard)
    await state.clear()

@dp.message(F.text == "💰 Изменить адресс крипты")
async def admin_edit_crypto(message: Message, state: FSMContext):
    current = (
        f"₿ BTC: <code>{admin_data['crypto_addresses']['BTC']}</code>\n"
        f"Ł LTC: <code>{admin_data['crypto_addresses']['LTC']}</code>"
    )
    await message.answer(
        f"<b>Текущие адреса:</b>\n\n{current}\n\nВыберите валюту для изменения:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="BTC"), KeyboardButton(text="LTC")],
                [KeyboardButton(text="⬅️ Назад")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True # <-- добавь
        )
    )
    await state.set_state(AdminState.change_crypto_address)


@dp.message(AdminState.change_crypto_address)
async def crypto_field_selected(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await message.answer("⬅️ Назад", reply_markup=admin_main_keyboard)
        return

    if message.text in ["BTC", "LTC"]:
        await state.update_data(coin=message.text)
        await message.answer(f"Введите новый адрес для {message.text}:", reply_markup=cancel_keyboard)
        await state.set_state(AdminState.enter_crypto_address)


@dp.message(AdminState.enter_crypto_address)
async def crypto_address_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    coin = data.get("coin")
    address = message.text.strip()

    admin_data["crypto_addresses"][coin] = address
    await message.answer(
        f"✅ Адрес {coin} обновлён:\n<code>{address}</code>",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard
    )
    await state.clear()



@dp.message(F.text == "📢 Рассылка")
async def broadcast_start(message: Message, state: FSMContext):
    await message.answer("Введите текст или фото для рассылки:", reply_markup=cancel_keyboard)
    await state.set_state(AdminState.broadcast_waiting)

@dp.message(AdminState.broadcast_waiting)
async def broadcast_send(message: Message, state: FSMContext):
    # TODO: получить список user_id из БД
    user_ids = [ADMIN_ID]  # временно только себе

    for uid in user_ids:
        try:
            if message.photo:
                photo_id = message.photo[-1].file_id
                await bot.send_photo(chat_id=uid, photo=photo_id, caption=message.caption or "")
            else:
                await bot.send_message(chat_id=uid, text=message.text)
        except:
            continue

    await message.answer("✅ Рассылка завершена", reply_markup=admin_main_keyboard)
    await state.clear()

@dp.message(F.text == "⬅️ Назад")
async def admin_back(message: Message, state: FSMContext):
    await state.clear()
    photo = FSInputFile("media/start.jpg")
    await message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )




# ================== KEYBOARDS ==================
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💱 Обменять крипту")],
        [KeyboardButton(text="📈 Купить"), KeyboardButton(text="📉 Продать")],
        [KeyboardButton(text="🎰 Испытай удачу"), KeyboardButton(text="🧮 Калькулятор")],
        [
            KeyboardButton(text="📜 Инструкция"),
            KeyboardButton(text="⭐ Отзывы")
        ],  # ← две кнопки в одной строке
        [KeyboardButton(text="💻 Личный кабинет"), KeyboardButton(text="📱 Контакты")],
    ],
    resize_keyboard=True,
)

exchange_direction_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="₿ BTC → USDT")],
        [KeyboardButton(text="Ł LTC → USDT")],
        [KeyboardButton(text="⬅ Назад")],
    ],
    resize_keyboard=True,
    
)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Отмена")],
    ]
)

coin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="₿ BTC"), KeyboardButton(text="Ł LTC")],
        [KeyboardButton(text="❌ Отмена")],
    ]
)

next_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Далее ➡️", callback_data="next_step")]
    ]
)

@dp.message(F.text == "⬅ Назад")
async def back_to_menu(message: Message, state: FSMContext):
    await state.clear()
    photo = FSInputFile("media/start.jpg")
    await message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )


# ================== HANDLERS ==================
@dp.message(F.text == "💱 Обменять крипту")
async def exchange_handler(message: Message):
    photo = FSInputFile("media/obmen.jpg")
    await message.answer_photo(
        photo=photo,
        caption="Выберите направление обмена:",
        reply_markup=exchange_direction_keyboard
    )

@dp.message(F.text.in_(["₿ BTC → USDT", "Ł LTC → USDT"]))
async def direction_selected(message: Message, state: FSMContext):
    await message.answer(
        text=(
            "📝 <b>Комиссия сервиса: 1.2% + комиссия сети</b>\n\n"
            "<b>Минимальная сумма = 0.00025 BTC</b>\n"
            "<b>Максимальная сумма = 0.035 BTC</b>\n\n"
            "Платежи меньше минимального игнорируются, не могут быть возвращены отправителю и не подлежат обмену.\n"
            "Любые платежи меньше минимального депозита считаются пожертвованием в пользу Хоттабыча.\n\n"
            "<b>Введите сумму BTC для обмена:</b>"
        ),
        reply_markup=cancel_keyboard
    )
    # переводим пользователя в состояние ввода суммы
    await state.set_state(ExchangeState.enter_amount)

# 1. Специфический обработчик отмены — должен идти ПЕРВЫМ!
@dp.message(ExchangeState.enter_amount, F.text == "❌ Отмена")
async def exchange_cancel(message: Message, state: FSMContext):
    await state.clear()
    
    # Удаляем сообщение с запросом суммы (чтобы чат был чистым)
    try:
        await message.delete()
    except:
        pass
    
    # Красивый возврат в главное меню
    photo = FSInputFile("media/start.jpg")
    await message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>\n\n",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )


# 2. Общий обработчик ввода суммы (теперь он не перехватывает отмену)
@dp.message(ExchangeState.enter_amount)
async def exchange_amount_handler(message: Message, state: FSMContext):
    # Дополнительная защита: если вдруг отмену пропустили
    if message.text.strip() == "❌ Отмена":
        await exchange_cancel(message, state)
        return

    # Основная логика ввода суммы
    await message.answer(
        "⛔️ В данный момент идет пополнение резерва по этому направлению,\n"
        "попробуйте позже или обратитесь в поддержку.\n"
        f"Поддержка: {SUPPORT_USER}",
        reply_markup=cancel_keyboard  # оставляем клавиатуру отмены
    )

# ================== BUY ==================
coin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔄 Купить BTC"), KeyboardButton(text="🔄 Купить LTC")],  # рядом в одной строке
        [KeyboardButton(text="⬅️ Назад")]                             # отдельно внизу
    ],
    resize_keyboard=True,        # делает кнопки обычного размера (не огромные)
    input_field_placeholder="Выберите валюту"  # подсказка в поле ввода (опционально, красиво)
)
@dp.message(F.text == "📈 Купить")
async def buy_start(message: Message, state: FSMContext):
    photo = FSInputFile("media/buy.jpg")
    await message.answer_photo(
        photo=photo,
        caption="Выберите валюту",
        reply_markup=coin_keyboard
    )
    await state.set_state(BuyState.choose_coin)


@dp.message(BuyState.choose_coin, F.text.in_(["🔄 Купить BTC", "🔄 Купить LTC"]))
async def buy_coin_selected(message: Message, state: FSMContext):
    coin = "BTC" if "BTC" in message.text else "LTC"

    await state.update_data(coin=coin)
    await state.set_state(BuyState.enter_amount)

    photo = FSInputFile("media/summa.jpg")
    # Первое сообщение с фото и основной инструкцией
    await message.answer_photo(
        photo=photo,
        caption=f"💰 Введи нужную сумму в <b>{coin}</b> или в <b>RUB</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )

    # Второе сообщение — отдельная подсказка
    await message.answer(
        "Например: <b>0.00041</b> или <b>1500</b>",
        parse_mode="HTML"
    )



@dp.message(BuyState.choose_coin, F.text == "⬅️ Назад")
async def buy_cancel_coin(message: Message, state: FSMContext):
    await state.clear()
    photo = FSInputFile("media/start.jpg")  # картинка старта
    await message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )
def format_crypto(amount: float) -> str:
    # округляем до 8 знаков, убираем хвостовые нули и точку
    return f"{amount:.8f}".rstrip("0").rstrip(".")



@dp.message(BuyState.enter_amount)
async def buy_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    coin = data.get("coin")
    text = message.text.replace(",", ".").strip()

    try:
        value = float(text.split()[0])
    except ValueError:
        await message.answer("Введите корректную сумму (в RUB или крипте)")
        return

    rate = BTC_BUY if coin == "BTC" else LTC_BUY
    markup_percent = 29.3
    discount_percent = 5

    if value < 1:  # пользователь ввёл крипту
        crypto_amount = value
        base_rub = crypto_amount * rate
        base_rub = base_rub * (1 + markup_percent / 100)
        discount = base_rub * (discount_percent / 100)
        final_rub = int(base_rub - discount)
    elif value >= MIN_RUB:  # пользователь ввёл рубли
        rub_amount = value
        base_rub = rub_amount * (1 + markup_percent / 100)
        discount = base_rub * (discount_percent / 100)
        final_rub = int(base_rub - discount)
        crypto_amount = round(final_rub / rate, 8)
    else:
        await message.answer(
            f"❌ Введите сумму в крипте (<1 {coin}) или в рублях (≥{int(MIN_RUB)} RUB)"
        )
        return

    await state.update_data(
        base_rub=base_rub,
        discount=discount,
        final_rub=final_rub,
        rub_amount=final_rub,
        crypto_amount=crypto_amount,
        coin=coin
    )

    buttons = []
    for i, method in enumerate(admin_data["payment_methods"]):
        buttons.append([
            InlineKeyboardButton(
                text=f"{method['bank_name']} ({final_rub} руб.)",
                callback_data=f"pay_{i}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    payment_keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    # Сначала сообщение с кнопками
    await message.answer(
        f"Получите: <b>{format_crypto(crypto_amount)}</b> <b>{coin}</b>\n"
        f"Скидка: <b>{int(discount)} ₽</b>\n\n"
        f"<u>Выберите способ оплаты ⬇️</u>",
        parse_mode="HTML",
        reply_markup=payment_keyboard
    )

    # Сразу следом отдельное сообщение (останется даже после удаления кнопок)
    await message.answer("🔮ХОТТАБЫЧ🔮")

@dp.callback_query(F.data == "cancel")
async def cancel_to_start_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()  # Очищаем состояние
    
    try:
        # Удаляем сообщение с кнопками
        await callback.message.delete()
    except:
        pass
    
    # Отправляем стартовое сообщение с фото
    photo = FSInputFile("media/start.jpg")
    await callback.message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )
@dp.callback_query(F.data.startswith("pay_"))
async def process_payment_choice(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    base_rub = data["base_rub"]
    discount = data["discount"]
    final_rub = data["final_rub"]
    crypto_amount = data["crypto_amount"]
    coin = data["coin"]

    # получаем индекс выбранного реквизита
    idx = int(callback.data.replace("pay_", ""))
    method = admin_data["payment_methods"][idx]

    # сохраняем в state выбранный банк и реквизиты
    await state.update_data(
        payout_method=method["bank_name"],
        requisites=method["requisites"]
    )

    # удаляем предыдущее сообщение с кнопками
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    except:
        pass

    # сообщение с расчётом + кнопка "Далее ➡️"
    await callback.message.answer(
        f"Получите: <b>{format_crypto(crypto_amount)}</b> <b>{coin}</b>\n"
        f"Скидка: <b>{int(discount)} ₽</b>\n"
        f"К оплате: <s>{int(base_rub)} ₽</s> → <code><b>{final_rub} ₽</b></code>",
        parse_mode="HTML",
        reply_markup=next_keyboard
    )

@dp.callback_query(F.data == "next_step")
async def process_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    coin = data.get("coin")

    cancel_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    await callback.message.answer(
        f"Введите свой <b>{coin}</b> адрес:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard
    )

    await state.set_state(BuyState.enter_wallet)


import uuid



# Кнопки для покупки
buy_pay_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="buy_paid")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="buy_cancel")]
    ]
)


# Обработка кнопки "Оплатил"
@dp.callback_query(F.data == "buy_paid")
async def buy_paid(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📎 Пришлите скриншот или документ (PDF/JPG/PNG) подтверждающий оплату ⬇️",
        parse_mode="HTML"
    )
    await state.set_state(BuyState.waiting_proof)


# В wallet_entered добавляем сохранение в state
@dp.message(BuyState.enter_wallet)
async def wallet_entered(message: Message, state: FSMContext):
    user_id = message.from_user.id
    wallet_address = message.text.strip()
    data = await state.get_data()
    coin = data.get("coin")
    payout_method = data.get("payout_method", "card")
    # проверки отмен/блокировок
    if user_id in block_until and datetime.now() < block_until[user_id]:
        remaining = int((block_until[user_id] - datetime.now()).total_seconds() // 60)
        await message.answer(
            f"⛔️ У вас слишком много отменённых заявок.\n"
            f"Подождите {remaining} минут перед новой сделкой."
        )
        await state.clear()
        return
    # проверка активной заявки
    if user_id in active_orders:
        await message.answer(
            "У вас уже есть активная заявка на оплату.\n"
            "Дождитесь её завершения или отмените:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❌ Отменить заявку",
                            callback_data=f"cancel_{active_orders[user_id]}"
                        )
                    ]
                ]
            )
        )
        return
    if wallet_address == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Операция отменена", reply_markup=main_keyboard)
        return
    await state.update_data(wallet=wallet_address)
    await message.answer("⏳ Идет подбор реквизитов...")
    await asyncio.sleep(random.randint(5, 10))
    # генерим ID оплаты
    pay_id = str(uuid.uuid4())[:6]
    pay_sum = data.get("rub_amount")
    crypto_amount = data.get("crypto_amount")
    if pay_sum is None or crypto_amount is None:
        await message.answer("❌ Ошибка: сумма сделки не найдена. Введите сумму заново.", reply_markup=main_keyboard)
        await state.set_state(BuyState.enter_amount)
        return
    bank_name = data.get("payout_method") # название банка, выбранное пользователем
    requisites = data.get("requisites") # реквизиты, выбранные пользователем
    formatted_req = " ".join([requisites[i:i+4] for i in range(0, len(requisites), 4)])
    pay_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_{pay_id}")],
            [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=f"cancel_{pay_id}")]
        ]
    )
    # Сохраняем в state
    await state.update_data(
        pay_id=pay_id,
        pay_sum=pay_sum,
        formatted_req=formatted_req
    )
    ...
    # сначала предупреждение
    await message.answer(
        "❗️Будьте внимательны❗️\n\n"
        "- ПЕРЕВОД НА ДРУГОЙ БАНК;\n"
        "- ПЕРЕВОД НЕВЕРНОЙ СУММЫ;\n"
        "- ПОЗДНИЙ ПЕРЕВОД СРЕДСТВ.\n\n"
        "❗️Вышеперечисленные действия приведут К ПОТЕРЕ СРЕДСТВ❗️",
        parse_mode="HTML"
    )

    # потом сообщение с реквизитами и кнопками
    payment_message = await message.answer(
        f"Перевод: <b>{bank_name}</b>\n"
        f"ID оплаты: <code>{pay_id}</code>\n"
        f"Реквизиты: <code>{formatted_req}</code>\n"
        f"Сумма к оплате: <b>{pay_sum} RUB</b>\n"
        f"К получению: <b>{format_crypto(crypto_amount)} {coin}</b>\n"
        f"На кошелек: <code>{wallet_address}</code>\n\n"
        f"⚠️ Внимание: Переводить точную сумму!\n"
        f"🧾 После оплаты нажмите \n"
        f"✅ Я оплатил\n\n"
        f"⏱️ На оплату даётся <b>25</b> мин!",
        parse_mode="HTML",
        reply_markup=pay_keyboard
    )

    # сохраняем в state
    await state.update_data(payment_msg_id=payment_message.message_id)

@dp.callback_query(F.data.startswith("cancel_"))
async def buy_cancel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    msg_id = None
    if len(parts) > 1:
        try:
            msg_id = int(parts[1])
        except ValueError:
            pass  # если pay_id не int, игнорируем
    await callback.answer("Заявка отменена")
    await state.clear()
    # Удаляем callback message
    try:
        await callback.message.delete()
    except:
        pass
    # Если есть msg_id (для активной заявки), удаляем payment message
    if msg_id:
        try:
            await bot.delete_message(user_id, msg_id)
        except:
            pass
    # Отправляем start фото
    photo = FSInputFile("media/start.jpg")
    await callback.message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )
    # Логика счётчика отмен
    if user_id in cancel_counts:
        count, _ = cancel_counts[user_id]
        cancel_counts[user_id] = (count + 1, datetime.now())
        if count + 1 >= 3:
            block_until[user_id] = datetime.now() + timedelta(hours=1)
            await callback.message.answer("❌ Слишком много отмен — новый заказ через 1 час.")
    else:
        cancel_counts[user_id] = (1, datetime.now())
    if user_id in active_orders:
        del active_orders[user_id]

@dp.callback_query(F.data.startswith("paid_"))
async def buy_paid(callback: CallbackQuery, state: FSMContext):
    # убираем клавиатуру у сообщения с реквизитами
    try:
        await bot.edit_message_reply_markup(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=None
        )
    except Exception as e:
        print("Не удалось убрать клавиатуру:", e)

    # теперь просим доказательство
    await callback.message.answer(
        "📎 Пришлите скриншот или документ (PDF/JPG/PNG) подтверждающий оплату ⬇️",
        parse_mode="HTML"
    )
    await state.set_state(BuyState.waiting_proof)

@dp.message(BuyState.waiting_proof, F.photo | F.document)
async def buy_proof_received(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    pay_id = data.get("pay_id", "—")
    pay_sum = data.get("pay_sum", "—")
    crypto_amount = format_crypto(data.get("crypto_amount", "—"), 8 if data.get("coin") == "BTC" else 4)
    coin = data.get("coin", "—")
    wallet_address = data.get("wallet", "—")
    payout_method = data.get("payout_method", "—")
    formatted_req = data.get("formatted_req", "—")
    caption = (
        f"✅ <b>Оплаченная заявка (Покупка)</b>\n\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"🆔 ID оплаты: <code>{pay_id}</code>\n"
        f"💵 Сумма: <b>{pay_sum} RUB</b>\n"
        f"📥 К получению: <b>{crypto_amount} {coin}</b>\n"
        f"📋 Метод оплаты: <b>{payout_method.upper()}</b>\n"
        f"🏦 Адрес кошелька: <code>{wallet_address}</code>\n"
        f"📑 Реквизиты: <code>{formatted_req}</code>"
    )
    if message.photo:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=caption, parse_mode="HTML")
    elif message.document:
        await bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id, caption=caption, parse_mode="HTML")
    await message.answer("✅ Оплата принята, оператор свяжется с вами!", reply_markup=main_keyboard)
    await state.clear()
    if user_id in active_orders:
        del active_orders[user_id]

# запускаем таймер, используя сохранённый ID
    if payment_msg_id:
        try:
            msg = await bot.edit_message_text(
                chat_id=user_id,
                message_id=payment_msg_id,
                text="⏳ Запущен таймер оплаты...",
                parse_mode="HTML"
            )
            active_orders[user_id] = payment_msg_id
            asyncio.create_task(countdown_task(
                msg=msg,
                user_id=user_id,
                pay_id=pay_id,
                pay_sum=pay_sum,
                crypto_amount=crypto_amount,
                coin=coin,
                wallet_address=wallet_address,
                requisites=formatted_req,
                payout_method=payout_method
            ))
        except Exception as e:
            print("Ошибка запуска таймера:", e)



async def countdown_task(msg: Message, user_id: int, pay_id: str,
                         pay_sum: int, crypto_amount: float,
                         coin: str, wallet_address: str,
                         requisites: str, payout_method: str):
    minutes_left = 25

    def get_text(minutes: int) -> str:
        trick = "\u200B" * ((minutes % 10) + 1)
        return (
            f"Перевод: <b>{payout_method.upper()}</b>\n"
            f"ID оплаты: <code>{pay_id}</code>\n"
            f"Реквизиты: <code>{requisites}</code>\n"
            f"Сумма к оплате: <b>{pay_sum} RUB</b>\n"
            f"К получению: <b>{format_crypto(crypto_amount)} {coin}</b>\n"
            f"На кошелек: <b>{wallet_address}</b>\n\n"
            f"⚠️ Внимание: Переводить точную сумму!\n"
            f"🧾 После оплаты нажмите \n"
            f"\"✅ Я оплатил\"\n\n"
            f"⏱️ На оплату даётся <b>{minutes}</b> мин!{trick}"
        )

    while minutes_left > 0:
        try:
            await msg.edit_text(
                get_text(minutes_left),
                parse_mode="HTML",
                reply_markup=msg.reply_markup
            )
        except:
            break
        await asyncio.sleep(60)
        minutes_left -= 1

    try:
        await msg.edit_text(
            f"⛔️ Время оплаты истекло!\n\n"
            f"Заявка <code>{pay_id}</code> закрыта.",
            parse_mode="HTML"
        )
    except:
        pass

    if user_id in active_orders:
        del active_orders[user_id]




@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_payment(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Показываем короткое уведомление (чтобы пользователь понял, что клик сработал)
    await callback.answer("Заявка отменена", show_alert=False)
    
    # Очищаем состояние FSM
    await state.clear()
    
    # Удаляем сообщение с реквизитами/кнопками (чтобы чат стал чистым)
    try:
        await callback.message.delete()
    except:
        pass  # если удалить не удалось — ничего страшного
    
    # Жёстко кидаем в главное меню со стартовым фото и текстом
    photo = FSInputFile("media/start.jpg")
    await callback.message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>\n\n"
                "Заявка на покупку отменена.\n"
                "Вы вернулись в главное меню.",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )
    # Увеличиваем счётчик отмен
    if user_id in cancel_counts:
        count, _ = cancel_counts[user_id]
        cancel_counts[user_id] = (count + 1, datetime.now())
        if count + 1 >= 3:
            block_until[user_id] = datetime.now() + timedelta(hours=1)
            await callback.message.edit_text("❌ Заявка отменена.\n⛔️ Слишком много отмен — новый заказ через 1 час.")
    else:
        cancel_counts[user_id] = (1, datetime.now())
        await callback.message.edit_text("❌ Заявка отменена.")

    await state.clear()
    if user_id in active_orders:
        del active_orders[user_id]




    # генерим номер заявки
    status_id = "№" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", k=18))
    data = await state.get_data()
    rub_amount = data.get("rub_amount")
    crypto_amount = data.get("crypto_amount")
    coin = data.get("coin")
    pay_id = data.get("pay_id", "—")
    wallet_address = data.get("wallet", "—")
    payout_method = data.get("payout_method", "—")

    # убираем кнопки
    await callback.message.edit_reply_markup(reply_markup=None)

    # финальное сообщение пользователю
    await callback.message.answer(
        f"🗳 Заявка: <code>{status_id}</code>\n\n"
        f"⏳ <b>Статус: обрабатывается...</b>\n"
        f"💵 <b>Сумма внесения: {rub_amount} RUB</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )


    await bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="HTML")

    await state.clear()
    if user_id in active_orders:
        del active_orders[user_id]


# ================== SELL ==================
# ================== SELL KEYBOARDS ==================
sell_coin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Продать BTC"), KeyboardButton(text="Продать LTC")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

payout_method_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Номер карты", callback_data="payout_card"),
            InlineKeyboardButton(text="СБП", callback_data="payout_sbp")
        ]
    ]
)

confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Продолжить"), KeyboardButton(text="❌ Отменить")]
    ],
    resize_keyboard=True
)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отменить")]],
    resize_keyboard=True
)


# ================== SELL STATES ==================
class SellState(StatesGroup):
    choose_coin = State()
    enter_rub_amount = State()
    choose_payout_method = State()
    enter_requisites = State()      # общий для карты и СБП
    enter_bank_name = State()
    confirm_sell = State()
    waiting_proof = State()
    confirm_sell_cancel = State() # <-- новое состояние


# ================== SELL HANDLERS ==================

@dp.message(F.text == "📉 Продать")
async def sell_start(message: Message, state: FSMContext):
    photo = FSInputFile("media/sell.jpg")
    await message.answer_photo(
        photo=photo,
        caption="Выберите валюту",
        reply_markup=sell_coin_keyboard
    )
    await state.set_state(SellState.choose_coin)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

@dp.message(SellState.choose_coin, F.text.in_(["Продать BTC", "Продать LTC"]))
async def sell_coin_selected(message: Message, state: FSMContext):
    coin = "BTC" if "BTC" in message.text else "LTC"
    await state.update_data(coin=coin)

    photo_path = "media/btc.jpg" if coin == "BTC" else "media/ltc.jpg"
    photo = FSInputFile(photo_path)

    # Формируем подпись динамически
    caption_text = (
        f"<b>ВВЕДИ СУММУ В {coin}:</b>\n"
        f"<i>пример: 1</i>"
    )

    await message.answer_photo(
        photo=photo,
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=cancel_keyboard
    )

    await state.set_state(SellState.enter_rub_amount)



@dp.message(SellState.choose_coin, F.text == "⬅️ Назад")
async def sell_back_from_coin(message: Message, state: FSMContext):
    await state.clear()
    photo = FSInputFile("media/start.jpg")
    await message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )



@dp.message(SellState.enter_rub_amount, F.text == "❌ Отмена")
async def sell_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отмена", reply_markup=main_keyboard)


def format_crypto(amount: float, precision: int = 8) -> str:
    """
    Форматирует число с заданной точностью, убирая хвостовые нули и точку.
    """
    try:
        return f"{float(amount):.{precision}f}".rstrip("0").rstrip(".")
    except Exception:
        return str(amount)

cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

# Клавиатура отмены (должна быть определена один раз в начале файла)
cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)


# 1. Выбор монеты → запрашиваем сумму
@dp.message(SellState.choose_coin, F.text.in_(["Продать BTC", "Продать LTC"]))
async def sell_coin_selected(message: Message, state: FSMContext):
    coin = "BTC" if "BTC" in message.text else "LTC"
    await state.update_data(coin=coin)

    photo_path = "media/btc.jpg" if coin == "BTC" else "media/ltc.jpg"
    photo = FSInputFile(photo_path)

    caption_text = (
        f"<b>ВВЕДИ СУММУ В {coin}:</b>\n"
        f"<i>пример: 1</i> или 1500 RUB\n\n"
        f"Для отмены нажмите кнопку внизу ↓"
    )

    await message.answer_photo(
        photo=photo,
        caption=caption_text,
        parse_mode="HTML",
        reply_markup=cancel_keyboard  # ← отмена здесь
    )

    await state.set_state(SellState.enter_rub_amount)


# 2. Ввод суммы (самый проблемный шаг)
@dp.message(SellState.enter_rub_amount)
async def sell_rub_amount_entered(message: Message, state: FSMContext):
    # Проверяем отмену ПЕРВОЙ
    if message.text.strip() == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Операция отменена", reply_markup=main_keyboard)
        return

    text = message.text.replace(",", ".").strip()

    data = await state.get_data()
    coin = data.get("coin")
    sell_rate = BTC_SELL if coin == "BTC" else LTC_SELL

    try:
        value = float(text.split()[0])

        if value < 200:
            crypto_amount = value
            rub_amount = int(crypto_amount * sell_rate)
            if rub_amount < 1500:
                await message.answer("❌ Минимальная сумма продажи — 1500 RUB")
                return
        elif value >= 1500:
            rub_amount = value
            crypto_amount = rub_amount / sell_rate
            if rub_amount < 1500:
                await message.answer("❌ Минимальная сумма продажи — 1500 RUB")
                return
        else:
            await message.answer("❌ Введите корректную сумму")
            return

    except ValueError:
        await message.answer("Введите сумму в RUB или LTC (например: 1500 или 0.005)")
        return

    await state.update_data(
        rub_amount=int(rub_amount),
        crypto_amount=crypto_amount
    )

    crypto_str = format_crypto(crypto_amount, 4 if coin == "LTC" else 8)

    payout_method_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Номер карты", callback_data="payout_card")],
            [InlineKeyboardButton(text="СБП", callback_data="payout_sbp")]
        ]
    )

    sent_msg = await message.answer(
        f"За продажу <b>{crypto_str} {coin}</b> "
        f"ты получишь <b>{int(rub_amount)} ₽</b>\n\n"
        "Способ зачисления:",
        parse_mode="HTML",
        reply_markup=payout_method_keyboard
    )

    await state.update_data(sell_msg_id=sent_msg.message_id)

    # Оставляем клавиатуру отмены и после этого шага
    await message.answer("-------------------------------------------------", reply_markup=cancel_keyboard)

    await state.set_state(SellState.choose_payout_method)


# 3. Выбор способа выплаты → запрашиваем реквизиты
@dp.callback_query(SellState.choose_payout_method, F.data.in_(["payout_card", "payout_sbp"]))
async def payout_method_selected(callback: CallbackQuery, state: FSMContext):
    method = "card" if callback.data == "payout_card" else "sbp"
    await state.update_data(payout_method=method)

    data = await state.get_data()
    sell_msg_id = data.get("sell_msg_id")
    if sell_msg_id:
        try:
            await bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=sell_msg_id
            )
        except:
            pass

    text = "⚙️ Введи реквизиты для получения выплаты за продажу\n\n"
    text += "💳 Номер карты:" if method == "card" else "Номер телефона для СБП:"

    await callback.message.answer(
        text,
        reply_markup=cancel_keyboard  # ← отмена здесь
    )

    await state.set_state(SellState.enter_requisites)
    await callback.answer()


# 4. Ввод реквизитов → запрашиваем банк
@dp.message(SellState.enter_requisites)
async def requisites_entered(message: Message, state: FSMContext):
    # Проверяем отмену ПЕРВОЙ
    if message.text.strip() == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Операция отменена", reply_markup=main_keyboard)
        return

    requisites = message.text.strip().replace(" ", "")
    data = await state.get_data()
    method = data["payout_method"]

    if method == "card":
        if not (requisites.isdigit() and len(requisites) in [16, 18, 19]):
            await message.answer("❌ Неверный формат номера карты (16-19 цифр без пробелов)")
            return
    else:
        if not (requisites.isdigit() and len(requisites) in [10, 11]):
            await message.answer("❌ Неверный формат телефона (10-11 цифр)")
            return

    await state.update_data(requisites=requisites)

    await message.answer(
        "🏦 Укажите банк",
        reply_markup=cancel_keyboard  # ← отмена здесь
    )

    await state.set_state(SellState.enter_bank_name)


# 5. Ввод названия банка
@dp.message(SellState.enter_bank_name)
async def bank_name_entered(message: Message, state: FSMContext):
    # Проверяем отмену ПЕРВОЙ
    if message.text.strip() == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Операция отменена", reply_markup=main_keyboard)
        return

    bank_name = message.text.strip()
    if len(bank_name) < 2:
        await message.answer("❌ Название банка слишком короткое")
        return

    data = await state.get_data()
    await state.update_data(bank_name=bank_name)

    formatted_req = " ".join([data["requisites"][i:i+4] for i in range(0, len(data["requisites"]), 4)])

    await message.answer(
        f"К оплате: <b>{data['crypto_amount']:.3f} {data['coin']}</b>\n"
        f"Получишь: <b>{data['rub_amount']} RUB</b>\n"
        f"Реквизиты: <b>{formatted_req} || {bank_name}</b>",
        parse_mode="HTML",
        reply_markup=confirm_keyboard  # здесь уже подтверждение
    )

    await state.set_state(SellState.confirm_sell)

# Уже есть в твоём коде — оставляем как есть
@dp.message(SellState.confirm_sell, F.text == "✅ Продолжить")
async def sell_confirm(message: Message, state: FSMContext):
    await message.answer(
        "⏳ Ожидайте, идет подбор реквизитов...",
        reply_markup=ReplyKeyboardRemove()
    )
    await asyncio.sleep(random.randint(1, 2))

    data = await state.get_data()
    coin = data["coin"]

    pay_id = "#" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", k=18))
    sell_address = admin_data["crypto_addresses"][coin]
    crypto_amount = round(data["crypto_amount"], 3)
    rub_amount = data["rub_amount"]

    pay_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="sell_paid")],
            [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="sell_cancel")]
        ]
    )

    await message.answer(
        f"Заявка <b>{pay_id}</b>\n\n"
        f"⚠️ ВАЖНО ПЕРЕВОДИТЬ ТОЧНУЮ СУММУ УКАЗАННУЮ БОТОМ\n\n"
        f"👇👇👇👇👇👇👇👇\n\n"
        f"Переведите <code>{crypto_amount:.3f}</code> {coin} на адрес :\n"
        f"<code>{sell_address}</code>\n\n"
        f"👆👆👆👆👆👆👆👆\n\n"
        f"⚠️ На перевод даётся 60 мин.\n\n"
        f"💳 Средства будут зачислены после 1 подтверждения сети",
        parse_mode="HTML",
        reply_markup=pay_keyboard
    )
    await state.update_data(pay_id=pay_id)


# Самый важный обработчик — именно для кнопки "❌ Отменить" на шаге подтверждения
@dp.message(SellState.confirm_sell, F.text == "❌ Отменить")
async def sell_cancel_confirm(message: Message, state: FSMContext):
    await state.clear()
    
    try:
        await message.delete()
    except:
        pass
    
    photo = FSInputFile("media/start.jpg")
    await message.answer_photo(
        photo=photo,
        caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>\n\n"
                "Заявка на продажу отменена.\n"
                "Вы вернулись в главное меню.",
        parse_mode="HTML",
        reply_markup=main_keyboard
    )

@dp.callback_query(F.data == "sell_paid")
async def sell_paid(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📎 Пришлите скриншот или документ (PDF/JPG/PNG) подтверждающий оплату ⬇️",
        parse_mode="HTML"
    )
    await state.set_state(SellState.waiting_proof)


@dp.message(SellState.waiting_proof, F.photo | F.document)
async def sell_proof_received(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    pay_id = data.get("pay_id", "—")
    coin = data.get("coin", "—")
    rub_amount = data.get("rub_amount", "—")
    requisites = data.get("requisites", "—")
    payout_method = data.get("payout_method", "—")

    caption = (
        f"✅ <b>Подтверждение оплаты (Продажа)</b>\n\n"
        f"👤 Пользователь: <code>{user_id}</code>\n"
        f"🆔 ID заявки: <code>{pay_id}</code>\n"
        f"💵 Сумма: <b>{rub_amount} RUB</b>\n"
        f"📥 Валюта: <b>{coin}</b>\n"
        f"📋 Метод выплаты: <b>{payout_method.upper()}</b>\n"
        f"🏦 Реквизиты: <code>{requisites}</code>"
    )

    if message.photo:
        await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id,
                             caption=caption, parse_mode="HTML")
    elif message.document:
        await bot.send_document(chat_id=ADMIN_ID, document=message.document.file_id,
                                caption=caption, parse_mode="HTML")

    await message.answer("✅ Оплата принята, оператор свяжется с вами!", reply_markup=main_keyboard)
    await state.clear()

@dp.message(SellState.confirm_sell, F.text == "❌ Отменить заявку")
async def sell_cancel(message: Message, state: FSMContext):
    await state.clear()
    
    await message.answer(
        "❌ Заявка успешно отменена\n\n"
        "Вы вернулись в главное меню",
        reply_markup=main_keyboard
    )


#=================================Личный кабинет===============
@dp.message(F.text == "💻 Личный кабинет")
async def profile_handler(message: Message):
    user_id = message.from_user.id
    
    photo = FSInputFile("media/lk.jpg")
    await message.answer_photo(
        photo=photo,
        caption=(
            f"Ваш уникальный ID: <code>{user_id}</code>\n"
            f"Количество обменов: <b>0</b>\n"
            f"Количество рефералов: <b>0</b>\n"
            f"Уровень реферальной программы: <b>1 уровень</b>\n"
            f"Получаемый процент по реферальной программе: <b>1.0 %</b>\n"
            f"Количество обменов рефералов: <b>0</b>\n"
            f"Реферальный счет: <b>0 RUB</b>\n"
            f"Кешбэк: <b>0 RUB</b>\n\n"
            f"<b>Ваша реферальная ссылка:</b>\n"
            f"https://telegram.me/Hottabich_obmen_bot?start={user_id}"
        ),
        parse_mode="HTML",
        reply_markup=profile_keyboard
    )

# Кнопка "Промокод"

profile_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏷 Промокод"), KeyboardButton(text="Вывести реф.счет")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

promo_cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

# Клавиатура внутри личного кабинета (у тебя уже есть, но на всякий — с единым эмодзи)
profile_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏷 Промокод"), KeyboardButton(text="Вывести реф.счет")],
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура при вводе промокода — такая же кнопка "Назад", как и везде
promo_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⬅️ Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура для ввода промокода
promo_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
    resize_keyboard=True
)
# Клавиатура для ввода промокода
promo_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⬅️ Назад")]],
    resize_keyboard=True
)

# Запуск ввода промокода
@dp.message(F.text == "🏷 Промокод")
async def promo_start(message: Message, state: FSMContext):
    photo = FSInputFile("media/promo.jpg")
    await message.answer_photo(
        photo=photo,
        caption="Введите промокод:",
        reply_markup=promo_keyboard
    )
    await state.set_state(PromoState.waiting_promo)

# Обработка ввода промокода — только в этом состоянии!
@dp.message(PromoState.waiting_promo, F.text)
async def promo_process(message: Message, state: FSMContext):
    if message.text == "⬅️ Назад":
        await state.clear()
        await profile_handler(message)  # возвращаем в личный кабинет
        return

    # Любой другой текст — некорректный промокод
    await message.answer(
        "⛔️ Некорректный промокод, попробуйте еще раз",
        reply_markup=promo_keyboard
    )
    # Остаёмся в состоянии — ждём новый ввод

# Важно: если пользователь в состоянии промокода нажмёт другую кнопку меню — очищаем состояние
@dp.message(PromoState.waiting_promo)
async def promo_cancel_by_menu(message: Message, state: FSMContext):
    await state.clear()
    # Ничего не отвечаем — просто выходим из режима промокода


@dp.message(F.text == "Вывести реф.счет")
async def withdraw_referral(message: Message):
    await message.answer(
        "⛔️ Минимальная сумма вывода <b>1000 RUB</b>\n"
        "💳 Ваш счет: <b>0 RUB</b>",
        parse_mode="HTML",
        reply_markup=profile_keyboard  # возвращаем клавиатуру ЛК
    )

# Кнопка "Назад" из личного кабинета
@dp.message(F.text == "⬅️ Назад")
async def profile_back(message: Message):
    await message.answer("⬅️ Возврат в главное меню", reply_markup=main_keyboard)



# Обработчик /start
@dp.message(F.text.startswith("/start"))
async def start_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id

    cursor.execute("SELECT passed FROM captcha_passed WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row and row[0] == 1:
        photo = FSInputFile("media/start.jpg")
        await message.answer_photo(
            photo=photo,
            caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
            reply_markup=main_keyboard
        )
        return

    captcha_photo, captcha_text = generate_captcha()
    
    await state.update_data(captcha_answer=captcha_text)
    await state.set_state(CaptchaState.waiting_captcha)

    await message.answer_photo(
        photo=captcha_photo,
        caption=(
            "<b>Введите капчу!</b>\n\n"
            "❗️ДЛЯ КОРРЕКТНОГО ВВОДА КАПЧИ ОТКРОЙТЕ ИЗОБРАЖЕНИЕ❗️\n\n"
            "<code>Бот не будет реагировать на сообщения до корректного ввода</code>"
        ),
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(CaptchaState.waiting_captcha)
async def captcha_input(message: Message, state: FSMContext):
    user_input = message.text.strip()
    data = await state.get_data()
    correct_answer = data.get("captcha_answer", "")

    if user_input == correct_answer:
        cursor.execute("""
            INSERT INTO captcha_passed (user_id, passed) 
            VALUES (?, 1) 
            ON CONFLICT(user_id) DO UPDATE SET passed = 1
        """, (message.from_user.id,))
        conn.commit()

        photo = FSInputFile("media/start.jpg")
        await message.answer_photo(
            photo=photo,
            caption="🪄<b>Твой быстрый обмен ₽ на BTC и LTC, BTC и LTC на ₽</b>",
            reply_markup=main_keyboard
        )
        await state.clear()
    else:
        captcha_photo, captcha_text = generate_captcha()
        await state.update_data(captcha_answer=captcha_text)

        await message.answer("❌ Введите капчу верно")
        await message.answer_photo(
            photo=captcha_photo,
            caption=(
                "<b>Введите капчу!</b>\n\n"
                "❗️ДЛЯ КОРРЕКТНОГО ВВОДА КАПЧИ ОТКРОЙТЕ ИЗОБРАЖЕНИЕ❗️\n\n"
                "<code>Бот не будет реагировать на сообщения до корректного ввода</code>"
            ),
            parse_mode="HTML"
        )

#===================испыитай удачу ==============
@dp.message(F.text == "🎰 Испытай удачу")
async def luck_trial(message: Message):
    user_id = message.from_user.id

    # Проверяем время последней игры
    cursor.execute("SELECT last_play FROM luck_attempts WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if row:
        last_play = datetime.fromisoformat(row[0])
        if datetime.now() < last_play + timedelta(days=1):
            await message.answer("⛔️⏰ С момента последнего вращения не прошли сутки, попробуйте позже")
            return

    # Обновляем/добавляем время игры (сейчас)
    now = datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO luck_attempts (user_id, last_play) 
        VALUES (?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET last_play = excluded.last_play
    """, (user_id, now))
    conn.commit()

    # Отправляем анимацию слот-машины и получаем результат
    dice_message = await message.answer_dice(emoji="🎰")

    # Ждём анимацию
    await asyncio.sleep(2)

    # Получаем value (1-64)
    value = dice_message.dice.value

    # Джекпот 777 — это value == 64 (по документации и примерам ботов)
    if value == 64:
        prize = 500
    else:
        prize = random.randint(10, 200)

    # Фото + текст в ОДНОЙ строке
    photo = FSInputFile("media/win.jpg")
    await message.answer_photo(
        photo=photo,
        caption=f"Вы испытали удачу 🤑! Теперь ваша скидка составляет <b>{prize} RUB</b>",
        parse_mode="HTML"
    )

#==============Контаккты============================
@dp.message(F.text == "📱 Контакты")
async def contacts_handler(message: Message):
    photo = FSInputFile("media/support.jpg")

    contacts_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Поддержка", url=f"https://t.me/{SUPPORT_USER.lstrip('@')}")],
            [InlineKeyboardButton(text="Новости", url=NEWS_URL)],
            [InlineKeyboardButton(text="Отзывы", url=REVIEWS_URL)],
            [InlineKeyboardButton(text="Чат", url=CHAT_URL)],
            [InlineKeyboardButton(text="Админ", url=ADMIN_URL)],
            [InlineKeyboardButton(text="Наш сайт", url=SITE_URL)],
        ]
    )

    await message.answer_photo(
        photo=photo,
        caption="⬇️ Наши контакты",
        reply_markup=contacts_keyboard
    )

#-======================Инструкция=====================
@dp.message(F.text == "📜 Инструкция")
async def instruction_handler(message: Message):
    photo = FSInputFile("media/check.jpg")

    caption = (
        "Подробная инструкция по использованию нашего бота представлена по ссылке:\n"
        "https://telegra.ph/Instrukciya-dlya-bota-Hottabych-09-16"
    )

    await message.answer_photo(
        photo=photo,
        caption=caption,
        parse_mode="HTML",  # не обязательно, но на всякий
        disable_web_page_preview=True  # оставляем превью, если хочешь — или True, чтобы без него
    )

#--------------------------калькулятор-------------------
calc_coin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="BTC"), KeyboardButton(text="LTC")],
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

calc_cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)
@dp.message(F.text == "🧮 Калькулятор")
async def calculator_start(message: Message, state: FSMContext):
    photo = FSInputFile("media/calculator.jpg")
    await message.answer_photo(
        photo=photo,
        caption="Выберите валюту",
        reply_markup=calc_coin_keyboard
    )
    await state.set_state(CalculatorState.choose_coin)



# Выбор монеты
@dp.message(CalculatorState.choose_coin, F.text.in_({"BTC", "LTC"}))
async def calc_coin_selected(message: Message, state: FSMContext):
    coin = "BTC" if message.text == "BTC" else "LTC"
    await state.update_data(coin=coin)

    await message.answer(
        f"Введите значение для <b>{coin}</b> в <b>РУБЛЯХ</b>",
        parse_mode="HTML",
        reply_markup=calc_cancel_keyboard
    )
    await state.set_state(CalculatorState.enter_rub_amount)

# Отмена на любом этапе калькулятора
@dp.message(CalculatorState.choose_coin, F.text == "❌ Отмена")
@dp.message(CalculatorState.enter_rub_amount, F.text == "❌ Отмена")
async def calc_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Операция отменена",
        reply_markup=main_keyboard
    )


# Отмена на этапе ввода суммы
@dp.message(CalculatorState.enter_rub_amount, F.text == "❌ Отмена")
async def calc_cancel_amount(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отмена", reply_markup=main_keyboard)

def format_crypto(amount: float, precision: int = 8) -> str:
    return f"{float(amount):.{precision}f}".rstrip("0").rstrip(".")

@dp.message(CalculatorState.enter_rub_amount)
async def calc_process_amount(message: Message, state: FSMContext):
    try:
        value = float(message.text.replace(",", ".").strip())
        if value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное число (больше 0)")
        return

    data = await state.get_data()
    coin = data["coin"]

    # Курсы из .env
    buy_rate = BTC_BUY if coin == "BTC" else LTC_BUY

    # Определяем тип ввода
    if value < 200:  # трактуем как крипту
        crypto_amount = value
        rub_amount = crypto_amount * buy_rate
        crypto_str = format_crypto(crypto_amount, 8 if coin == "BTC" else 4)
        rub_str = int(round(rub_amount))
        result_text = (
            f"<code>{crypto_str}</code> {coin}\n\n"
            f"это по курсу <code>{rub_str}</code> рублей"
        )
    elif value >= 1500:  # трактуем как рубли
        rub_amount = value
        crypto_amount = rub_amount / buy_rate
        crypto_str = format_crypto(crypto_amount, 8 if coin == "BTC" else 4)
        rub_str = int(round(rub_amount))
        result_text = (
            f"<code>{rub_str}</code> рублей\n\n"
            f"это по курсу <code>{crypto_str}</code> {coin}"
        )
    else:
        result_text = "❌ Введите сумму в крипте (<200) или в рублях (≥1500)"

    await message.answer(result_text, parse_mode="HTML", reply_markup=main_keyboard)
    await state.clear()



@dp.message(F.text == "⭐ Отзывы")
async def reviews_handler(message: types.Message):
    url = os.getenv("REVIEWS_URL")
    
    if not url:
        await message.answer("Отзывы пока не настроены 😔")
        return

    # Только одна кнопка-ссылка
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Отзывы", url=url)]
    ])

    # Минимальный текст, чтобы сообщение не выглядело пустым
    await message.answer("Отзывы:", reply_markup=kb)


async def main():
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
    ])
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
