import json
import logging
import os

from aiogram import Router, F, Bot
from aiogram.dispatcher.event.bases import UNHANDLED
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, \
    InlineKeyboardMarkup, CallbackQuery, ErrorEvent

from src.admin_kit.keyboards import kb_admin_order_confirm
from src.admin_panel import get_admin_context
from src.cfg import ADMIN_CHAT_IDS, CRYPTO_COSH, PAYMENT_DETAILS, CONTACT_FILE
from src.keyboard import home_btn,  calc_btn, buy_btn, buy_btn_finish, sale_btn, sale_btn_finish, \
    buy_card_btn
from src.service import load_users, save_user, fetch_crypto, generate_request_id
from src.state import CaptchaStates, CalcStates, ExchangeStates, SaleStates

router = Router()
logger = logging.getLogger(__name__)

# Configuration from environment variables
FIXED_DISCOUNT_RUB = float(os.getenv("FIXED_DISCOUNT_RUB", "150.0"))
MIN_RUB = float(os.getenv("MIN_RUB", "1500"))
BONUS_EXCHANGES_COUNT = int(os.getenv("BONUS_EXCHANGES_COUNT", "7"))
CAPTCHA_ANSWER = os.getenv("CAPTCHA_ANSWER", "540349")


@router.error()
async def network_error_handler(event: ErrorEvent):
    if isinstance(event.exception, TelegramNetworkError):
        logger.warning("Telegram network timeout while handling update: %s", event.exception)
        return True
    return UNHANDLED


def _admin_notification_targets() -> list[int]:
    ctx = get_admin_context()
    if ctx is not None and ctx.admin_ids:
        return list(ctx.admin_ids)
    return list(ADMIN_CHAT_IDS)


async def _notify_admins(
    bot: Bot,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    for chat_id in _admin_notification_targets():
        try:
            await bot.send_message(chat_id, text, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            logger.warning("Cannot send admin notification to chat_id=%s: %s", chat_id, exc)
        except Exception:
            logger.exception("Unexpected error while notifying admin chat_id=%s", chat_id)


def _order_status_label(status: str) -> str:
    labels = {
        "pending_payment": "ожидает оплату",
        "paid": "оплачено",
        "confirmed": "выдано",
        "cancelled": "отменено",
    }
    return labels.get(status, status)


def _fmt_rub(value: object) -> str:
    if isinstance(value, (int, float)):
        return str(int(round(float(str(value).replace(",", ".").replace(" ", "")))))
    if isinstance(value, str):
        raw = value.strip().replace(",", ".")
        try:
            return str(int(round(float(raw))))
        except ValueError:
            return "0"
    return "0"


def _normalize_phone_for_spb(raw_phone: str) -> str | None:
    digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]

    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return "+" + digits


def load_json(path: str, default=None):
    if default is None:
        default = {}
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=4)
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def contact_btn():
    # Map contact buttons to configurable links from admin context
    ctx = get_admin_context()
    if ctx is not None:
        links = ctx.settings.env_links
        contact_data = {
            "help": {"text": "ПОМОЩЬ ПО БОТУ/ОБМЕНУ", "url": links.get("faq", "https://t.me/LITEBITBIT_CHANNEL")},
            "reviews": {"text": "ОТЗЫВЫ", "url": links.get("reviews", "https://t.me/lit_otxov")},
            "admin": {"text": "АДМИН", "url": links.get("manager", "https://t.me/Litebit_2")},
        }
    else:
        contact_data = load_json(CONTACT_FILE, default={
            "help": {"text": "ПОМОЩЬ ПО БОТУ/ОБМЕНУ", "url": "https://t.me/LITEBITBIT_CHANNEL"},
            "reviews": {"text": "ОТЗЫВЫ", "url": "https://t.me/lit_otxov"},
            "admin": {"text": "АДМИН", "url": "https://t.me/Litebit_2"},
        })
    buttons = [[InlineKeyboardButton(text=v["text"], url=v["url"])] for v in contact_data.values()]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def fallback_payment_methods() -> list[str]:
    return list(PAYMENT_DETAILS.keys())


async def home(message: Message):
    await message.answer("⬇ Выберите меню ниже:", reply_markup=home_btn())


@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext):
    await state.clear()
    logger.info("Start command from chat_id=%s", message.chat.id)
    chat_id = message.chat.id
    if chat_id in load_users():
        await home(message)
        return

    photo = FSInputFile("assets/start.jpeg")
    caption = """
Введите капчу!

<b>❗ДЛЯ КОРРЕКТНОГО ВВОДА КАПЧИ ОТКРОЙТЕ ИЗОБРАЖЕНИЕ ❗</b>
<code>Бот не будет реагировать на сообщения до корректного ввода</code>
    """
    try:
        await message.answer_photo(photo, caption=caption)
    except Exception:
        logger.exception("Failed to send captcha photo to chat_id=%s", message.chat.id)
        await message.answer(caption)

    await state.set_state(CaptchaStates.waiting_for_captcha)


@router.message(CaptchaStates.waiting_for_captcha)
async def captcha_handler(message: Message, state: FSMContext):
    chat_id = message.chat.id

    if message.text == CAPTCHA_ANSWER:
        save_user(chat_id)
        await state.clear()
        await home(message)


@router.message(F.text == "📱 Контакты")
async def contacts_menu_handler(message: Message):
    await message.answer(
        "⬇ Наши контакты", reply_markup=contact_btn()
    )


@router.message(F.text == "💻 Личный кабинет")
async def profile_handler(message: Message):
    await message.answer(f"""
Ваш уникальный ID: <code>{message.chat.id}</code>
Количество обменов: <b>0</b>
Количество рефералов: <b>0</b>
Реферальный счет: <b>0</b> RUB
Кешбэк: <b>0</b> RUB
    """
)


@router.message(F.text == "🛒 Готовые обмены")
async def ready_exchanges_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("⛔️ Пока нет свободных обменов, попробуйте позже", reply_markup=home_btn())


@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await home(message)


@router.message(F.text == "⬅️ Назад")
async def back_handler(message: Message):
    await home(message)


@router.message(F.text == "🧮 Калькулятор")
async def calc_start(message: Message, state: FSMContext):
    await message.answer("Выберите валюту", reply_markup=calc_btn())
    await state.set_state(CalcStates.waiting_for_currency)


@router.message(CalcStates.waiting_for_currency)
async def choose_currency(message: Message, state: FSMContext):
    text = message.text or ""
    currency = text.upper()
    if currency not in ["BTC", "LTC", "XMR", "USDT", "❌"]:
        await message.answer("⛔️ Некорректная валюта, выберите снова.", reply_markup=calc_btn())
        return

    if currency == "❌":
        await state.clear()
        await message.answer("Отмена", reply_markup=home_btn())
        return

    await state.update_data(currency=currency)
    await state.set_state(CalcStates.waiting_for_amount)

    await message.answer(f"Введите значение для {currency} в РУБЛЯХ:", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True
    ))


@router.message(CalcStates.waiting_for_amount)
async def calc_input_amount(message: Message, state: FSMContext):
    text = message.text or ""
    if text == "❌":
        await state.clear()
        await message.answer("Отмена", reply_markup=home_btn())
        return

    try:
        amount_rub = float(text.replace(",", "."))
    except ValueError:
        await message.answer("⛔️ Некорректное значение, попробуйте ещё раз.")
        return

    rates = await fetch_crypto()
    data = await state.get_data()
    currency = data["currency"]

    price_rub = rates.get(currency)
    if price_rub is None:
        await message.answer("Ошибка получения курса, попробуйте позже.")
        return

    crypto_amount = amount_rub / price_rub
    await message.answer(f"""<code>{int(amount_rub)}</code> рублей
это по курсу <code>{crypto_amount:.8f}</code> {currency}""", reply_markup=home_btn())
    await state.clear()


@router.message(F.text == "📈 Купить")
async def buy_menu_handler(message: Message):
    await message.answer(
        "Выберите валюту", reply_markup=buy_btn()
    )


@router.message(F.text.startswith("🔄 "))
async def select_currency(message: Message, state: FSMContext):
    text = message.text or ""
    currency = text.replace("🔄 ", "").upper()
    if currency not in ["BTC", "LTC", "XMR", "USDT"]:
        await message.answer("⛔️ Некорректная валюта, попробуйте снова.")
        return

    await state.update_data(currency=currency)
    await state.set_state(ExchangeStates.waiting_for_amount)

    main_texts = {
        "BTC": "💰 Введи нужную сумму в BTC:\n\n<b>Мин. сумма: 1000 руб.</b>\n<b>Макс. сумма: 150000 руб.</b>",
        "LTC": "💰 Введи нужную сумму в LTC:\n\n<b>Мин. сумма: 1000 руб.</b>\n<b>Макс. сумма: 150000 руб.</b>",
        "XMR": "💰 Введи нужную сумму в XMR:\n\n<b>Мин. сумма: 1000 руб.</b>\n<b>Макс. сумма: 150000 руб.</b>",
        "USDT": "💰 Введи нужную сумму в USDT:\n\n<b>Мин. сумма: 1000 руб.</b>\n<b>Макс. сумма: 150000 руб.</b>"
    }

    examples = {
        "BTC": "Например: <b>0.00041</b> или <b>1000</b>\n\n<u>Также можете воспользоваться готовыми обменами, это быстрее и дешевле</u>",
        "LTC": "Например: <b>0.18</b> или <b>1000</b>\n\n<u>Также можете воспользоваться готовыми обменами, это быстрее и дешевле</u>",
        "XMR": "Например: <b>0.065</b> или <b>1000</b>\n\n<u>Также можете воспользоваться готовыми обменами, это быстрее и дешевле</u>",
        "USDT": "Например: <b>10</b>\n\n<u>Также можете воспользоваться готовыми обменами, это быстрее и дешевле</u>"
    }

    await message.answer(main_texts[currency], reply_markup=buy_btn_finish())
    await message.answer(examples[currency])


@router.message(ExchangeStates.waiting_for_amount)
async def exchange_input_amount(message: Message, state: FSMContext):
    text = message.text or ""
    if text == "❌":
        await state.clear()
        await message.answer("Отмена", reply_markup=home_btn())
        return

    try:
        amount = float(text.replace(",", "."))
    except ValueError:
        await message.answer("⛔️ Некорректное значение, попробуйте ещё раз.")
        return

    data = await state.get_data()
    currency = data["currency"]

    rates = await fetch_crypto()
    price_rub = rates.get(currency)

    if price_rub is None:
        await message.answer("Ошибка получения курса, попробуйте позже.")
        return

    # --- ЛОГИКА ПРО КРИПТА/РУБЛИ ---
    if currency == "USDT":
        if amount <= 1000:
            crypto_amount = amount
            converted_rub = round(crypto_amount * price_rub, 2)
        else:
            converted_rub = amount
            crypto_amount = round(amount / price_rub, 2)
    else:
        if amount <= 1:
            crypto_amount = amount
            converted_rub = round(crypto_amount * price_rub, 2)
        else:
            converted_rub = amount
            crypto_amount = round(amount / price_rub, 8)

    if converted_rub < MIN_RUB:
        await message.answer(f"Минимальная сумма {MIN_RUB} RUB")
        return

    ctx = get_admin_context()
    commission_percent = 5.0
    if ctx is not None:
        commission_percent = float(ctx.settings.commission_percent)

    commission_amount = round(converted_rub * (commission_percent / 100), 2)
    old_price = converted_rub
    discount = FIXED_DISCOUNT_RUB
    final_price = round(old_price + commission_amount - discount, 2)
    if final_price < 0:
        final_price = 0.0
    left_exchanges = BONUS_EXCHANGES_COUNT

    # ⛔ ОБЯЗАТЕЛЬНО СОХРАНЯЕМ ДАННЫЕ
    await state.update_data(
        amount_crypto=f"{crypto_amount} {currency}",
        commission_percent=commission_percent,
        commission_amount=commission_amount,
        discount=discount,
        old_price=old_price,
        final_price=final_price,
        left_exchanges=left_exchanges,
    )

    text = (
        f"До бонусного обмена осталось {left_exchanges} обм.\n\n"
        f"Получите: <b>{crypto_amount} {currency}</b>\n"
        f"Скидка: <b>{int(round(discount))} ₽</b>\n\n"
        f"<u>Выберите способ оплаты ⬇️</u>"
    )

    await message.answer(text, reply_markup=buy_card_btn(final_price))

    # НЕ ОЧИЩАЙ СТЕЙТ — ТЫ ЖЕ ПОСЛЕ НУЖЕН payment_method
    # await state.clear()  ⛔ удалить


@router.callback_query(F.data.startswith("pay_method_"))
async def choose_payment_method(callback: CallbackQuery, state: FSMContext):
    callback_data = callback.data or ""
    method_key = callback_data.replace("pay_method_", "")
    if method_key.isdigit():
        index = int(method_key)
        ctx = get_admin_context()
        methods = ctx.settings.payment_methods() if ctx is not None else fallback_payment_methods()
        if index < 0 or index >= len(methods):
            await callback.answer("Некорректный способ оплаты", show_alert=True)
            return
        method = methods[index]
    else:
        method = method_key
    await state.update_data(payment_method=method)

    data = await state.get_data()

    amount_crypto = data["amount_crypto"]
    discount = data.get("discount", FIXED_DISCOUNT_RUB)
    final_price = data.get("final_price", 0.0)
    left_exchanges = data["left_exchanges"]

    text = (
        f"До бонусного обмена осталось {left_exchanges} обм.\n\n"
        f"Получите: <b>{amount_crypto}</b>\n"
        f"Скидка: <b>{int(round(float(discount)))} ₽</b>\n"
        f"К оплате: <b>{int(round(float(final_price)))} ₽</b>\n\n"
        # f"Способ оплаты: {method}\n"
    )

    next_btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➡️ Далее", callback_data="next_step")]
        ]
    )

    callback_message = callback.message
    if not isinstance(callback_message, Message):
        await callback.answer()
        return

    await callback_message.edit_text(text, reply_markup=next_btn)
    await callback.answer()


@router.callback_query(F.data == "next_step")
async def ask_crypto_address(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    currency = data.get("currency", "").upper()

    text = (
        f"Выбранная валюта: {currency}\n"
        f"Введите свой {currency} адрес:"
    )

    callback_message = callback.message
    if not isinstance(callback_message, Message):
        await callback.answer()
        return

    await callback_message.edit_text(text)

    await state.set_state(ExchangeStates.waiting_for_wallet)
    await callback.answer()


@router.message(ExchangeStates.waiting_for_wallet)
async def input_wallet(message: Message, state: FSMContext, bot: Bot):
    wallet = message.text or ""
    await message.answer("⏳ Идет подбор реквизитов")

    data = await state.get_data()
    from_user = message.from_user
    username = from_user.username if from_user and from_user.username else "нет username"

    amount_crypto = data.get("amount_crypto")
    final_price = data.get("final_price")
    payment_method = data.get("payment_method", "Не выбран")

    payment_id = generate_request_id()


    ctx = get_admin_context()
    if ctx is not None:
        bank, requisites = ctx.settings.method_requisites(str(payment_method))
        coin_symbol = str(data.get("currency") or "").upper()
        coin_amount = 0.0
        if isinstance(amount_crypto, str):
            raw_amount = amount_crypto.split(" ", 1)[0]
            try:
                coin_amount = float(str(raw_amount).replace(",", ".").replace(" ", ""))
            except ValueError:
                coin_amount = 0.0
        amount_rub = float(final_price) if isinstance(final_price, (int, float)) else 0.0
        order = ctx.orders.create_order(
            user_id=from_user.id if from_user is not None else message.chat.id,
            username=username,
            wallet=wallet,
            coin_symbol=coin_symbol,
            coin_amount=coin_amount,
            amount_rub=amount_rub,
            payment_method=str(payment_method),
            bank=bank,
        )
        payment_id = order["order_id"]
    else:
        details = PAYMENT_DETAILS.get(payment_method, {"bank": "Неизвестный банк", "requisites": "Нет реквизитов"})
        bank = details["bank"]
        requisites = details["requisites"]

    text = (
        f"ID оплаты: <b>{payment_id}</b>\n"
        f"Перевод: <b>{bank}</b>\n"
        f"Реквизиты: <b>{requisites}</b>\n"
        f"Сумма к оплате: <b>{_fmt_rub(final_price)} RUB</b>\n"
        f"К получению: <b>{amount_crypto}</b>\n"
        f"На кошелек: <code>{wallet}</code>\n\n"
        f"⚠️ Важно: переводите <b>ТОЧНУЮ</b> сумму!\n\n"
        f"🧾 После оплаты нажмите:\n"
        f"<b>«✅ Я оплатил»</b>\n\n"

    )

    pay_btn = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"paid_confirmed:{payment_id}")],
            [InlineKeyboardButton(text="🚫 Отменить", callback_data=f"cancel_order:{payment_id}")],
        ]
    )

    warning_text = (
        "⏱ Будьте внимательны! На оплату даётся 13 минут! ⏱\n\n"
        "⚠️ ПЕРЕВОД НА ДРУГОЙ БАНК;\n"
        "⚠️ ПЕРЕВОД НЕВЕРНОЙ СУММЫ;\n"
        "⚠️ ПОЗДНИЙ ПЕРЕВОД СРЕДСТВ.\n\n"
        "❗ Вышеперечисленные действия приведут К ПОТЕРЕ СРЕДСТВ ❗"
    )

    await message.answer(warning_text)
    await message.answer(text, reply_markup=pay_btn)

    await _notify_admins(
        bot,
        f"""
<b>ПОКУПКА</b>
📩 *Новая оплата #{payment_id}*

👤 Пользователь: @{username}
💳 Метод оплаты: {payment_method}

💰 Сумма: {_fmt_rub(final_price)} RUB
📈 К получению: {amount_crypto}

🏦 Банк: {bank}
🔢 Реквизиты: {requisites}

📤 Кошелёк клиента: `{wallet}`
            """,
    )
    await state.clear()


@router.callback_query(F.data.startswith("paid_confirmed"))
async def paid_confirmed_handler(callback: CallbackQuery):
    callback_message = callback.message
    if not isinstance(callback_message, Message):
        await callback.answer()
        return
    callback_data = callback.data or ""
    order_id = ""
    if ":" in callback_data:
        order_id = callback_data.split(":", 1)[1]

    ctx = get_admin_context()
    if ctx is not None and order_id and ctx.orders.mark_paid(order_id):
        order = ctx.orders.get_order(order_id)
        if order is not None:
            callback_bot = callback.bot
            if callback_bot is None:
                await callback.answer()
                return
            await _notify_admins(
                callback_bot,
                (
                    "💳 Оплата подтверждена пользователем\n\n"
                    f"ID заявки: <b>{order_id}</b>\n"
                    f"Пользователь: <b>{order['user_id']}</b>\n"
                    f"Способ оплаты: <b>{order['payment_method']}</b>\n"
                    f"Кошелёк: <code>{order['wallet']}</code>\n"
                    f"Сумма: <b>{_fmt_rub(order['amount_rub'])} RUB</b>\n"
                    f"К выдаче: <b>{order['coin_amount']} {order['coin_symbol']}</b>"
                ),
                reply_markup=kb_admin_order_confirm(order_id),
            )

    await callback_message.answer(
        "⚡️ Пожалуйста, прикрепите скриншот оплаты, просто отправьте его в бота, он будет передан менеджеру.",
        reply_markup=home_btn(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_order"))
async def cancel_order_handler(callback: CallbackQuery):
    callback_message = callback.message
    if not isinstance(callback_message, Message):
        await callback.answer()
        return

    callback_data = callback.data or ""
    order_id = ""
    if ":" in callback_data:
        order_id = callback_data.split(":", 1)[1]

    ctx = get_admin_context()
    if ctx is not None and order_id:
        ctx.orders.mark_cancelled(order_id)

    try:
        await callback_message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass

    await callback_message.answer("Заявка отменена.", reply_markup=home_btn())
    await callback.answer("Отменено")


@router.message(F.photo)
async def user_photo_receipt_handler(message: Message, bot: Bot):
    from_user = message.from_user
    if from_user is None or not message.photo:
        return

    ctx = get_admin_context()
    order = None
    if ctx is not None:
        order = ctx.orders.latest_order_for_user(
            from_user.id,
            statuses={"pending_payment", "paid", "confirmed"},
        )

    username = f"@{from_user.username}" if from_user.username else "без username"
    caption = (message.caption or "").strip()
    if len(caption) > 180:
        caption = caption[:180] + "..."

    lines = [
        "<b>🧾 Чек / фото от пользователя</b>",
        f"👤 Юзер: <b>{username}</b>",
        f"🆔 ID: <code>{from_user.id}</code>",
    ]
    if order is not None:
        lines.extend(
            [
                f"🔁 Обмен: <b>#{order['order_id']}</b> ({_order_status_label(order['status'])})",
                f"💰 Сумма: <b>{_fmt_rub(order['amount_rub'])} RUB</b>",
                f"📈 К выдаче: <b>{order['coin_amount']} {order['coin_symbol']}</b>",
                f"💳 Оплата: <b>{order['payment_method']}</b> / <b>{order['bank']}</b>",
            ]
        )
    else:
        lines.append("🔁 Обмен: <b>не найден</b>")

    if caption:
        lines.append(f"💬 Комментарий: <i>{caption}</i>")

    admin_caption = "\n".join(lines)
    photo_file_id = message.photo[-1].file_id

    for chat_id in _admin_notification_targets():
        try:
            await bot.send_photo(chat_id=chat_id, photo=photo_file_id, caption=admin_caption)
        except TelegramBadRequest as exc:
            logger.warning("Cannot send user photo to admin chat_id=%s: %s", chat_id, exc)
        except Exception:
            logger.exception("Unexpected error while forwarding user photo to admin chat_id=%s", chat_id)

    order_id = order["order_id"] if order is not None else "n/a"
    logger.info("User photo forwarded to admins: user_id=%s order_id=%s", from_user.id, order_id)
    await message.answer("⚡️Спасибо! С вами свяжется наш менеджер.", reply_markup=home_btn())


# -------

@router.message(F.text == "📉 Продать")
async def sell_menu_handler(message: Message):
    await message.answer(
        "Выберите валюту", reply_markup=sale_btn()
    )


@router.message(F.text.startswith("Продать "))
async def sell_currency_handler(message: Message, state: FSMContext):
    text = message.text or ""
    currency = text.replace("Продать ", "").upper()

    if currency not in ["BTC", "LTC", "XMR", "USDT"]:
        await message.answer("⛔️ Некорректная валюта, попробуйте снова.")
        return

    # сохраняем валюту
    await state.update_data(currency=currency)
    await state.set_state(SaleStates.waiting_for_amount)

    await message.answer(
        f"<b>ВВОДИ СУММУ В {currency}:</b>",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="❌ Отмена")]],
            resize_keyboard=True
        )
    )


@router.message(SaleStates.waiting_for_amount)
async def process_sale_amount(message: Message, state: FSMContext):
    text = message.text or ""
    if text == "❌":
        await state.clear()
        await message.answer("Отменено.", reply_markup=home_btn())
        return

    try:
        amount_crypto = float(text.replace(",", "."))
    except ValueError:
        await message.answer("⛔️ Некорректное значение, попробуйте ещё раз.")
        return

    data = await state.get_data()
    currency = data["currency"]

    rates = await fetch_crypto()
    price_rub = rates.get(currency)
    if price_rub is None:
        await message.answer("⛔️ Не удалось получить актуальный курс из CoinGecko, попробуйте позже.")
        return

    total_rub = round(amount_crypto * price_rub, 2)

    # ⬇️ сохраняем сумму и цену
    await state.update_data(amount_crypto=amount_crypto, total_rub=total_rub)

    await message.answer(
        f"За продажу <b>{amount_crypto} {currency}</b> ты получишь <b>{_fmt_rub(total_rub)} ₽</b>\n\n"
        f"Способ зачисления:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="СПБ 📱", callback_data="spb")]
            ]
        )
    )


@router.callback_query(F.data == 'spb')
async def sale_spb_handler(callback: CallbackQuery, state: FSMContext) -> None:
    callback_message = callback.message
    if not isinstance(callback_message, Message):
        await callback.answer()
        return

    await callback_message.answer("""⚙️ Введи реквизиты для получения выплаты за продажу

<b>СБП - Номер телефона:</b>""", )
    await state.set_state(SaleStates.waiting_for_number)
    await callback.answer()


@router.message(SaleStates.waiting_for_number)
async def spb_number_handler(message: Message, state: FSMContext):
    phone_raw = (message.text or "").strip()
    phone = _normalize_phone_for_spb(phone_raw)
    if phone is None:
        await message.answer(
            "⛔️ Неверный номер телефона.\n"
            "Введите номер в формате +7XXXXXXXXXX (можно с пробелами/скобками)."
        )
        return

    await state.update_data(phone=phone)

    await message.answer("🏦 Укажите банк")
    await state.set_state(SaleStates.waiting_for_bank)

user_sales: dict[int, dict[str, float | str]] = {}

@router.message(SaleStates.waiting_for_bank)
async def spb_bank_handler(message: Message, state: FSMContext):
    bank = (message.text or "").strip()
    if len(bank) < 2 or len(bank) > 48:
        await message.answer("⛔️ Неверный банк. Введите название банка, например: Сбер / Озон / Т-Банк.")
        return

    await state.update_data(bank=bank)

    data = await state.get_data()
    amount_crypto = data["amount_crypto"]
    total_rub = data["total_rub"]
    currency = data["currency"]
    phone = data["phone"]
    from_user = message.from_user
    if from_user is None:
        await message.answer("⛔️ Ошибка пользователя.")
        return
    user_id = from_user.id

    user_sales[user_id] = {
        "currency": data["currency"],
        "amount_crypto": data["amount_crypto"],
        "total_rub": data["total_rub"],
        "phone": data["phone"],
        "bank": bank
    }

    await message.answer(
        f"К оплате: <b>{amount_crypto} {currency}</b>\n"
        f"Получишь: <b>{_fmt_rub(total_rub)} RUB</b>\n"
        f"Реквизиты: <b>{phone} {bank}</b>",
        reply_markup=sale_btn_finish()
    )

    await state.clear()

@router.message(F.text == "✅ Продолжить")
async def continue_handler(message: Message, bot: Bot):
    from_user = message.from_user
    if from_user is None:
        await message.answer("⛔️ Ошибка пользователя.")
        return
    chat_id = from_user.id

    data = user_sales.get(chat_id)
    if not data:
        await message.answer("⛔️ Ошибка: нет активной заявки.")
        return

    amount_crypto = data["amount_crypto"]
    total_rub = data["total_rub"]
    currency = data["currency"]
    phone = data["phone"]
    bank = data["bank"]
    username = from_user.username or "нет username"
    request_id = generate_request_id(20)

    await message.answer(
        f"""
Заявка #{request_id}

Переведи <code>{amount_crypto}</code> {currency} на <code>{CRYPTO_COSH[currency]}</code>

Выплата будет на реквизиты: <b>{phone} {bank}</b>

⚠️ На перевод дается 60 минут.
        """,
        reply_markup=home_btn()
    )

    await _notify_admins(
        bot,
        f"""
<b>ПРОДАЖА #{request_id}</b>

👤 @{username}
📱 Тел: {phone}
🏦 Карта: {bank}

💰 {amount_crypto} {currency}
💸 RUB: {_fmt_rub(total_rub)}
        """
    )

    user_sales.pop(chat_id, None)
