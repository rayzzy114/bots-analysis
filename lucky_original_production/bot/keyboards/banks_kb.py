from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

BANKS = [


    "Кибит", "Альфа Банк", "Венец Банк", "Абсолют банк", "АК Барс Банк", "Банк Дом РФ", "Банк ЗЕНИТ", "Банк Открытие",


    "Банк ПСКБ", "Банк РЕСО Кредит", "Банк Русский Стандарт", "Банк Санкт-Петербург", "Банк УБРиР", "БКС Банк", "ВТБ", "Газпромбанк",


    "Ингосстрах Банк", "Киви Банк", "Кредит Урал Банк", "Локо-Банк", "МБ Банк", "МКБ", "МТС Банк", "Озон Банк",


    "ОТП Банк", "Почта Банк", "Промсвязьбанк", "Райффайзен", "Россельхозбанк", "Сбербанк", "Совкомбанк", "Уралсиб",


    "Хоум Банк", "Челиндбанк", "Челябинвестбанк", "ЮMoney", "Юникредит банк", "Юнистрим", "Яндекс Банк", "Азиатско-Тихоокеанский Банк",


    "Т-Банк", "ТКБ Банк", "Центр-Инвест Банк", "Банк Россия", "Цифра Банк", "Свой Банк", "Банк Кубань Кредит", "Новикомбанк",


    "Дальневосточный банк", "ГенБанк", "Банк Казани", "Алмазэргиэнбанк", "Единый ЦУПИС", "Севергаз Банк", "Банк Кошелев", "Солид Банк"

]


def get_banks_kb(page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()


    start = page * page_size

    end = start + page_size

    current_banks = BANKS[start:end]


    for i in range(0, len(current_banks), 2):

        row = [InlineKeyboardButton(text=current_banks[i], callback_data=f"bank_{current_banks[i]}")]

        if i + 1 < len(current_banks):

            row.append(InlineKeyboardButton(text=current_banks[i+1], callback_data=f"bank_{current_banks[i+1]}"))

        builder.row(*row)


    total_pages = (len(BANKS) + page_size - 1) // page_size


    nav_row = []

    if page > 0:

        nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"banks_page_{page-1}"))

    else:

         nav_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))


    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))


    if end < len(BANKS):

        nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"banks_page_{page+1}"))

    else:

        nav_row.append(InlineKeyboardButton(text=" ", callback_data="ignore"))


    builder.row(*nav_row)

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main"))


    return builder.as_markup()
