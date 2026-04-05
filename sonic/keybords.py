from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from config import URL_INFO


def kb_start():
    keybord = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('Правила и соглашение SoNic Ex', url=URL_INFO)],
        [InlineKeyboardButton('Я согласен', callback_data='App|yes'),
         InlineKeyboardButton('Не согласен', callback_data='App|no')]
    ])
    return keybord


def kb_menu():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('Купить Bitcoin (BTC)')
    kb2 = KeyboardButton('Купить Litecoin (LTC)')
    kb3 = KeyboardButton('👤Мой кошелек👤')
    kb4 = KeyboardButton('🔗ПАРТНЕРКА🔗')
    kb5 = KeyboardButton('📉Продать криптовалюту📉 ')
    kb6 = KeyboardButton('🧮Калькулятор🧮')
    kb7 = KeyboardButton('📜Правила📜')
    kb8 = KeyboardButton('🗃Отзывы🗃')
    kb9 = KeyboardButton('👨‍💻Оператор👨‍💻')
    return keybord.add(kb1, kb2).add(kb3).add(kb4, kb5).add(kb6).add(kb7, kb8).add(kb9)



def kb_no_app():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('Обновить')
    return keybord.add(kb1)

def kb_cancel_input():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('Отмена')
    return keybord.add(kb1)



def kb_pay_go():
    keybord = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('Перейти к сделке', callback_data='Go'),
         InlineKeyboardButton('Отмена', callback_data='cancel')]
    ])
    return keybord


def kb_adress_go():
    keybord = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('Подтвердить', callback_data='AdressGO'),
         InlineKeyboardButton('Отмена', callback_data='cancel')]
    ])
    return keybord


def kb_promokod_go():
    keybord = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('ВВЕСТИ ПРОМО-КОД', callback_data='promo_null')],
        [InlineKeyboardButton('Перейти к оплате', callback_data='payments'),
         InlineKeyboardButton('Отмена', callback_data='cancel')]
    ])
    return keybord


def kb_payments_success():
    keybord = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('✅ Я оплатил(а)', callback_data='Finish_pay')],
        [InlineKeyboardButton('❌ Отменить заявку', callback_data='cancel')]
    ])
    return keybord


def kb_home_finish():
    keybord = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton('На главную', callback_data='cancel')],
    ])
    return keybord


def kb_my_wallet():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('📤Отправить📤')
    kb2 = KeyboardButton('📥Пополнить📥')
    kb3 = KeyboardButton('🏠В главное меню🏠')
    return keybord.add(kb1, kb2).add(kb3)


def kb_pay_money_Wallet():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('Купить Bitcoin (BTC)')
    kb2 = KeyboardButton('Купить Litecoin (LTC)')
    kb3 = KeyboardButton('👤Мой кошелек👤')
    kb4 = KeyboardButton('🏠В главное меню🏠')
    return keybord.add(kb1, kb2).add(kb3).add(kb4)


def kb_parthers():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('🤑 Вывод средств 🤑')
    kb3 = KeyboardButton('🏠В главное меню🏠')
    return keybord.add(kb1).add(kb3)


def kb_one_menu():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('🏠В главное меню🏠')
    return keybord.add(kb1)


def kb_calkulate():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('🧮BTC')
    kb2 = KeyboardButton('🧮LTC')
    kb3 = KeyboardButton('Отмена')
    return keybord.add(kb1, kb2).add(kb3)



def ikb_menu_admin():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb1 = KeyboardButton('Изменить VISA')
    kb2 = KeyboardButton('Изменить СБП')
    kb3 = KeyboardButton('Выход')
    return keybord.add(kb1).add(kb2).add(kb3)


def ikb_stop_admin():
    keybord = ReplyKeyboardMarkup(resize_keyboard=True)
    kb = KeyboardButton('Выйти из режима ввода')
    return keybord.add(kb)