from aiogram.dispatcher.filters.state import StatesGroup, State


class UserBuy(StatesGroup):
    amount = State()
    adress = State()


class UserCalkulate(StatesGroup):
    amount = State()


class UpdatesKarta(StatesGroup):
    karta = State()

class UpdatesSbp(StatesGroup):
    karta = State()