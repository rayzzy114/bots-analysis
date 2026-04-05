from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder
import random
import asyncio

from utils.valute import parse_amount, is_rub_amount, get_bank_details_from_db, rate_manager, get_commission_rate

from config import (
    MIN_BTC,
    MAX_BTC,
    MIN_XMR,
    MAX_XMR,
    ADMIN_IDS
)

router = Router()

CRYPTO_CONFIG = {
    "btc": {
        "name": "BTC",
        "min": MIN_BTC,
        "max": MAX_BTC,
        "address_min_length": 25,
        "address_max_length": 62,
        "address_name": "BTC кошелек",
        "currency_name": "Bitcoin",
        "back_handler": "buy_btc_standard",
        "validation_msg": "Неверный BTC адрес. Попробуйте еще раз."
    },
    "xmr": {
        "name": "XMR",
        "min": MIN_XMR,
        "max": MAX_XMR,
        "address_min_length": 95,
        "address_max_length": 106,
        "address_name": "XMR кошелек",
        "currency_name": "Monero (XMR)",
        "back_handler": "buy_xmr_standard",
        "validation_msg": "Неверный XMR адрес. Попробуйте еще раз."
    }
}

class PaymentStates(StatesGroup):
    waiting_for_amount = State() 
    waiting_for_address = State()
    waiting_for_receipt = State()

def get_current_rate(crypto_type: str) -> float:
    if crypto_type == "btc":
        return rate_manager.get_btc_to_rub_rate()
    elif crypto_type == "xmr":
        return rate_manager.get_xmr_to_rub_rate()
    return 0.0

@router.callback_query(F.data.startswith("pay_with_"))
async def handle_payment(callback: CallbackQuery, state: FSMContext):
    
    parts = callback.data.replace("pay_with_", "").split("_")
    
    if len(parts) == 1:
        payment_method = parts[0]
        crypto_type = "btc"
    else:
        payment_method = parts[0]
        crypto_type = parts[1] if len(parts) > 1 else "btc"
    
    if payment_method not in get_bank_details_from_db():
        await callback.answer("Данный способ оплаты временно недоступен")
        return
    
    if crypto_type not in CRYPTO_CONFIG:
        await callback.answer("Данная криптовалюта недоступна")
        return
    
    await state.update_data(
        payment_method=payment_method,
        crypto_type=crypto_type
    )
    
    crypto_config = CRYPTO_CONFIG[crypto_type]
    
    kb = InlineKeyboardBuilder()
    kb.button(
        text="⬅️Назад",
        callback_data=crypto_config["back_handler"]
    )

    current_rate = get_current_rate(crypto_type)

    msg = (f"❇️Доступно для покупки этим способом оплаты: {crypto_config['max']} {crypto_config['name']}\n"
           f"📉Минимальная сумма: {crypto_config['min']} {crypto_config['name']} "
           f"({crypto_config['min'] * current_rate:,.0f} RUB)\n"
           f"📈Максимальная сумма: {crypto_config['max']} {crypto_config['name']} "
           f"({crypto_config['max'] * current_rate:,.0f} RUB)\n\n"
           f"Введите нужную сумму в {crypto_config['name']}\n\n"
           "Пример: 0.01"
    )
    
    await callback.message.edit_text(
        msg, reply_markup=kb.as_markup()
    )
    
    await state.set_state(PaymentStates.waiting_for_amount)

@router.message(StateFilter(PaymentStates.waiting_for_amount))
async def process_amount(message: Message, state: FSMContext):
    try:
        user_data = await state.get_data()
        crypto_type = user_data.get('crypto_type', 'btc')
        crypto_config = CRYPTO_CONFIG.get(crypto_type, CRYPTO_CONFIG['btc'])
        
        current_rate = get_current_rate(crypto_type)
        
        text_amount = message.text.strip()
        amount = parse_amount(text_amount)
        
        if is_rub_amount(amount):
            rub_amount = amount
            crypto_amount = rub_amount / current_rate
            
            if crypto_amount < crypto_config['min']:
                min_rub = crypto_config['min'] * current_rate
                await message.answer(f"Сумма слишком мала. Минимальная сумма: {min_rub:,.0f} RUB")
                return
            elif crypto_amount > crypto_config['max']:
                max_rub = crypto_config['max'] * current_rate
                await message.answer(f"Сумма слишком велика. Максимальная сумма: {max_rub:,.0f} RUB")
                return
                
            await state.update_data(
                amount=crypto_amount,
                original_amount=rub_amount,
                currency="RUB",
                current_rate=current_rate
            )
            
            await message.answer(
                f"<b>Введите {crypto_config['address_name']}, куда вы хотите получить {crypto_config['name']}.</b>"
            )

        else:
            crypto_amount = amount
            
            if crypto_amount < crypto_config['min']:
                await message.answer(
                    f"Укажите сумму в диапазоне от {crypto_config['min']:.4f} до {crypto_config['max']:.4f}"
                )
                return
            elif crypto_amount > crypto_config['max']:
                await message.answer(
                    f"Укажите сумму в диапазоне от {crypto_config['min']:.4f} до {crypto_config['max']:.4f}"
                )
                return
                
            rub_amount = crypto_amount * current_rate
            await state.update_data(
                amount=crypto_amount,
                original_amount=crypto_amount,
                currency=crypto_config['name'],
                current_rate=current_rate
            )
            
            await message.answer(
                f"<b>Введите {crypto_config['address_name']}, куда вы хотите получить {crypto_config['name']}.</b>"
            )
        
        await state.set_state(PaymentStates.waiting_for_address)
        
    except ValueError:
        await message.answer(
            "Вы не вывели корректную сумму."
        )
        
    except Exception as e:
        await state.clear()

@router.message(StateFilter(PaymentStates.waiting_for_address))
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    
    user_data = await state.get_data()
    crypto_type = user_data.get('crypto_type', 'btc')
    crypto_config = CRYPTO_CONFIG.get(crypto_type, CRYPTO_CONFIG['btc'])
    payment_method = user_data.get('payment_method')
    amount = user_data.get('amount')
    current_rate = user_data.get('current_rate')
    
    if not current_rate:
        current_rate = get_current_rate(crypto_type)
    
    if (len(address) < crypto_config['address_min_length'] or 
        len(address) > crypto_config['address_max_length']):
        await message.answer(crypto_config['validation_msg'])
        return
    
    bank_info = get_bank_details_from_db().get(payment_method, {})
    bank_name = bank_info.get("name", "")
    bank_details = bank_info.get("details", "")


    rub_orig_amount = amount * current_rate
    rub_amount_com = amount * current_rate * (1 + get_commission_rate())
    
    summary_msg = (
        f"Создать зявку?\n"
    #    f"Создать заявку на покупку {crypto_config['currency_name']}?\n"
        f"Сумма: {amount:.4f} {crypto_config['name']} ({rub_orig_amount:,.0f} RUB)\n"
        f"Кошелек: {address}\n\n"
    #    f"Способ оплаты: {bank_name}\n\n"
        
        "<b>Скидки:</b>\n"
        "<i>Личная скидка:</i>  0 руб.\n"
        "<i>Бонус:</i> 0 руб.\n\n"

        f"<b>Сумма к оплате составит: {rub_amount_com:,.0f} руб.</b>\n\n"
        
        f"<b>Правила:</b>\n"
        f"‼️Оплачивать необходимо точную сумму как в заявке, в противном случае вы рискуете потерять деньги!\n"
        f"‼️Если проверка идет более 5мин, пришлите чек в поддержку.\n"
        f"‼️Внимательно перепроверяйте кошелек и сумму, после оплаты транзакцию уже нельзя отменить.\n\n"
        
        "<b>С правилами согласны? Создать заявку?</b>"
    )
    
    await state.update_data(
        crypto_address=address,
        current_rate=current_rate
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data=f"confirm_payment_{crypto_type}")
    kb.button(text="Нет", callback_data=f"{crypto_config['back_handler']}")
    kb.button(
        text="Изменить сумму / кошелек", 
        callback_data=f"pay_with_{payment_method}_{crypto_type}"
    )
    kb.adjust(1)
    
    await message.answer(summary_msg, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("confirm_payment_"))
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    crypto_type = callback.data.replace("confirm_payment_", "")
    
    if crypto_type not in CRYPTO_CONFIG:
        await callback.answer("Ошибка: неизвестный тип криптовалюты")
        return
    
    crypto_config = CRYPTO_CONFIG[crypto_type]
    
    user_data = await state.get_data()
    payment_method = user_data.get('payment_method')
    amount = user_data.get('amount')
    crypto_address = user_data.get('crypto_address')
    current_rate = user_data.get('current_rate')
    
    if not current_rate:
        current_rate = get_current_rate(crypto_type)
    
    bank_info = get_bank_details_from_db().get(payment_method, {})
    bank_name = bank_info.get("name", "")
    bank_details = bank_info.get("details", "")
    
    rub_orig_amount = amount * current_rate
    rub_amount_com = amount * current_rate * (1 + get_commission_rate())

    kb = InlineKeyboardBuilder()
    kb.button(text="Отменить", callback_data=f"start_handler")
    kb.adjust(1)

    wait_msg = "♻️ Готовим платежные данные..."
    await callback.message.edit_text(wait_msg, reply_markup=kb.as_markup())
    await state.clear()

    wait_in_seconds = random.randint(10, 20)
    await asyncio.sleep(wait_in_seconds)
    
    final_msg = (
        f"✅ <b>Заявка на покупку {crypto_config['currency_name']} создана!</b>\n\n"
        
        f"<b>Детали заявки:</b>\n"
        f"• Сумма: {amount:.4f} {crypto_config['name']} ({rub_orig_amount:,.0f} RUB)\n"
        f"• Курс: 1 {crypto_config['name']} = {current_rate:,.0f} RUB\n"
        f"• {crypto_config['address_name']}: <code>{crypto_address}</code>\n"
        f"• Способ оплаты: {bank_name}\n\n"
        
        f"<b>Реквизиты для оплаты:</b>\n"
        f"<code>{bank_details}</code>\n\n"
        
        f"<b>Инструкция по оплате:</b>\n"
        f"1. Переведите {rub_amount_com:,.0f} RUB на указанные реквизиты\n"
        f"2. После оплаты средства поступят на ваш кошелек в течение 5-15 минут\n\n"
        
        f"<b>Статус заявки:</b> Ожидает оплаты\n"
        f"<b>Время на оплату:</b> 30 минут\n\n"
        
        "📞 При возникновении вопросов обращайтесь в поддержку"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Проверить статус", callback_data=f"check_status_{crypto_type}")
    kb.button(text="✅ Оплатил", callback_data=f"paid_{crypto_type}")
    kb.button(text="🏠 В главное меню", callback_data=crypto_config["back_handler"])
    kb.adjust(1)
    
    try:
        await callback.message.edit_text(final_msg, reply_markup=kb.as_markup(), parse_mode="HTML")
    except:
        pass
    
    await state.clear()

@router.callback_query(F.data.startswith("check_status_"))
async def check_status(callback: CallbackQuery):
    
    await asyncio.sleep(random.randint(2, 5))
    await callback.answer("Денежные средства не получены.")

@router.callback_query(F.data.startswith("paid_"))
async def handle_paid_button(callback: CallbackQuery, state: FSMContext):
    crypto_type = callback.data.replace("paid_", "")
    crypto_config = CRYPTO_CONFIG.get(crypto_type, CRYPTO_CONFIG['btc'])

    user_data = await state.get_data()
    order_data = user_data.get('order_data')

    await callback.answer()
    
    if not order_data:
        try:
            message_text = callback.message.text
            lines = message_text.split('\n')
            
            amount_line = [line for line in lines if "Сумма:" in line][0]
            address_line = [line for line in lines if "кошелек:" in line or "адрес:" in line][0]
            
            order_data = {
                'crypto_type': crypto_type,
                'amount': float(amount_line.split(':')[1].split()[0]),
                'crypto_address': address_line.split(':')[1].strip(),
                'user_id': callback.from_user.id,
                'username': callback.from_user.username
            }
        except:
            return
    
    await state.update_data(order_data=order_data)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data="start_handler")
    kb.adjust(1)
    
    request_msg = "Отправьте скрин перевода, либо чек оплаты."
    await callback.message.answer(request_msg, reply_markup=kb.as_markup())
    
    await state.set_state(PaymentStates.waiting_for_receipt)

@router.message(StateFilter(PaymentStates.waiting_for_receipt), 
               F.content_type.in_([ContentType.PHOTO, ContentType.DOCUMENT]))
async def handle_receipt(message: Message, state: FSMContext):
    user_data = await state.get_data()
    order_data = user_data.get('order_data', {})
    
    crypto_type = order_data.get('crypto_type', 'btc')
    crypto_config = CRYPTO_CONFIG.get(crypto_type, CRYPTO_CONFIG['btc'])

    kb = InlineKeyboardBuilder()
    kb.button(text="Главное меню", callback_data="start_handler")
    kb.adjust(1)
    
    confirmation_msg = "✅ Чек принят, ожидайте зачисление в течении 20 минут!"
    await message.answer(confirmation_msg, reply_markup=kb.as_markup())
    
    admin_message = (
        f"🆕 Поступил новый чек оплаты!\n\n"
        f"👤 Пользователь: @{message.from_user.username or 'нет username'}\n"
        f"🆔 ID: {message.from_user.id}\n"
        f"💰 Криптовалюта: {crypto_config['currency_name']}\n"
        f"📊 Сумма: {order_data.get('amount', 0):.4f} {crypto_config['name']}\n"
        f"🏦 Способ оплаты: {order_data.get('bank_name', 'Не указан')}\n"
        f"📝 Адрес: <code>{order_data.get('crypto_address', 'Не указан')}</code>\n\n"
        f"📎 Чек прикреплен ниже"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=admin_message
            )
            
            if message.photo:
                await message.bot.send_photo(
                    chat_id=admin_id,
                    photo=message.photo[-1].file_id,
                    caption=f"Чек от пользователя @{message.from_user.username}"
                )
            elif message.document:
                await message.bot.send_document(
                    chat_id=admin_id,
                    document=message.document.file_id,
                    caption=f"Чек от пользователя @{message.from_user.username}"
                )
        except Exception as e:
            print(f"{e}")
    
    await state.clear()

@router.message(StateFilter(PaymentStates.waiting_for_receipt))
async def handle_invalid_receipt(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Отмена", callback_data="start_handler")
    kb.adjust(1)
    await message.answer("Отправьте скрин перевода, либо чек оплаты.", reply_markup=kb.as_markup())