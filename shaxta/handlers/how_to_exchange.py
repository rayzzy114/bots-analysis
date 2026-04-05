from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, InputMediaPhoto
import asyncio

router = Router()

@router.callback_query(F.data.startswith("how_to_exchange"))
async def how_to_exchange_handler(callback: types.CallbackQuery):
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="Назад", callback_data="back")
    
        kb.adjust(1)

        caption = (
            """
ПОКУПКА КРИПТОВАЛЮТЫ
1.Для покупки криптовалюты  в сплывающем окне нажмите кнопку «КУПИТЬ»
2.В сплывающем окне выберите валюту для покупки и нажмите на соответствующую кнопку:BTC,LTC,ETH,XMR
3.Далее,в сплывающем окне нажмите «ОПЛАТА ЛЮБОЙ КАРТОЙ»
4.После нажатия кнопки «ОПЛАТА ЛЮБОЙ КАРТОЙ» Вы увидите всплывающее окно с текущим курсом.
5.Проверив курс валюты,введите количество монет,сколько хотите купить,в строку «ОТПРАВИТЬ СООБЩЕНИЕ»,после чего нажмите  значек «ОТПРАВИТЬ».
6.Появится сообщение «ВВЕДИТЕ АДРЕС  ПОЛУЧЕНИЯ»,после этого введите реквизиты кошелька,куда бы вы хотели получить средства и нажмите  кнопку «ОТПРАВИТЬ»
7.Появится всплывающее окно, оплатите  сумму покупки и нажмите кнопку «ОПЛАТИЛ»
8.После оплаты ожидайте поступления средств на указанный вами кошелек.Средства поступают в течение 20-40 минут,что связано с техническим процессом.

ПРОДАЖА КРИПТОВАЛЮТЫ
1.В панели управления нажмите кнопку «ПРОДАТЬ»
2.В всплывающем окне нажмите кнопку «BTC»
3.В всплывающем окне ознакомьтесь с текущим курсом продажи и в строке чата введите сумму,какую хотите продать.Нажмите кнопку «ОТПРАВИТЬ»
4.Введите номер карты для получения средств.
5.В всплывающем окне ознакомьтесь с суммой ,которая будет отправлена на вашу карту,после чего скопируйте кошелек для перевода  криптовалюты , вставьте его в строку чата и нажмите кнопку «ОПЛАТИЛ».
6.После зачисления средств на указанный кошелек,вам на карту будут перечислены средства.
            """""
        )
        try:
            await callback.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile("media/how_to_exchange.jpg")
                )
            )
            await asyncio.sleep(0.5)
            await callback.message.answer(
                caption,
                reply_markup=kb.as_markup()
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=FSInputFile("media/how_to_exchange.jpg")
            )
            await asyncio.sleep(0.5)
            await callback.message.answer(
                caption,
                reply_markup=kb.as_markup()
            )
        await callback.answer()
    except Exception as e:
        await callback.answer()
        print(f"Ошибка на [how_to_exchange_handler]: {e}")
