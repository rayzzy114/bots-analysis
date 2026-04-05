
from aiogram import types, executor
from aiogram.dispatcher import FSMContext
from aiogram.utils.markdown import hlink
from keybords import *
from loader import dp, bot, db
from func import *
from config import *
from aiogram.types import CallbackQuery, Message
from States import *



async def set_default_commands(dp):
    await dp.bot.set_my_commands([
        types.BotCommand("start", "🔄 Начать обмен")
    ])

@dp.message_handler(text=['Отмена', '🏠В главное меню🏠', 'Выход'], state='*')
async def buy_xmr(message:Message, state:FSMContext):
    await state.finish()
    await message.answer('Выбери нужный пункт меню:', reply_markup=kb_menu())


@dp.callback_query_handler(text='cancel', state='*')
async def buy_xmr(callback:CallbackQuery, state:FSMContext):
    await state.finish()
    await callback.message.delete()
    await callback.message.answer('Выбери нужный пункт меню:', reply_markup=kb_menu())


@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message:Message, state:FSMContext):
    await state.finish()
    await message.answer('''Привет, я 🦊 <b>SoNic Ex</b> 🦊! 
Меняем Крипту: 
🪙 Bitcoin (BTC) 
🪙 Litecoin (LTC) 
Только с Нами 
Быстро 🚀🚀🚀 
Выгодно 🔥🔥🔥 
Надежно 🏦🏦🏦 
Для начала работы со мной, ознакомься с правилами пользования обмена сервиса <b>SoNic Ex</b>''', reply_markup=kb_start())



@dp.callback_query_handler(text_startswith='App')
async def app_func(callback:CallbackQuery):
    method = callback.data.split('|')[1]
    if method == 'yes':
        await callback.message.edit_text('Твое согласие принято! Можем приступать к обмену вместе с <b>SoNic Ex!</b>')
        await callback.message.answer('''Вас Приветствует Sonic Ex Бот 🦊

У Нас Вы можете продать или обменять по выгодному курсу BTC и LTC 🤝 

Доставим Ваши монеты до адреса быстро и без потерь 🤛''')
        return await callback.message.answer('Выбери нужный пункт меню:', reply_markup=kb_menu())
    await callback.message.answer('Очень жаль, к сожалению дальнейшее наше взамодействие невозможно, без твоего согласия.', reply_markup=kb_no_app())


@dp.message_handler(text='Обновить')
async def cmd_repStart(message:Message, state:FSMContext):
    await cmd_start(message, state)


@dp.message_handler(text=['Купить Bitcoin (BTC)', 'Купить Litecoin (LTC)'], state='*')
async def buy_money(message:Message, state:FSMContext):
    await state.finish()
    money = message.text.split(' ')[2][1:4]
    await message.answer(f'''У Нас Самый Выгодный Курс Обмена 👍

На какую сумму Вы хотите купить {money}?
(Напишите сумму : от 300 руб 💶)''', reply_markup=kb_cancel_input())
    await state.update_data(money=money)
    await UserBuy.amount.set()


@dp.message_handler(lambda message: not message.text.isdigit() or int(message.text) < 300, state=UserBuy.amount)
async def chek_fsm(message:Message):
    await message.delete()


@dp.message_handler(state=UserBuy.amount)
async def fsm_input_amount(message:Message, state:FSMContext):
    await message.delete()
    data = await state.get_data()
    MONEY_USDT = await get_price(f'{data["money"]}USDT')
    RUBS = await RUB()
    result = float(message.text) / (float(MONEY_USDT) * (float(RUBS)))
    price = int(message.text) * (1 + COMMISSION_PERCENT / 100)
    await state.update_data(result_money=round(float(result), 7), price=round(float(price), 2))
    await message.answer(f'''Сумма к оплате составит: <b>{round(float(price), 2)} ₽</b> 💰
Вы получите: <b>{round(float(result), 7)} {data["money"]}</b>

Оплата принимается на карту 💳 банка 

любым удобным для Вас способом (с карты любого банка и терминалов, а так же других ЭПС)

Если Вы перевели неправильную сумму, или валюта не поступила на Ваш адрес в течении 60 мин - свяжитесь с оператором 👉{OPERATOR_PAY}''', reply_markup=kb_pay_go())



@dp.callback_query_handler(text='Go', state='*')
async def go_pay_func(callback:CallbackQuery, state:FSMContext):
    await callback.message.edit_text('Введите адрес кошелька:')
    await UserBuy.next()


@dp.message_handler(lambda message: len(message.text) < 15, state=UserBuy.adress)
async def del_fsm(message:Message):
    await message.delete()


@dp.message_handler(state=UserBuy.adress)
async def input_adress_fsm(message:Message, state:FSMContext):
    await state.update_data(adress=message.text)
    await message.answer('Подтвердите адрес кошелька:\n\n'
                         f'<b>{message.text}</b>', reply_markup=kb_adress_go())


@dp.callback_query_handler(text='AdressGO', state='*')
async def go_pay_func(callback:CallbackQuery, state:FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(f'''⚙️ Детали обмена:

📧 Адрес кошелька : 
<code>{data["adress"]}</code> 

💰 Количество приобретаемой валюты : 
<b>{data["result_money"]} {data["money"]}</b> 

💸 Сумма к оплате : 
<b>{data["price"]} ₽</b>.

⬇️Для получения скидки, введите ПРОМО-КОД⬇️''', reply_markup=kb_promokod_go())



@dp.callback_query_handler(text='payments', state='*')
async def finish_pay(callback:CallbackQuery, state:FSMContext):
    await callback.message.edit_text(text=callback.message.html_text)
    await callback.message.answer(f'''Реквизиты для оплаты: 
Оплату принимаем на КАРТУ БАНКА 

👇👇👇
<code>{db.get_karta()}</code>

Или ПО НОМЕРУ ТЕЛЕФОНА
👇👇👇
<code>{db.get_sbp()}</code> 📲 

❗️ВАЖНО ❗️
Переводите точную сумму
Иначе потеряете свои деньги

После успешного перевода денег по указанным реквизитам нажмите на кнопку 
«✅ Я оплатил(а)»
 или же Вы можете отменить данную заявку нажав на кнопку 
«❌ Отменить заявку»

❗️ВАЖНО ❗️
⏱ ЗАЯВКА ДЕЙСТВИТЕЛЬНА
⏱           1️⃣0️⃣ МИНУТ 
⏱ С МОМЕНТА ЕЕ СОЗДАНИЯ''', reply_markup=kb_payments_success())
    await state.finish()



@dp.callback_query_handler(text='Finish_pay')
async def finish_pay_func(callback:CallbackQuery):
    await callback.message.edit_text(callback.message.html_text)
    operator = hlink('оператором', URL_OPERATOR)
    await callback.message.answer(f'''Если Вы перевели неправильную сумму, или валюта не поступила на Ваш адрес в течении 10 мин - свяжитесь с {operator}''', reply_markup=kb_home_finish())
    for i in ADMIN:
        try:
            await bot.send_message(chat_id=i, text=f'Пользователь @{callback.from_user.id} (<code>{callback.from_user.id}</code>) подтвердил оплату')
        except Exception:
            continue



@dp.message_handler(text='👤Мой кошелек👤')
async def my_wallet_func(message:Message):
    await message.answer(f'''<b>💳 Баланс 💳

BTC-адрес: 
<code>{BTC_WALLET}</code>
Баланс: 0.00000000 BTC

LTC-адрес: 
<code>{LTC_WALLET}</code>
Баланс: 0.00000000 LTC</b>''', reply_markup=kb_my_wallet())



@dp.callback_query_handler(text='promo_null', state='*')
async def promo_fake(callback:CallbackQuery):
    await callback.answer('Промокоды закончились', show_alert=True)



@dp.message_handler(text='📤Отправить📤')
async def my_wallet_func(message:Message):
    await message.answer('На вашем балансе недостаточно средств!\n'
                         'Пополните баланс одного из кошельков')


@dp.message_handler(text='📥Пополнить📥')
async def my_wallet_func(message:Message):
    await message.answer(f'''📥 <b>Пополнение баланса 📥

Ваши кошельки:

BTC-адрес: 
<code>{BTC_WALLET}</code>
Баланс: 0.00000000 BTC

LTC-адрес: 
<code>{LTC_WALLET}</code>
Баланс: 0.00000000 LTC

Для пополнения ваших кошельков используйте указанные адреса (чтобы скопировать, просто нажмите на нужный адрес).

Переводы внутри бота занимают всего 5-10 минут!</b>''', reply_markup=kb_pay_money_Wallet())


@dp.message_handler(text='🔗ПАРТНЕРКА🔗')
async def my_wallet_func(message:Message):
    await message.answer(f'''<b>Ваша статистика:
Кол-во сделок: 0
Кол-во рефералов: 0
Кол-во сделок рефералов: 0
Баланс: 0.0
Выведено: 0.0
Ваша ссылка:
https://t.me/{USERNAME_BOT}?start={message.from_user.id}

ВАЖНО! Вывод средств доступен от 500Р на балансе</b>''', reply_markup=kb_parthers())


@dp.message_handler(text='🤑 Вывод средств 🤑')
async def my_wallet_func(message:Message):
    await message.answer('''К сожалению, Вам пока что недоступен вывод средств 😩 
Но не стоит отчаиваться!🦊
Накопи больше бонусов, чтобы воспользоваться данной услугой!👍''', reply_markup=kb_one_menu())


@dp.message_handler(text='📉Продать криптовалюту📉')
async def my_wallet_func(message:Message):
    await message.answer(URL_SELL)


@dp.message_handler(text='🧮Калькулятор🧮')
async def my_wallet_func(message:Message):
    await message.answer('💸 Выберите валюту:', reply_markup=kb_calkulate())



@dp.message_handler(text=['🧮BTC', '🧮LTC'])
async def my_wallet_func(message:Message, state:FSMContext):
    money = message.text[1:]
    await message.answer(f'''🧮 Калькулятор {money} 🧮

(Напишите сумму :  от 300 руб 💶''', reply_markup=kb_cancel_input())
    await state.update_data(money=money)
    await UserCalkulate.amount.set()


@dp.message_handler(lambda message: not message.text.isdigit() or int(message.text) < 300, state=UserCalkulate.amount)
async def chek_fsm(message:Message):
    await message.delete()


@dp.message_handler(state=UserCalkulate.amount)
async def fsm_input_amount(message:Message, state:FSMContext):
    await message.delete()
    data = await state.get_data()
    MONEY_USDT = await get_price(f'{data["money"]}USDT')
    RUBS = await RUB()
    result = float(message.text) / (float(MONEY_USDT) * (float(RUBS)))
    price = int(message.text) * (1 + COMMISSION_PERCENT_SELL / 100)
    await state.update_data(result_money=round(float(result), 7), price=round(float(price), 2))
    await message.answer(f'''Вы получите <b>{round(float(result), 7)} {data["money"]}</b> на {round(float(message.text), 1)} RUB.
С учетом комисии сети сумма к оплате составит {round(float(price), 1)} RUB.
''')
    await state.finish()


@dp.message_handler(text='📜Правила📜')
async def my_wallet_func(message:Message):
    await message.answer(URL_INFO)


@dp.message_handler(text='🗃Отзывы🗃')
async def my_wallet_func(message:Message):
    await message.answer(URL_REWIEV)


@dp.message_handler(text='👨‍💻Оператор👨‍💻')
async def my_wallet_func(message:Message):
    await message.answer(URL_OPERATOR)



@dp.message_handler(commands=['admin'])
async def cmd_admin(message:types.Message):
    if message.from_user.id in ADMIN:
        await message.answer('<b>Вы в админ меню</b>', reply_markup=ikb_menu_admin())



@dp.message_handler(text='Изменить VISA')
async def cmd_admin(message:types.Message):
    if message.from_user.id in ADMIN:
        karta = db.get_karta()
        await message.answer(f'Используется: <code>{karta}</code>\n\n'
                             f'Введите новый номер карты чтобы обновить ее', reply_markup=ikb_stop_admin())
        await UpdatesKarta.karta.set()


@dp.message_handler(state=UpdatesKarta.karta)
async def cmd_admin(message:types.Message, state:FSMContext):
    karta = message.text
    db.update_karta(karta)
    await message.answer('✅ Карта успешно обновлена\n\n'
                         f'Новое значение: <code>{karta}</code>', reply_markup=ikb_menu_admin())
    await state.finish()





@dp.message_handler(text='Изменить СБП')
async def cmd_admin(message:types.Message):
    if message.from_user.id in ADMIN:
        karta = db.get_sbp()
        await message.answer(f'Используется: <code>{karta}</code>\n\n'
                             f'Введите новый номер СБП чтобы обновить ее', reply_markup=ikb_stop_admin())
        await UpdatesSbp.karta.set()


@dp.message_handler(state=UpdatesSbp.karta)
async def cmd_admin(message:types.Message, state:FSMContext):
    karta = message.text
    db.update_sbp(karta)
    await message.answer('✅ Номер СБП успешно обновлен\n\n'
                         f'Новое значение: <code>{karta}</code>', reply_markup=ikb_menu_admin())
    await state.finish()


@dp.message_handler(text='Выйти из режима ввода', state='*')
async def home_back(message:types.Message, state:FSMContext):
    if message.from_user.id in ADMIN:
        await state.finish()
        await message.answer('<b>Админ панель</b>', reply_markup=ikb_menu_admin())





async def on_startup(_):
    await set_default_commands(dp)
    print('Bot started')


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)