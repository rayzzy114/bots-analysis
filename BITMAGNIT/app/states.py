from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    waiting_antispam_fire = State()
    waiting_buy_amount = State()
    waiting_buy_confirm = State()
    waiting_buy_wallet = State()
    waiting_buy_receipt = State()
    waiting_sell_amount = State()
    waiting_sell_requisites = State()
    waiting_calc_coin = State()
    waiting_calc_amount = State()
    waiting_promo = State()


class AdminState(StatesGroup):
    waiting_admin_commission = State()
    waiting_admin_env = State()
    waiting_admin_link = State()
    waiting_admin_requisites_value = State()
    waiting_admin_sell_btc_address = State()
    waiting_admin_bank_name = State()
    waiting_admin_payment_method_add = State()
