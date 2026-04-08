from aiogram.fsm.state import State, StatesGroup


class UserBuy(StatesGroup):
    amount = State()
    adress = State()


class UserCalkulate(StatesGroup):
    amount = State()


class UpdatesKarta(StatesGroup):
    karta = State()

class UpdatesSbp(StatesGroup):
    karta = State()
