from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    waiting_admin_commission = State()
    waiting_admin_env = State()
    waiting_admin_link = State()
    waiting_admin_sell_wallet = State()
