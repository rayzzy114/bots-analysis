from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    waiting_buy_amount = State()
    waiting_buy_wallet = State()
    waiting_buy_payment_method = State()
    waiting_buy_confirmation = State()
    waiting_buy_order_pending = State()


class AdminState(StatesGroup):
    waiting_admin_commission = State()
    waiting_admin_env = State()
    waiting_admin_link = State()
    waiting_admin_requisites_value = State()
    waiting_admin_bank_name = State()
    waiting_admin_payment_method_add = State()
