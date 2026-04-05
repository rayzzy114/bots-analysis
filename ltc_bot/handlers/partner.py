from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from db.user import update_user_card, get_user_card

class WalletState(StatesGroup):
    waiting_for_wallet_address = State()

router = Router()

def get_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔗 Моя партнерская ссылка", callback_data="my_partner")
    kb.button(text="✏️ Мои финансы", callback_data="my_finances")
    kb.button(text="Кошелек для вывода", callback_data="my_wallet")
    kb.button(text="💸 Вывод", callback_data="withdraw")
    kb.button(text="Главное меню", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

@router.callback_query(F.data == "partner")
async def partner_handler(callback: types.CallbackQuery):
    text = (
        f"<b>Условия партнерской программы:</b>\n\n"
        f"Рекомендуйте наш сервис, стройте команду и получайте вознаграждение от каждого обмена привлеченных вами клиентов!\n\n"
        f"Минимальная сумма на вывод: 0.0002 BTC\n\n"
        f"Вывод средств по запросу!"
    )

    await callback.message.delete()
    await callback.message.answer(text, reply_markup=get_keyboard())
    await callback.answer()

@router.callback_query(F.data == "my_partner")
async def my_partner_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    text = (
        f"Ваша ссылка для приглашения партнеров:\n\n"
        f"https://t.me/{bot_info.username}?start={user_id}"
    )

    await callback.message.answer(text, reply_markup=get_keyboard())
    await callback.answer()

@router.callback_query(F.data == "my_finances")
async def my_finances_handler(callback: types.CallbackQuery):
    text = (
        f"Количество партнеров в моей команде: 0\n\n"
        f"Активные партнеры: 0\n\n"
        f"Оплаченных заказов: 0\n\n"
        f"На балансе: 0\n\n"
        f"Минимальная сумма на вывод: 0.0002 BTC"
    )

    await callback.message.answer(text, reply_markup=get_keyboard())
    await callback.answer()

@router.callback_query(F.data == "my_wallet")
async def my_wallet_handler(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    adress = await get_user_card(user_id)

    text = (
        f"Ранее вы указали адрес: <code>{adress}</code>\n\n"
        f"Если Вы желаете изменить его, введите Ваш новый BTC адрес:"
    )

    await callback.message.answer(text, reply_markup=get_keyboard())
    await state.set_state(WalletState.waiting_for_wallet_address)
    await callback.answer()

@router.message(WalletState.waiting_for_wallet_address)
async def wallet_address_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    new_card = message.text.strip()

    await update_user_card(user_id, new_card)

    await message.answer(f"✅ Ваш BTC адрес успешно обновлен:\n<code>{new_card}</code>", reply_markup=get_keyboard())
    await state.clear()

@router.callback_query(F.data == "withdraw")
async def withdraw_handler(callback: types.CallbackQuery):
    text = (
        f"Пока что у Вас нет партнерских вознаграждений.\n\n"
        f"Вы сможете запросить вывод средств, если сумма реферальных вознаграждений достигла или превышает 0.0002 BTC"
    )

    await callback.message.answer(text, reply_markup=get_keyboard())
    await callback.answer()