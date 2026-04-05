from aiogram.fsm.state import StatesGroup, State


class BuyCryptoState(StatesGroup):
    value = State()
    chat_id = State()
    currency = State()
    cosh = State()
    awaiting_payment_method = State()
    waiting_receipt = State()


class PromoCodeState(StatesGroup):
    waiting_code = State()

