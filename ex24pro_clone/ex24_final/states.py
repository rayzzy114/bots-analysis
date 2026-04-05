from aiogram.fsm.state import State, StatesGroup


class ClientState(StatesGroup):
    waiting_for_source = State()


class AdminChatState(StatesGroup):
    replying_to_user = State()
