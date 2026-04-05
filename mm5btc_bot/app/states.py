from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    waiting_receiver_address = State()
    waiting_confirm = State()


class AdminState(StatesGroup):
    waiting_fee = State()
    waiting_deposit_address = State()
    waiting_website_url = State()
    waiting_tor_url = State()
    waiting_link_rates = State()
    waiting_link_sell_btc = State()
    waiting_link_news_channel = State()
    waiting_link_operator = State()
    waiting_link_operator2 = State()
    waiting_link_operator3 = State()
    waiting_link_work_operator = State()
