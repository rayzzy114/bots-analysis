from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.user import get_user_card, update_user_card


class WalletState(StatesGroup):
    waiting_for_wallet_address = State()

router = Router()

def get_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Моя партнерская программа", callback_data="my_partner")
    kb.button(text="✏️ Мои финансы", callback_data="my_finances")
    kb.button(text="Кошелек для вывода", callback_data="my_wallet")
    kb.button(text="💸 Вывод", callback_data="withdraw")
    kb.button(text="Правила", callback_data="rules")
    kb.button(text="Главное меню", callback_data="back")
    kb.adjust(1, 2, 1, 1, 1, 1)
    return kb.as_markup()

@router.callback_query(F.data.startswith("partner"))
async def partner_crypto_handler(callback: types.CallbackQuery):

    text = (
        "<b>Условия партнерской программы:</b>\n\n"
        "Рекомендуйте наш сервис, стройте команду получайте вознаграждение от каждого обмена привлеченных вами клиентов!\n\n"
        "Минимальная сумма на вывод: 0.0002 BTC\n\n"
        "Вывод средств по запросу!"
    )

    await callback.message.delete()
    await callback.message.answer(
        text, reply_markup=get_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("my_partner"))
async def my_partner_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    text = (
        f"Ваша ссылка для приглашения партнеров:\n\n"
        f"https://t.me/{bot_info.username}?start={user_id}"
    )

    await callback.message.answer(
        text, reply_markup=get_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("my_finances"))
async def my_finances_handler(callback: types.CallbackQuery):
    text = (
        "Количество партнеров в моей команде: 0\n\n"
        "Активные партнеры: 0\n\n"
        "Оплаченных заказов\n\n"
        "На балансе: 0\n\n"
        "Минимальная сумма на вывод: 0.0002 BTC"
    )

    await callback.message.answer(
        text, reply_markup=get_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("my_wallet"))
async def my_wallet_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    adress = await get_user_card(user_id)

    text = (
        f"Ранее вы указали адрес: <code>{adress}</code>\n\n"
        f"Если Вы желаете изменить его, введите Ваш новый BTC адрес:"
    )

    await callback.message.answer(
        text, reply_markup=get_keyboard()
    )
    await state.set_state(WalletState.waiting_for_wallet_address)
    await callback.answer()

@router.message(WalletState.waiting_for_wallet_address)
async def wallet_address_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    new_card = message.text.strip()

    await update_user_card(user_id, new_card)

    await message.answer(f"✅ Ваш BTC адрес успешно обновлен:\n<code>{new_card}</code>")
    await state.clear()

@router.callback_query(F.data.startswith("withdraw"))
async def withdraw_handler(callback: types.CallbackQuery):
    text = (
        "Пока что у Вас нет партнерских вознаграждений.\n\n"
        "Вы сможете запросить вывод средств, если сумма реферальных вознагражении достигла или превышает 0.0002 BTC"
    )

    await callback.message.answer(
        text, reply_markup=get_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rules"))
async def rules_handler(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="Главное меню", callback_data="back")
    kb.adjust(1)

    text = (
        "<b>Обязательства партнера:</b>\n\n"
        "1 ) Регулярная публикация промо-материалов с реферальной ссылкой. Минимум 8 упоминаний в месяц с указанием реферальной ссылки.\n\n\n"
        "2 ) Привлечение нового трафика. Ресурсы, с помощью которых привлекаются клиенты по реферальной ссылке — должны постоянно подпитываться новой аудиторией. Пост-трафик не интересен.\n\n\n"
        "<b>Что запрещено?</b>\n\n\n"
        "1 ) Партнер не может рекламировать конкурентные сервисы, которые как либо связаны с покупкой/продажей BTC.\n\n\n"
        "2 ) Партнер не может использовать бренд «BTC MONOPOLY» в интеграциях/публикациях как либо связанных с серым/черным контентом.\n\n\n"
        "<b>Условия вывода реферальных средств :</b>\n\n\n"
        "1 ) Вывод осуществляется максимум 2 раза в месяц. Партнер должен с менеджером утвердить данные даты и следовать им.\n\n\n"
        "2 ) BTC MONOPOLY не платит за пост-трафик. Соответственно, если партнер прекращает работу с сервисом, он может получить свою последнюю выплату спустя 30 дней с момента завершения сотрудничества. После этого, реферальные деньги блокируются и могут быть выплачены только при возобновлении сотрудничества.\n\n\n"
        "3 ) Вывод осуществляется только на BTC или же Тинькофф по СБП. На QIWI и другие кошельки вывод невозможен.\n\n\n"
        "4 ) Администрация BTC MONOPOLY имеет право в одностороннем порядке завершить сотрудничество с партнером, тем самым аннулировать базу рефералов.\n\n\n"
    )

    await callback.message.answer(
        text, reply_markup=kb.as_markup()
    )
    await callback.answer()
