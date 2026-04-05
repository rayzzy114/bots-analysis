from aiogram.fsm.state import StatesGroup, State


class BuyCryptoState(StatesGroup):
    value = State()
    chat_id = State()
    currency = State()
    cosh = State()


class SaleCryptoState(StatesGroup):
    value = State()
    chat_id = State()
    currency = State()
    cosh = State()
    payment_count = State()


class CouponState(StatesGroup):
    code = State()


class CalculatorState(StatesGroup):
    mode = State()  # buy или sale
    currency = State()  # btc, ltc, xmr
    calc_type = State()  # crypto или rub
    value = State()  # значение для расчета
