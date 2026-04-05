from aiogram.fsm.state import State, StatesGroup


class TradeState(StatesGroup):
    waiting_buy_amount = State()
    waiting_buy_wallet = State()
    waiting_sell_amount = State()
    waiting_sell_card = State()
    waiting_admin_commission = State()
    waiting_admin_link = State()
    waiting_admin_env = State()
    waiting_admin_requisites_value = State()
    waiting_admin_requisites_bank = State()
    waiting_admin_payment_method_add = State()
