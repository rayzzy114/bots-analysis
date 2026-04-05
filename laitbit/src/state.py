from aiogram.fsm.state import StatesGroup, State


class CaptchaStates(StatesGroup):
    waiting_for_captcha = State()


class CalcStates(StatesGroup):
    waiting_for_currency = State()
    waiting_for_amount = State()


class ExchangeStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_wallet = State()


class SaleStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_number = State()
    waiting_for_bank = State()


class AdminStates(StatesGroup):
    waiting_for_payment_value = State()
    waiting_for_crypto_value = State()
    waiting_for_contact_url = State()