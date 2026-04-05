import random

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..constants import COINS
from ..context import AppContext
from ..keyboards import (
    kb_addresses_menu,
    kb_buy_menu,
    kb_cabinet_menu,
    kb_calc_menu,
    kb_cancel,
    kb_contacts,
    kb_main_menu,
    kb_saved_address_actions,
    kb_saved_addresses,
    kb_wallet_coin_menu,
    kb_wallet_menu,
)
from ..states import UserState
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, fmt_money, parse_amount


def build_common_router(ctx: AppContext) -> Router:
    router = Router(name="common")

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("⬇ Выберите меню ниже:", reply_markup=kb_main_menu())

    @router.message(Command("rates"))
    async def cmd_rates(message: Message) -> None:
        rates = await ctx.rates.get_rates(force=True)
        lines = [
            f"BTC: {fmt_money(rates['btc'])} RUB",
            f"LTC: {fmt_money(rates['ltc'])} RUB",
            f"XMR: {fmt_money(rates['xmr'])} RUB",
            f"USDT: {fmt_money(rates['usdt'])} RUB",
        ]
        await message.answer("Текущие курсы:\n" + "\n".join(lines))

    @router.callback_query(F.data == "nav:main")
    async def nav_main(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        if msg is None:
            await callback.answer()
            return
        await callback.answer()
        await state.clear()
        await msg.answer("⬇ Выберите меню ниже:", reply_markup=kb_main_menu())

    @router.message(F.text.in_({"❌ Отмена", "⬅️ Назад"}))
    async def menu_back(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("⬇ Выберите меню ниже:", reply_markup=kb_main_menu())

    @router.message(F.text == "📈 Купить")
    async def menu_buy(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Выберите валюту", reply_markup=kb_buy_menu())

    @router.message(F.text == "📉 Продать")
    async def menu_sell(message: Message, state: FSMContext) -> None:
        await state.clear()
        manager_link = ctx.settings.link("manager") or ctx.settings.link("operator")
        await message.answer(
            f"Для продажи криптовалюты пишите менеджеру: {manager_link}",
            reply_markup=kb_main_menu(),
        )

    @router.message(F.text == "🧮 Калькулятор")
    async def menu_calc(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Выберите валюту для расчета:", reply_markup=kb_calc_menu())

    @router.message(F.text.in_({"BTC", "LTC", "XMR", "USDT"}))
    async def calc_choose_coin(message: Message, state: FSMContext) -> None:
        mapping = {"BTC": "btc", "LTC": "ltc", "XMR": "xmr", "USDT": "usdt"}
        text = message.text or ""
        if text not in mapping:
            return

        current_state = await state.get_state()
        if current_state == UserState.waiting_address_coin.state:
            await state.update_data(address_coin=text)
            await state.set_state(UserState.waiting_address_value)
            await message.answer(f"Введите {text} адрес", reply_markup=kb_cancel())
            return
        if current_state == UserState.waiting_wallet_deposit_coin.state:
            return

        await state.set_state(UserState.waiting_calc_amount)
        await state.update_data(calc_coin=mapping[text])
        await message.answer(
            f"Введите сумму в RUB для {text}:",
            reply_markup=kb_cancel(),
        )

    @router.message(UserState.waiting_calc_amount)
    async def calc_input_amount(message: Message, state: FSMContext) -> None:
        amount = parse_amount(message.text or "")
        if amount is None:
            await message.answer("Введите корректную сумму, например: 5000")
            return
        data = await state.get_data()
        coin_key = data.get("calc_coin", "btc")
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin_key, 1.0)
        coin_amount = amount / max(rate, 0.0000001)
        symbol = COINS.get(coin_key, COINS["btc"])["symbol"]
        await state.clear()
        await message.answer(
            f"<b>{fmt_money(amount)} RUB</b>\nЭто по курсу <code>{fmt_coin(coin_amount)}</code> {symbol}",
            reply_markup=kb_main_menu(),
        )

    @router.message(F.text == "📱 Контакты")
    async def menu_contacts(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "⬇ Наши контакты",
            reply_markup=kb_contacts(ctx.settings.all_links()),
        )

    @router.message(F.text == "💻 Личный кабинет")
    async def menu_cabinet(message: Message, state: FSMContext) -> None:
        await state.clear()
        user_id = message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить пользователя.")
            return
        profile = ctx.users.user(user_id)
        bot_username = "bot"
        bot = message.bot
        if bot is not None:
            try:
                me = await bot.get_me()
                if me.username:
                    bot_username = me.username
            except Exception as e:
                print(f'Exception caught: {e}')
        referral_url = f"https://t.me/{bot_username}?start={user_id}"
        await message.answer(
            (
                f"Ваш уникальный ID: <code>{user_id}</code>\n"
                f"Количество обменов: {profile['trades_total']}\n"
                f"Реферальный счет: {fmt_money(profile['bonus_balance'])} RUB\n\n"
                f"<b>Ваша реферальная ссылка:\n{referral_url}</b>"
            ),
            reply_markup=kb_cabinet_menu(),
        )

    @router.message(F.text == "🔐 Кошелек")
    async def menu_wallet(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("🔐 Это твой личный кошелек", reply_markup=kb_wallet_menu())

    @router.message(F.text == "⬇️ Депозит")
    async def wallet_deposit(message: Message, state: FSMContext) -> None:
        await state.set_state(UserState.waiting_wallet_deposit_coin)
        await message.answer("Выберите валюту:", reply_markup=kb_wallet_coin_menu())

    @router.message(F.text == "⬆️ Вывод")
    async def wallet_withdraw(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Вывод пока доступен через менеджера.", reply_markup=kb_wallet_menu())

    @router.message(UserState.waiting_wallet_deposit_coin, F.text.in_({"BTC", "LTC", "XMR", "USDT"}))
    async def wallet_deposit_coin(message: Message, state: FSMContext) -> None:
        text = message.text or "BTC"
        addresses = {
            "BTC": "bc1qk89a48h740vkwvlx42g9dz43hqy6aclg5x7k80",
            "LTC": "ltc1qk89a48h740vkwvlx42g9dz43hqy6aclg5x7k80",
            "XMR": "49fVx9mQ5Yf6xg5nQX8Vt9y1Xb3Yc5YvD2m9U5s",
            "USDT": "TPsR4x4cfE1h3M3y8Jb4bNwN1a4T8S7f3A",
        }
        mins = {"BTC": "0.00001 BTC", "LTC": "0.001 LTC", "XMR": "0.01 XMR", "USDT": "10 USDT"}
        await state.clear()
        await message.answer(
            f"Сеть:{text}\nАдрес:{addresses[text]}\nМин. депозит:{mins[text]}",
            reply_markup=kb_wallet_menu(),
        )

    @router.message(F.text == "📚 Мои адреса")
    async def menu_addresses(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer(
            "В этом разделе ты можешь сохранять адреса и выбирать их для покупки криптовалюты",
            reply_markup=kb_addresses_menu(),
        )

    @router.message(F.text == "✅ Добавить адрес")
    async def addresses_add_start(message: Message, state: FSMContext) -> None:
        await state.set_state(UserState.waiting_address_coin)
        await message.answer("Выберите валюту", reply_markup=kb_wallet_coin_menu())

    @router.message(UserState.waiting_address_value)
    async def addresses_value_input(message: Message, state: FSMContext) -> None:
        address = (message.text or "").strip()
        if len(address) < 10:
            await message.answer("Введите корректный адрес.")
            return
        data = await state.get_data()
        coin = str(data.get("address_coin", "BTC"))
        await state.set_state(UserState.waiting_address_name)
        await state.update_data(address_value=address)
        await message.answer(
            f"Введите название для вашего {coin} адреса\n\n{address}",
            reply_markup=kb_cancel(),
        )

    @router.message(UserState.waiting_address_name)
    async def addresses_name_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None:
            await state.clear()
            return
        name = (message.text or "").strip()
        if len(name) < 2:
            await message.answer("Название должно быть не короче 2 символов.")
            return
        data = await state.get_data()
        coin = str(data.get("address_coin", "BTC"))
        address = str(data.get("address_value", ""))
        ctx.users.add_address(user_id=user_id, coin=coin, address=address, name=name)
        await state.clear()
        await message.answer("✅ Вы успешно добавили адрес", reply_markup=kb_addresses_menu())

    @router.message(F.text == "🗓️ Посмотреть мои адреса")
    async def addresses_list(message: Message) -> None:
        user_id = message_user_id(message)
        if user_id is None:
            return
        addresses = ctx.users.list_addresses(user_id)
        if not addresses:
            await message.answer("У вас пока нет сохраненных адресов.", reply_markup=kb_addresses_menu())
            return
        await message.answer("Ваши сохраненные адреса", reply_markup=kb_saved_addresses(addresses))

    @router.callback_query(F.data.startswith("addr:view:"))
    async def addresses_view(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None:
            await callback.answer()
            return
        raw_index = (callback.data or "").split(":")[-1]
        if not raw_index.isdigit():
            await callback.answer("Некорректный адрес", show_alert=True)
            return
        index = int(raw_index)
        addresses = ctx.users.list_addresses(user_id)
        if index < 0 or index >= len(addresses):
            await callback.answer("Адрес не найден", show_alert=True)
            return
        item = addresses[index]
        await callback.answer()
        await msg.answer(
            f"Название: {item['name']}\n\nАдрес: {item['address']}\n\nВалюта: {item['coin']}",
            reply_markup=kb_saved_address_actions(index),
        )

    @router.callback_query(F.data.startswith("addr:delete:"))
    async def addresses_delete(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None:
            await callback.answer()
            return
        raw_index = (callback.data or "").split(":")[-1]
        if not raw_index.isdigit():
            await callback.answer("Некорректный адрес", show_alert=True)
            return
        index = int(raw_index)
        if not ctx.users.delete_address(user_id, index):
            await callback.answer("Адрес не найден", show_alert=True)
            return
        await callback.answer("Адрес удален")
        await msg.answer("❌ Адрес удален")

    @router.callback_query(F.data == "addr:back:list")
    async def addresses_back_list(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None:
            await callback.answer()
            return
        addresses = ctx.users.list_addresses(user_id)
        await callback.answer()
        if not addresses:
            await msg.answer("У вас пока нет сохраненных адресов.", reply_markup=kb_addresses_menu())
            return
        await msg.answer("Ваши сохраненные адреса", reply_markup=kb_saved_addresses(addresses))

    @router.message(F.text == "🏷 Промокод")
    async def promo_start(message: Message, state: FSMContext) -> None:
        await state.set_state(UserState.waiting_promo)
        await message.answer("Введите промокод ниже:", reply_markup=kb_cancel())

    @router.message(UserState.waiting_promo)
    async def promo_input(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("❌ Такого промокода не существует.", reply_markup=kb_cabinet_menu())

    @router.message(F.text == "🎰 Испытай удачу")
    async def lucky_spin(message: Message) -> None:
        user_id = message_user_id(message)
        if user_id is None:
            return
        bot = message.bot
        if bot is None:
            return
        await bot.send_dice(chat_id=user_id, emoji="🎰")
        bonus = random.randint(5, 50)
        await message.answer(f"Вы испытали удачу. Ваша бонусная скидка: <b>{bonus}</b> RUB")

    @router.message(F.text == "Вывести реф. счет")
    async def withdraw_ref(message: Message) -> None:
        user_id = message_user_id(message)
        if user_id is None:
            return
        profile = ctx.users.user(user_id)
        await message.answer(
            "⛔ Минимальная сумма вывода 1000 RUB\n"
            f"💳 Ваш счет: {fmt_money(profile['bonus_balance'])} RUB"
        )

    return router
