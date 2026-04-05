from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import random
import string

router = Router()

def generate_crypto_address(currency):
    prefixes = {
        "BTC": ["1", "3", "bc1"],
        "LTC": ["L", "M", "ltc1"],
        "USDT": ["T"]
    }
    
    lengths = {
        "BTC": random.randint(26, 35),
        "LTC": random.randint(26, 34),
        "USDT": 34
    }
    
    prefix = random.choice(prefixes.get(currency, ["1"]))
    address_length = lengths.get(currency, 34) - len(prefix)
    
    chars = string.ascii_letters + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(address_length))
    
    return prefix + random_part

@router.callback_query(F.data == "deposit")
async def deposit_handler(callback: types.CallbackQuery):
    try:
        await callback.message.delete()

        kb = InlineKeyboardBuilder()
        kb.button(text="BTC", callback_data="deposit_btc")
        kb.button(text="LTC", callback_data="deposit_ltc")
        kb.button(text="USDT TRC", callback_data="deposit_usdt")
        kb.button(text="Главная меню", callback_data="back")
        kb.adjust(2, 1)

        text = "Выберите что хотите пополнить."

        await callback.message.answer(
            text,
            reply_markup=kb.as_markup()
        )
    
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка в [deposit_handler]: {e}")

@router.callback_query(F.data.in_({"deposit_btc", "deposit_ltc", "deposit_usdt"}))
async def specific_deposit_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()

        currency = callback.data.split("_")[1].upper()

        min_amounts = {
            "BTC": "0.0005",
            "LTC": "0.01", 
            "USDT": "10"
        }
        min_amount = min_amounts.get(currency, "0.001")

        kb = InlineKeyboardBuilder()
        kb.button(text="Получить новый адрес кошелька", callback_data=f"generate_new_address_{currency.lower()}")
        kb.button(text="Главная меню", callback_data="back")
        kb.adjust(1)

        address = generate_crypto_address(currency)

        await state.update_data(current_address=address, currency=currency)

        text = (
            f"<b>Ваш адрес для депозита\n\n"
            f"Внимание! Минимальная сумма пополнения {min_amount} {currency}!</b>\n\n"
            f"<code>{address}</code>"
        )

        await callback.message.answer(
            text,
            reply_markup=kb.as_markup()
        )
    
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка в [specific_deposit_handler]: {e}")

@router.callback_query(F.data.startswith("generate_new_address_"))
async def generate_new_address_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
        
        currency = callback.data.split("_")[-1].upper()
        
        new_address = generate_crypto_address(currency)
        
        await state.update_data(current_address=new_address, currency=currency)
        
        min_amounts = {
            "BTC": "0.0005",
            "LTC": "0.01",
            "USDT": "10"
        }
        min_amount = min_amounts.get(currency, "0.001")

        kb = InlineKeyboardBuilder()
        kb.button(text="Получить новый адрес кошелька", callback_data=f"generate_new_address_{currency.lower()}")
        kb.button(text="Главная меню", callback_data="back")
        kb.adjust(1)

        text = (
            f"<b>Новый адрес для депозита\n\n"
            f"Внимание! Минимальная сумма пополнения {min_amount} {currency}!</b>\n\n"
            f"<code>{new_address}</code>"
        )

        await callback.message.answer(
            text,
            reply_markup=kb.as_markup()
        )
    
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка в [generate_new_address_handler]: {e}")