from aiogram import Router, F
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from src.keyboards.user import generate_random_fruit_keyboard, main_button, contact_button, other_button, coupons_button, promotions_button, activity_button, roulette_button, calculator_button, complaint_book_button
from src.keyboards.transaction import buy_button_operation, sale_button_operation
from src.texts.user import UserTexts
from src.states.transaction import CouponState, CalculatorState, BuyCryptoState, SaleCryptoState
from src.handlers.transaction import (
    BTC_RUB_BUY, XMR_RUB_BUY, LTC_RUB_BUY,
    BTC_RUB_SELL, XMR_RUB_SELL, LTC_RUB_SELL, USDT_RUB_SELL
)
from src.utils.manager import manager

start_router = Router()
texts = UserTexts()

user_message_ids = {}
correct_answer_to_fruit = {}


async def send_main_menu_with_photo(message_or_callback, reply_markup=None):
    photo = FSInputFile("menu.jpg")
    try:
        if isinstance(message_or_callback, Message):
            photo_message = await message_or_callback.answer_photo(
                photo=photo,
                caption=texts.get("start_description"),
                reply_markup=reply_markup or main_button()
            )
            await manager.set_photo_message(message_or_callback.chat.id, photo_message)
            await manager.set_message(message_or_callback.chat.id, photo_message)
            return photo_message
        else:
            photo_message = await message_or_callback.message.answer_photo(
                photo=photo,
                caption=texts.get("start_description"),
                reply_markup=reply_markup or main_button()
            )
            await manager.set_photo_message(message_or_callback.message.chat.id, photo_message)
            await manager.set_message(message_or_callback.message.chat.id, photo_message)
            return photo_message
    except TelegramForbiddenError:
        return None


@start_router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    fruit, keyboard = generate_random_fruit_keyboard()
    correct_answer_to_fruit[message.chat.id] = fruit[1]
    try:
        new_message = await message.answer(texts.get("start", fruit=fruit[0], emoji=fruit[1]), reply_markup=keyboard)
        await manager.set_message(message.chat.id, new_message)
    except TelegramForbiddenError:
        return


@start_router.callback_query(F.data.startswith('fruit_'))
async def callback_start_button(callback: CallbackQuery) -> None:
    selected_emoji = callback.data.replace("fruit_", "")
    correct_emoji = correct_answer_to_fruit.get(callback.message.chat.id)
    await manager.delete_message(callback.message.chat.id)

    if selected_emoji == correct_emoji:
        new_message = await send_main_menu_with_photo(callback.message)
        await manager.set_message(callback.message.chat.id, new_message)
    else:
        fruit, keyboard = generate_random_fruit_keyboard()
        correct_answer_to_fruit[callback.message.chat.id] = fruit[1]
        new_message = await callback.message.answer(texts.get("start", fruit=fruit[0], emoji=fruit[1]), reply_markup=keyboard)
        await manager.set_message(callback.message.chat.id, new_message)
        await callback.answer()


@start_router.callback_query(F.data.startswith('home'))
async def callback_main_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_message(callback.message.chat.id)
    new_message = await send_main_menu_with_photo(callback)
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'contacts')
async def contacts(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("contacts"), reply_markup=contact_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'other')
async def other(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("start_description"), reply_markup=other_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'earn')
async def earn(callback: CallbackQuery) -> None:
    await callback.answer()


@start_router.callback_query(F.data == 'roulette')
async def roulette(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("roulette"), reply_markup=roulette_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'coupons')
async def coupons(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("coupons"), reply_markup=coupons_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'promotions')
async def promotions(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("promotions"), reply_markup=promotions_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'activity')
async def activity(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("activity"), reply_markup=activity_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'calculator')
async def calculator(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(mode="buy", currency="btc", calc_type="crypto")
    await state.set_state(CalculatorState.value)
    await manager.delete_main_menu(callback.message.chat.id)
    
    prompt_text = "✏️ Введите количество BTC для расчета:"
    calculator_text = texts.get("calculator") + f"\n\n{prompt_text}"
    
    new_message = await callback.message.answer(calculator_text, reply_markup=calculator_button("buy", "btc", "crypto"))
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data.startswith('calc_from_buy_'))
async def calculator_from_buy(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.replace("calc_from_buy_", "")
    await state.update_data(mode="buy", currency=currency, calc_type="crypto", from_transaction="buy")
    await state.set_state(CalculatorState.value)
    
    prompt_text = f"✏️ Введите количество {currency.upper()} для расчета:"
    calculator_text = texts.get("calculator") + f"\n\n{prompt_text}"
    
    try:
        await callback.message.edit_text(calculator_text, reply_markup=calculator_button("buy", currency, "crypto", from_transaction="buy"))
        await manager.set_message(callback.message.chat.id, callback.message)
    except Exception:
        new_message = await callback.message.answer(calculator_text, reply_markup=calculator_button("buy", currency, "crypto", from_transaction="buy"))
        await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data.startswith('calc_from_sale_'))
async def calculator_from_sale(callback: CallbackQuery, state: FSMContext) -> None:
    currency = callback.data.replace("calc_from_sale_", "")
    await state.update_data(mode="sale", currency=currency, calc_type="crypto", from_transaction="sale")
    await state.set_state(CalculatorState.value)
    
    prompt_text = f"✏️ Введите количество {currency.upper()} для расчета:"
    calculator_text = texts.get("calculator") + f"\n\n{prompt_text}"
    
    try:
        await callback.message.edit_text(calculator_text, reply_markup=calculator_button("sale", currency, "crypto", from_transaction="sale"))
        await manager.set_message(callback.message.chat.id, callback.message)
    except Exception:
        new_message = await callback.message.answer(calculator_text, reply_markup=calculator_button("sale", currency, "crypto", from_transaction="sale"))
        await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data.startswith('calc_back_'))
async def calculator_back(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.replace("calc_back_", "").split("_")
    transaction_type = parts[0]
    currency = parts[1] if len(parts) > 1 else "btc"
    
    await manager.delete_message(callback.message.chat.id)
    await state.clear()
    
    if transaction_type == "buy":
        from src.texts.transaction import TransactionTexts
        transaction_texts = TransactionTexts()
        new_message = await callback.message.answer(
            transaction_texts.get("buy_currency", currency=currency.upper()),
            reply_markup=buy_button_operation(crypto=False, currency=currency)
        )
        await manager.set_message(callback.message.chat.id, new_message)
        await state.update_data(currency=currency)
        await state.update_data(payment_method="crypto")
        await state.set_state(BuyCryptoState.value)
    elif transaction_type == "sale":
        from src.texts.transaction import TransactionTexts
        transaction_texts = TransactionTexts()
        new_message = await callback.message.answer(
            transaction_texts.get("sale_currency", currency=currency.upper()),
            reply_markup=sale_button_operation(crypto=False, currency=currency)
        )
        await manager.set_message(callback.message.chat.id, new_message)
        await state.update_data(currency=currency)
        await state.set_state(SaleCryptoState.value)
    
    await callback.answer()


@start_router.callback_query(F.data.startswith('calc_') & ~F.data.startswith('calc_back_'))
async def calculator_options(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    mode = data.get("mode", "buy")
    currency = data.get("currency", "btc")
    calc_type = data.get("calc_type", "crypto")
    
    if callback.data == "calc_buy":
        mode = "buy"
    elif callback.data == "calc_sale":
        mode = "sale"
    elif callback.data == "calc_btc":
        currency = "btc"
    elif callback.data == "calc_ltc":
        currency = "ltc"
    elif callback.data == "calc_xmr":
        currency = "xmr"
    elif callback.data == "calc_usdt":
        currency = "usdt"
    elif callback.data == "calc_crypto":
        calc_type = "crypto"
    elif callback.data == "calc_rub":
        calc_type = "rub"
    
    await state.update_data(mode=mode, currency=currency, calc_type=calc_type)
    from_transaction = data.get("from_transaction")
    
    # Если все опции выбраны, запрашиваем ввод значения
    if mode and currency and calc_type:
        await state.set_state(CalculatorState.value)
        prompt_text = ""
        if calc_type == "crypto":
            prompt_text = f"✏️ Введите количество {currency.upper()} для расчета:"
        else:
            prompt_text = "✏️ Введите сумму в рублях для расчета:"
        
        try:
            await callback.message.edit_text(
                texts.get("calculator") + f"\n\n{prompt_text}",
                reply_markup=calculator_button(mode, currency, calc_type, from_transaction)
            )
        except Exception:
            await callback.message.answer(
                texts.get("calculator") + f"\n\n{prompt_text}",
                reply_markup=calculator_button(mode, currency, calc_type, from_transaction)
            )
    else:
        try:
            await callback.message.edit_reply_markup(reply_markup=calculator_button(mode, currency, calc_type, from_transaction))
        except Exception as e:
            print(f'Exception caught: {e}')
    
    await callback.answer()


@start_router.message(CalculatorState.value)
async def process_calculator_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    mode = data.get("mode", "buy")
    currency = data.get("currency", "btc")
    calc_type = data.get("calc_type", "crypto")
    
    try:
        value = float(message.text.replace(",", "."))
        await message.delete()
        
        # Выбираем курс в зависимости от режима
        if mode == "buy":
            if currency == "btc":
                rate = BTC_RUB_BUY
            elif currency == "ltc":
                rate = LTC_RUB_BUY
            elif currency == "xmr":
                rate = XMR_RUB_BUY
            else:
                rate = BTC_RUB_BUY
        else:  # sale
            if currency == "btc":
                rate = BTC_RUB_SELL
            elif currency == "ltc":
                rate = LTC_RUB_SELL
            elif currency == "xmr":
                rate = XMR_RUB_SELL
            elif currency == "usdt":
                rate = USDT_RUB_SELL
            else:
                rate = BTC_RUB_SELL
        
        # Рассчитываем результат
        if calc_type == "crypto":
            # Вводим крипту -> показываем рубли
            result = value * rate
            result_text = f"💰 {value} {currency.upper()} = {result:,.2f} ₽"
        else:
            # Вводим рубли -> показываем крипту
            result = value / rate
            result_text = f"💰 {value:,.2f} ₽ = {result:.8f} {currency.upper()}"
        
        from_transaction = data.get("from_transaction")
        await state.clear()
        new_message = await message.answer(
            result_text + "\n\n" + texts.get("calculator"),
            reply_markup=calculator_button(mode, currency, calc_type, from_transaction)
        )
        await manager.set_message(message.chat.id, new_message)
        
    except ValueError:
        await message.delete()
        prompt_text = ""
        if calc_type == "crypto":
            prompt_text = f"✏️ Введите количество {currency.upper()} для расчета:"
        else:
            prompt_text = "✏️ Введите сумму в рублях для расчета:"
        
        from_transaction = data.get("from_transaction")
        error_message = await message.answer(
            "❌ Неверный формат числа. Используйте только цифры и точку.\n\n" + prompt_text,
            reply_markup=calculator_button(mode, currency, calc_type, from_transaction)
        )
        await manager.set_message(message.chat.id, error_message)


@start_router.callback_query(F.data == 'complaint_book')
async def complaint_book(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("complaint_book"), reply_markup=complaint_book_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data.startswith('complaint_'))
async def complaint_options(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.edit_text(texts.get("complaint_problem"), reply_markup=contact_button())
    except Exception:
        await callback.message.answer(texts.get("complaint_problem"), reply_markup=contact_button())


@start_router.callback_query(F.data == 'profile')
async def profile(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await manager.delete_main_menu(callback.message.chat.id)
    new_message = await callback.message.answer(texts.get("profile"), reply_markup=contact_button())
    await manager.set_message(callback.message.chat.id, new_message)


@start_router.callback_query(F.data == 'activate_coupon')
async def activate_coupon(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await callback.message.edit_text(texts.get("activate_coupon"), reply_markup=contact_button())
    except Exception:
        await callback.message.answer(texts.get("activate_coupon"), reply_markup=contact_button())
    await state.set_state(CouponState.code)


@start_router.message(CouponState.code)
async def process_coupon_code(message: Message, state: FSMContext) -> None:
    await state.clear()
    # Удаляем сообщение с кодом купона
    await message.delete()
    # Отправляем ответ о неверном купоне
    new_message = await message.answer("❌ Купон неверный", reply_markup=contact_button())
    await manager.set_message(message.chat.id, new_message)

