import asyncio
import logging
import signal
import sys
import os
from typing import Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import StateFilter
from aiogram.types import BotCommand, CallbackQuery, Message

from config import *
from func import *
from keybords import *
from database import DataBase
from States import *

logging.basicConfig(level=logging.INFO)

bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
db = DataBase("database.db")


def get_db() -> DataBase:
    """Lazy DB connection per-message to avoid sharing across handlers."""
    return DataBase("database.db")


async def set_default_commands(bot: Bot) -> None:
    await bot.set_my_commands([BotCommand(command="start", description="🔄 Начать обмен")])


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Привет, я 🦊 <b>SoNic Ex</b> 🦊! \n"
        "Меняем Крипту: \n"
        "🪙 Bitcoin (BTC) \n"
        "🪙 Litecoin (LTC) \n"
        "Только с Нами \n"
        "Быстро 🚀🚀 \n"
        "Выгодно 🔥🔥🔥 \n"
        "Надежно 🏦🏦 \n"
        "Для начала работы со мной, ознакомься с правилами пользования обмена сервиса <b>SoNic Ex</b>",
        reply_markup=kb_start(),
    )


@dp.callback_query(F.data.startswith("App"))
async def app_func(callback: CallbackQuery) -> None:
    method = callback.data.split("|")[1]
    if method == "yes":
        await callback.message.edit_text(
            "Твое согласие принято! Можем приступать к обмену вместе с <b>SoNic Ex!</b>"
        )
        await callback.message.answer(
            "Вас Приветствует Sonic Ex Бот 🦊\n\n"
            "У Нас Вы можете продать или обменять по выгодному курсу BTC и LTC 🤝 \n\n"
            "Доставим Ваши монеты до адреса быстро и без потерь 🤛"
        )
        await callback.message.answer("Выбери нужный пункт меню:", reply_markup=kb_menu())
    else:
        await callback.message.answer(
            "Очень жаль, к сожалению дальнейшее наше взамодействие невозможно, без твоего согласия.",
            reply_markup=kb_no_app(),
        )


@dp.message(Command("repstart"))
@dp.message(F.text == "Обновить")
async def cmd_repStart(message: Message, state: FSMContext) -> None:
    await cmd_start(message, state)


@dp.message(F.text.in_({"Отмена", "🏠В главное меню🏠", "Выход"}))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выбери нужный пункт меню:", reply_markup=kb_menu())


@dp.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Выбери нужный пункт меню:", reply_markup=kb_menu())


@dp.message(F.text.in_({"Купить Bitcoin (BTC)", "Купить Litecoin (LTC)"}))
async def buy_money(message: Message, state: FSMContext) -> None:
    await state.clear()
    money = message.text.split(" ")[2][1:4]
    await message.answer(
        f"У Нас Самый Выгодный Курс Обмена 👍\n\n"
        f"На какую сумму Вы хотите купить {money}?\n"
        f"(Напишите сумму : от 300 руб 💶)",
        reply_markup=kb_cancel_input(),
    )
    await state.update_data(money=money)
    await UserBuy.amount.set()


@dp.message(StateFilter(UserBuy.amount), F.text.is_digit().not_(lambda x: int(x) >= 300) | ~F.text.is_digit())
async def chek_fsm_buy(message: Message) -> None:
    if not message.text.isdigit() or int(message.text) < 300:
        await message.delete()


@dp.message(StateFilter(UserBuy.amount))
async def fsm_input_amount(message: Message, state: FSMContext) -> None:
    await message.delete()
    data = await state.get_data()
    money = data["money"]

    MONEY_USDT = await get_price(f"{money}USDT")
    RUBS = await RUB()

    result = float(message.text.replace(",", ".").replace(" ", "")) / (float(MONEY_USDT) * float(RUBS))
    price = int(message.text) * (1 + COMMISSION_PERCENT / 100)

    await state.update_data(result_money=round(float(result), 7), price=round(float(price), 2))

    await message.answer(
        f"Сумма к оплате составит: <b>{round(float(price), 2)} ₽</b> 💰\n"
        f"Вы получите: <b>{round(float(result), 7)} {money}</b>\n\n"
        f"Оплата принимается на карту 💳 банка \n\n"
        f"любым удобным для Вас способом (с карты любого банка и терминалов, а так же других ЭПС)\n\n"
        f"Если Вы перевели неправильную сумму, или валюта не поступила на Ваш адрес в течении 60 мин - свяжитесь с оператором 👉{OPERATOR_PAY}",
        reply_markup=kb_pay_go(),
    )


@dp.callback_query(F.data == "Go")
async def go_pay_func(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Введите адрес кошелька:")
    await UserBuy.adress.set()


@dp.message(StateFilter(UserBuy.adress), lambda m: len(m.text) < 15)
async def del_fsm_adress(message: Message) -> None:
    await message.delete()


@dp.message(StateFilter(UserBuy.adress))
async def input_adress_fsm(message: Message, state: FSMContext) -> None:
    await state.update_data(adress=message.text)
    await message.answer(
        f"Подтвердите адрес кошелька:\n\n<b>{message.text}</b>",
        reply_markup=kb_adress_go(),
    )


@dp.callback_query(F.data == "AdressGO")
async def adress_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.message.edit_text(
        f"⚙️ Детали обмена:\n\n"
        f"📧 Адрес кошелька : \n<code>{data['adress']}</code> \n\n"
        f"💰 Количество приобретаемой валюты : \n<b>{data['result_money']} {data['money']}</b> \n\n"
        f"💸 Сумма к оплате : \n<b>{data['price']} ₽</b>.\n\n"
        f"⬇️Для получения скидки, введите ПРОМО-КОД⬇️",
        reply_markup=kb_promokod_go(),
    )


@dp.callback_query(F.data == "payments")
async def finish_pay(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(text=callback.message.html_text)
    await callback.message.answer(
        f"Реквизиты для оплаты: \n"
        f"Оплату принимаем на КАРТУ БАНКА \n\n"
        f"👇👇\n<code>{db.get_karta()}</code>\n\n"
        f"Или ПО НОМЕРУ ТЕЛЕФОНА\n"
        f"👇👇\n<code>{db.get_sbp()}</code> 📲 \n\n"
        f"❗️ВАЖНО ❗️\n"
        f"Переводите точную сумму\n"
        f"Иначе потеряете свои деньги\n\n"
        f"После успешного перевода денег по указанным реквизитам нажмите на кнопку \n"
        f"«✅ Я оплатил(а)»\n"
        f" или же Вы можете отменить данную заявку нажав на кнопку \n"
        f"«❌ Отменить заявку»\n\n"
        f"❗️ВАЖНО ❗️\n"
        f"⏱ ЗАЯВКА ДЕЙСТВИТЕЛЬНА\n"
        f"⏱           1️⃣0️ МИНУТ \n"
        f"⏱ С МОМЕНТА ЕЕ СОЗДАНИЯ",
        reply_markup=kb_payments_success(),
    )
    await state.clear()


@dp.callback_query(F.data == "Finish_pay")
async def finish_pay_func(callback: CallbackQuery) -> None:
    await callback.message.edit_text(callback.message.html_text)
    operator_link = f"[оператором]({URL_OPERATOR})"
    await callback.message.answer(
        f"Если Вы перевели неправильную сумму, или валюта не поступила на Ваш адрес в течении 10 мин - свяжитесь с {operator_link}",
        reply_markup=kb_home_finish(),
    )
    for admin_id in ADMIN:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"Пользователь @{callback.from_user.id} (<code>{callback.from_user.id}</code>) подтвердил оплату",
                parse_mode="HTML",
            )
        except Exception:
            pass


@dp.message(F.text == "👤Мой кошелек👤")
async def my_wallet_func(message: Message) -> None:
    await message.answer(
        f"<b>💳 Баланс 💳\n\n"
        f"BTC-адрес: \n<code>{BTC_WALLET}</code>\n"
        f"Баланс: 0.00000000 BTC\n\n"
        f"LTC-адрес: \n<code>{LTC_WALLET}</code>\n"
        f"Баланс: 0.00000000 LTC</b>",
        reply_markup=kb_my_wallet(),
    )


@dp.callback_query(F.data == "promo_null")
async def promo_fake(callback: CallbackQuery) -> None:
    await callback.answer("Промокоды закончились", show_alert=True)


@dp.message(F.text == "📤Отправить📤")
async def wallet_send(message: Message) -> None:
    await message.answer(
        "На вашем балансе недостаточно средств!\n"
        "Пополните баланс одного из кошельков"
    )


@dp.message(F.text == "📥Пополнить📥")
async def wallet_deposit(message: Message) -> None:
    await message.answer(
        f"📥 <b>Пополнение баланса 📥\n\n"
        f"Ваши кошельки:\n\n"
        f"BTC-адрес: \n<code>{BTC_WALLET}</code>\n"
        f"Баланс: 0.00000000 BTC\n\n"
        f"LTC-адрес: \n<code>{LTC_WALLET}</code>\n"
        f"Баланс: 0.00000000 LTC\n\n"
        f"Для пополнения ваших кошельков используйте указанные адреса (чтобы скопировать, просто нажмите на нужный адрес).\n\n"
        f"Переводы внутри бота занимают всего 5-10 минут!</b>",
        reply_markup=kb_pay_money_Wallet(),
    )


@dp.message(F.text == "🔗ПАРТНЕРКА🔗")
async def partners_func(message: Message) -> None:
    bot_username = USERNAME_BOT
    await message.answer(
        f"<b>Ваша статистика:\n"
        f"Кол-во сделок: 0\n"
        f"Кол-во рефералов: 0\n"
        f"Кол-во сделок рефералов: 0\n"
        f"Баланс: 0.0\n"
        f"Выведено: 0.0\n"
        f"Ваша ссылка:\n"
        f"https://t.me/{bot_username}?start={message.from_user.id}\n\n"
        f"ВАЖНО! Вывод средств доступен от 500Р на балансе</b>",
        reply_markup=kb_parthers(),
    )


@dp.message(F.text == "🤑 Вывод средств 🤑")
async def withdraw_func(message: Message) -> None:
    await message.answer(
        "К сожалению, Вам пока что недоступен вывод средств 😩 \n"
        "Но не стоит отчаиваться!🦊\n"
        "Накопи больше бонусов, чтобы воспользоваться данной услугой!👍",
        reply_markup=kb_one_menu(),
    )


@dp.message(F.text == "📉Продать криптовалюту📉")
async def sell_crypto(message: Message) -> None:
    await message.answer(URL_SELL)


@dp.message(F.text == "🧮Калькулятор🧮")
async def calc_menu(message: Message) -> None:
    await message.answer("💸 Выберите валюту:", reply_markup=kb_calkulate())


@dp.message(F.text.in_({"🧮BTC", "🧮LTC"}))
async def calc_crypto(message: Message, state: FSMContext) -> None:
    money = message.text[1:]
    await message.answer(
        f"🧮 Калькулятор {money} 🧮\n\n"
        f"(Напишите сумму :  от 300 руб 💶",
        reply_markup=kb_cancel_input(),
    )
    await state.update_data(money=money)
    await UserCalkulate.amount.set()


@dp.message(StateFilter(UserCalkulate.amount), lambda m: not m.text.isdigit() or int(m.text) < 300)
async def chek_fsm_calc(message: Message) -> None:
    if not message.text.isdigit() or int(message.text) < 300:
        await message.delete()


@dp.message(StateFilter(UserCalkulate.amount))
async def fsm_calc_amount(message: Message, state: FSMContext) -> None:
    await message.delete()
    data = await state.get_data()
    money = data["money"]

    MONEY_USDT = await get_price(f"{money}USDT")
    RUBS = await RUB()

    result = float(message.text.replace(",", ".").replace(" ", "")) / (float(MONEY_USDT) * float(RUBS))
    price = int(message.text) * (1 + COMMISSION_PERCENT_SELL / 100)

    await state.update_data(result_money=round(float(result), 7), price=round(float(price), 2))

    await message.answer(
        f"Вы получите <b>{round(float(result), 7)} {money}</b> на "
        f"{round(float(message.text.replace(',', '.').replace(' ', '')), 1)} RUB.\n"
        f"С учетом комисии сети сумма к оплате составит {round(float(price), 1)} RUB.\n"
    )
    await state.clear()


@dp.message(F.text == "📜Правила📜")
async def rules_func(message: Message) -> None:
    await message.answer(URL_INFO)


@dp.message(F.text == "🗃Отзывы🗃")
async def reviews_func(message: Message) -> None:
    await message.answer(URL_REWIEV)


@dp.message(F.text == "👨‍💻Оператор👨‍")
async def operator_func(message: Message) -> None:
    await message.answer(URL_OPERATOR)


# ─── Admin handlers ───


@dp.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in ADMIN:
        return
    await message.answer("<b>Вы в админ меню</b>", reply_markup=ikb_menu_admin())


@dp.message(F.text == "Изменить VISA")
async def admin_change_visa(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN:
        return
    karta = db.get_karta()
    await message.answer(
        f"Используется: <code>{karta}</code>\n\n"
        f"Введите новый номер карты чтобы обновить ее",
        reply_markup=ikb_stop_admin(),
    )
    await UpdatesKarta.karta.set()


@dp.message(StateFilter(UpdatesKarta.karta))
async def admin_update_karta(message: Message, state: FSMContext) -> None:
    karta = message.text
    db.update_karta(karta)
    await message.answer(
        f"✅ Карта успешно обновлена\n\n"
        f"Новое значение: <code>{karta}</code>",
        reply_markup=ikb_menu_admin(),
    )
    await state.clear()


@dp.message(F.text == "Изменить СБП")
async def admin_change_sbp(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN:
        return
    karta = db.get_sbp()
    await message.answer(
        f"Используется: <code>{karta}</code>\n\n"
        f"Введите новый номер СБП чтобы обновить ее",
        reply_markup=ikb_stop_admin(),
    )
    await UpdatesSbp.karta.set()


@dp.message(StateFilter(UpdatesSbp.karta))
async def admin_update_sbp(message: Message, state: FSMContext) -> None:
    karta = message.text
    db.update_sbp(karta)
    await message.answer(
        f"✅ Номер СБП успешно обновлен\n\n"
        f"Новое значение: <code>{karta}</code>",
        reply_markup=ikb_menu_admin(),
    )
    await state.clear()


@dp.message(F.text == "Выход")
async def admin_exit(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN:
        return
    await state.clear()
    await message.answer("<b>Админ панель</b>", reply_markup=ikb_menu_admin())


@dp.message(F.text == "Выйти из режима ввода")
async def admin_input_exit(message: Message, state: FSMContext) -> None:
    if message.from_user.id not in ADMIN:
        return
    await state.clear()
    await message.answer("<b>Админ панель</b>", reply_markup=ikb_menu_admin())


# ─── Startup / Shutdown ───


async def on_startup() -> None:
    await set_default_commands(bot)
    logging.info("Bot started")


async def on_shutdown() -> None:
    await bot.session.close()
    logging.info("Bot stopped")


async def main() -> None:
    await set_default_commands(bot)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s)),
        )

    logging.info("Starting polling...")
    await dp.start_polling(bot)


async def shutdown(signal_name: str) -> None:
    logging.info(f"Received {signal_name}, shutting down...")
    await on_shutdown()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
