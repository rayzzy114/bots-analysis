"""FSM-состояния (clone_spec.md §6 + админка)."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ExchangeSG(StatesGroup):
    waiting_amount = State()      # показан inline-калькулятор
    waiting_address = State()     # «Введите адрес … кошелька»
    awaiting_payment = State()    # экран реквизитов + «проверить оплату»
    awaiting_proof = State()      # наш кастом: ждём PDF/скрин (§9)


class AddCoinSG(StatesGroup):
    waiting_name = State()        # «нет нужной» → ввод названия валюты


class WalletsSG(StatesGroup):
    choose_coin = State()         # выбор валюты для списка адресов
    browsing = State()            # просмотр списка адресов выбранной валюты
    waiting_address = State()
    waiting_label = State()
    waiting_delete_id = State()
    waiting_rename_id = State()
    waiting_rename = State()


class AdminSG(StatesGroup):
    menu = State()
    waiting_link = State()        # правка ссылочного поля
    waiting_numeric = State()     # правка числового поля
    waiting_min_rub = State()     # правка минимума per-coin
