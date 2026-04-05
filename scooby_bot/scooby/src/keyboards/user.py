import random

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


fruits = {
    "🍎": "Яблоко",
    "🍏": "Зелёное яблоко",
    "🍌": "Банан",
    "🍒": "Вишня",
    "🍇": "Виноград",
    "🍈": "Дыня",
    "🍉": "Арбуз",
    "🍑": "Персик",
    "🍍": "Ананас",
    "🍓": "Клубника",
    "🥭": "Манго",
    "🍋": "Лимон",
    "🍐": "Груша",
    "🥝": "Киви",
    "🥥": "Кокос",
    "🫐": "Черника",
    "🥑": "Авокадо",
    "🍊": "Мандарин"
}


def generate_random_fruit_keyboard(count: int = 6, row_width: int = 3):
    selected = random.sample(list(fruits.keys()), count)
    answer = random.choice(selected)
    buttons = [InlineKeyboardButton(text=emoji, callback_data=("fruit_" + emoji)) for emoji in selected]
    keyboard_rows = [buttons[i:i + row_width] for i in range(0, len(buttons), row_width)]
    return (fruits[answer], answer), InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


def main_button():
    buttons = [
        [InlineKeyboardButton(text="💸 Купить", callback_data="buy"),
         InlineKeyboardButton(text="💰 Продать", callback_data="sale")],
        [InlineKeyboardButton(text="📖 Контакты", callback_data="contacts")],
        [InlineKeyboardButton(text="⚙️ Прочее", callback_data="other")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def contact_button():
    buttons = [
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def coupons_button():
    buttons = [
        [InlineKeyboardButton(text="🎟 Активировать купон", callback_data="activate_coupon")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def promotions_button():
    buttons = [
        [InlineKeyboardButton(text="🏃 Активность", callback_data="activity")],
        [InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def activity_button():
    buttons = [
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="promotions"),
            InlineKeyboardButton(text="📜 Главное меню", callback_data="home")
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def roulette_button():
    buttons = [
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def complaint_book_button():
    buttons = [
        [InlineKeyboardButton(text="О проблеме", callback_data="complaint_problem")],
        [InlineKeyboardButton(text="Можно сделать лучше", callback_data="complaint_suggestion")],
        [InlineKeyboardButton(text="Мои обращения", callback_data="complaint_my_appeals")],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def calculator_button(mode="buy", currency="btc", calc_type="crypto", from_transaction=None):
    currency_buttons = [
        InlineKeyboardButton(
            text="✅ BTC" if currency == "btc" else "BTC",
            callback_data="calc_btc"
        ),
        InlineKeyboardButton(
            text="✅ LTC" if currency == "ltc" else "LTC",
            callback_data="calc_ltc"
        ),
        InlineKeyboardButton(
            text="✅ XMR" if currency == "xmr" else "XMR",
            callback_data="calc_xmr"
        )
    ]
    
    # Добавляем USDT только для режима продажи
    if mode == "sale":
        currency_buttons.append(
            InlineKeyboardButton(
                text="✅ USDT" if currency == "usdt" else "USDT",
                callback_data="calc_usdt"
            )
        )
    
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Купить" if mode == "buy" else "Купить",
                callback_data="calc_buy"
            ),
            InlineKeyboardButton(
                text="✅ Продать" if mode == "sale" else "Продать",
                callback_data="calc_sale"
            )
        ],
        currency_buttons,
        [
            InlineKeyboardButton(
                text="✅ В крипте" if calc_type == "crypto" else "В крипте",
                callback_data="calc_crypto"
            ),
            InlineKeyboardButton(
                text="✅ В рублях" if calc_type == "rub" else "В рублях",
                callback_data="calc_rub"
            )
        ],
    ]
    
    if from_transaction:
        buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"calc_back_{from_transaction}_{currency}")])
    
    buttons.append([InlineKeyboardButton(text="📜 Главное меню", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def other_button():
    buttons = [
        [InlineKeyboardButton(text="💼 Зарабатывай с нами", callback_data="earn")],
        [
            InlineKeyboardButton(text="🎰 Рулетка", callback_data="roulette"),
            InlineKeyboardButton(text="🎟 Купоны", callback_data="coupons")
        ],
        [
            InlineKeyboardButton(text="🎁 Акции и скидки", callback_data="promotions"),
            InlineKeyboardButton(text="📲 Калькулятор", callback_data="calculator")
        ],
        [
            InlineKeyboardButton(text="📗 Книга жалоб", callback_data="complaint_book"),
            InlineKeyboardButton(text="📈 Профиль", callback_data="profile")
        ],
        [InlineKeyboardButton(text="📜 Главное меню", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

