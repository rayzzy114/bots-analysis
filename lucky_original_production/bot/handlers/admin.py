import asyncio

from aiogram import Router, F, Bot

from aiogram.filters import Command

from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from aiogram.fsm.context import FSMContext

from aiogram.fsm.state import State, StatesGroup

from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update, desc

from sqlalchemy.ext.asyncio import AsyncSession


from core.models import User, Order, OrderStatus, Rate, Setting

from core.config import Config


router = Router()


class AdminSG(StatesGroup):

    menu = State()

    edit_rate = State()

    edit_wallet = State()

    broadcasting = State()


async def is_admin(session: AsyncSession, telegram_id: int) -> bool:


    if str(telegram_id) == str(Config.ADMIN_ID):

        return True



    result = await session.execute(select(User).where(User.telegram_id == telegram_id))

    user = result.scalar_one_or_none()

    return user.is_admin if user else False


@router.message(Command("admin"))

async def cmd_admin(message: Message, state: FSMContext, session: AsyncSession):

    if not await is_admin(session, message.from_user.id):

        return


    await state.clear()

    text = "👑 <b>Админ-панель</b>\n\nВыберите действие:"

    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="📋 Заявки", callback_data="admin_orders"))

    builder.row(InlineKeyboardButton(text="📈 Курсы валют", callback_data="admin_rates"))

    builder.row(InlineKeyboardButton(text="💳 Реквизиты", callback_data="admin_wallets"))

    builder.row(InlineKeyboardButton(text="🔗 Ссылки", callback_data="admin_links"))

    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))


    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "admin_menu")

async def back_to_admin(callback: CallbackQuery, state: FSMContext, session: AsyncSession):

    if not await is_admin(session, callback.from_user.id): return

    await state.clear()

    text = "👑 <b>Админ-панель</b>\n\nВыберите действие:"

    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="📋 Заявки", callback_data="admin_orders"))

    builder.row(InlineKeyboardButton(text="📈 Курсы валют", callback_data="admin_rates"))

    builder.row(InlineKeyboardButton(text="💳 Реквизиты", callback_data="admin_wallets"))

    builder.row(InlineKeyboardButton(text="🔗 Ссылки", callback_data="admin_links"))

    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))


    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")



@router.callback_query(F.data == "admin_orders")

async def admin_orders_list(callback: CallbackQuery, session: AsyncSession):


    query = select(Order).where(Order.status == OrderStatus.PENDING).order_by(desc(Order.created_at)).limit(10)

    result = await session.execute(query)

    orders = result.scalars().all()


    if not orders:

        builder = InlineKeyboardBuilder()

        builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

        await callback.message.edit_text("📭 Нет активных заявок.", reply_markup=builder.as_markup())

        return


    text = "📋 <b>Активные заявки:</b>\n\n"

    builder = InlineKeyboardBuilder()


    for order in orders:

        status_icon = "⏳"

        builder.row(InlineKeyboardButton(

            text=f"{status_icon} #{order.id} | {order.amount_in} {order.currency_in} -> {order.amount_out:.0f} RUB",

            callback_data=f"admin_order_{order.id}"

        ))


    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("admin_order_"))

async def admin_order_detail(callback: CallbackQuery, session: AsyncSession):

    order_id = int(callback.data.split("_")[2])

    result = await session.execute(select(Order).where(Order.id == order_id))

    order = result.scalar_one_or_none()


    if not order:

        await callback.answer("Заявка не найдена")

        return


    text = (

        f"📝 <b>Заявка #{order.id}</b>\n"

        f"👤 User ID: <code>{order.user_id}</code>\n"

        f"🔄 Тип: <b>{order.type.value.upper()}</b>\n"

        f"📥 Вход: {order.amount_in} {order.currency_in}\n"

        f"📤 Выход: {order.amount_out} {order.currency_out}\n"

        f"💳 Метод: {order.payment_method}\n"

        f"🏦 Банк: {order.bank_name or 'Не указан'}\n"

        f"📱 Реквизиты: <code>{order.requisites_phone or order.wallet_address}</code>\n"

        f"👤 ФИО: {order.requisites_fio or 'Не указано'}\n"

        f"📅 Дата: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"

        f"Статус: {order.status.value}"

    )


    builder = InlineKeyboardBuilder()

    builder.row(

        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"adm_confirm_{order.id}"),

        InlineKeyboardButton(text="❌ Отменить", callback_data=f"adm_cancel_{order.id}")

    )

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_orders"))


    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_confirm_"))

async def admin_confirm_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):

    order_id = int(callback.data.split("_")[2])

    result = await session.execute(select(Order).where(Order.id == order_id))

    order = result.scalar_one_or_none()


    if order:

        order.status = OrderStatus.COMPLETED

        await session.commit()



        res_user = await session.execute(select(User).where(User.id == order.user_id))

        user = res_user.scalar_one()

        try:

            await bot.send_message(user.telegram_id, f"✅ <b>Ваша заявка #{order.id} выполнена!</b>\nСредства отправлены на ваши реквизиты.", parse_mode="HTML")

        except:

            pass


        await callback.answer("Заявка подтверждена!")

        await admin_orders_list(callback, session)

    else:

        await callback.answer("Ошибка обновления")


@router.callback_query(F.data.startswith("adm_cancel_"))

async def admin_cancel_order(callback: CallbackQuery, session: AsyncSession, bot: Bot):

    order_id = int(callback.data.split("_")[2])

    result = await session.execute(select(Order).where(Order.id == order_id))

    order = result.scalar_one_or_none()


    if order:

        order.status = OrderStatus.CANCELLED

        await session.commit()



        res_user = await session.execute(select(User).where(User.id == order.user_id))

        user = res_user.scalar_one()

        try:

            await bot.send_message(user.telegram_id, f"❌ <b>Ваша заявка #{order.id} отменена администратором.</b>", parse_mode="HTML")

        except:

            pass


        await callback.answer("Заявка отменена!")

        await admin_orders_list(callback, session)

    else:

        await callback.answer("Ошибка обновления")



@router.callback_query(F.data == "admin_rates")

async def admin_rates_list(callback: CallbackQuery, session: AsyncSession):

    result = await session.execute(select(Rate))

    rates = result.scalars().all()


    text = "📈 <b>Курсы валют:</b>\nВыберите валюту для изменения курса:"

    builder = InlineKeyboardBuilder()


    for rate in rates:

        builder.row(InlineKeyboardButton(

            text=f"{rate.currency}: {rate.buy_rate:,.0f} / {rate.sell_rate:,.0f}",

            callback_data=f"adm_edit_rate_{rate.currency}"

        ))


    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_edit_rate_"))

async def admin_edit_rate_prompt(callback: CallbackQuery, state: FSMContext):

    currency = callback.data.split("_")[3]

    await state.update_data(editing_currency=currency)

    await state.set_state(AdminSG.edit_rate)


    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="Отмена", callback_data="admin_rates"))


    await callback.message.edit_text(

        f"✏️ Введите новый курс для <b>{currency}</b> в формате:\n<code>ПОКУПКА ПРОДАЖА</code>\n\nПример: <code>6850000 6600000</code>",

        reply_markup=builder.as_markup(),

        parse_mode="HTML"

    )


@router.message(AdminSG.edit_rate)

async def admin_save_rate(message: Message, state: FSMContext, session: AsyncSession):

    try:

        buy, sell = map(float, message.text.split())

        data = await state.get_data()

        currency = data['editing_currency']


        await session.execute(

            update(Rate).where(Rate.currency == currency).values(buy_rate=buy, sell_rate=sell)

        )

        await session.commit()


        await message.answer(f"✅ Курс {currency} обновлен!")


        await cmd_admin(message, state, session)

    except ValueError:

        await message.answer("❌ Неверный формат. Введите два числа через пробел.")



@router.callback_query(F.data == "admin_wallets")

async def admin_wallets_menu(callback: CallbackQuery):

    text = "💳 <b>Управление реквизитами</b>\nЧто хотите изменить?"

    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="👛 Кошельки (Продажа)", callback_data="adm_set_wallets"))

    builder.row(InlineKeyboardButton(text="🏦 Карты/СБП (Покупка)", callback_data="adm_set_reqs"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "adm_set_wallets")

async def admin_wallets_list(callback: CallbackQuery):

    currencies = ["BTC"]

    builder = InlineKeyboardBuilder()

    for cur in currencies:

        builder.row(InlineKeyboardButton(text=f"👛 {cur}", callback_data=f"adm_edit_wallet_{cur}"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_wallets"))

    await callback.message.edit_text("Выберите валюту для смены кошелька:", reply_markup=builder.as_markup())


@router.callback_query(F.data == "adm_set_reqs")
async def admin_reqs_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Изменить Карту", callback_data="adm_edit_req_val"))
    builder.row(InlineKeyboardButton(text="🏦 Изменить Название Банка", callback_data="adm_edit_req_bank"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_wallets"))

    await callback.message.edit_text("⚙️ <b>Настройка реквизитов (Покупка)</b>\n\nВыберите, какой параметр вы хотите изменить:", reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_edit_req_"))
async def admin_edit_req_prompt(callback: CallbackQuery, state: FSMContext):
    target = callback.data.replace("adm_edit_req_", "")
    key = "requisites_global" if target == "val" else "requisites_bank"
    label = "Номер карты" if target == "val" else "Название банка"
    
    await state.update_data(editing_key=key, editing_label=label)
    await state.set_state(AdminSG.edit_wallet)
    
    await callback.message.edit_text(f"✏️ Введите новое значение для: <b>{label}</b>", parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm_edit_wallet_"))

async def admin_edit_wallet_prompt(callback: CallbackQuery, state: FSMContext):

    currency = callback.data.split("_")[3]

    await state.update_data(editing_key=f"wallet_{currency}", editing_label=f"Кошелек {currency}")

    await state.set_state(AdminSG.edit_wallet)

    await callback.message.edit_text(f"✏️ Введите новый адрес кошелька для <b>{currency}</b>:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_wallets")]]))


@router.callback_query(F.data == "admin_links")

async def admin_links_menu(callback: CallbackQuery):

    text = "🔗 <b>Управление ссылками</b>\nЧто хотите изменить?"

    builder = InlineKeyboardBuilder()

    builder.row(InlineKeyboardButton(text="Отзывы", callback_data="adm_edit_link_reviews"))

    builder.row(InlineKeyboardButton(text="Новости", callback_data="adm_edit_link_news"))

    builder.row(InlineKeyboardButton(text="Поддержка", callback_data="adm_edit_link_support"))

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm_edit_link_"))

async def admin_edit_link_prompt(callback: CallbackQuery, state: FSMContext):

    target = callback.data.split("_")[3]

    await state.update_data(editing_key=f"link_{target}", editing_label=f"Ссылка ({target})")

    await state.set_state(AdminSG.edit_wallet)

    await callback.message.edit_text(f"✏️ Введите новую ссылку для <b>{target}</b>:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="admin_links")]]))


@router.message(AdminSG.edit_wallet)

async def admin_save_setting(message: Message, state: FSMContext, session: AsyncSession):

    data = await state.get_data()

    key = data['editing_key']

    value = message.text.strip()



    res = await session.execute(select(Setting).where(Setting.key == key))

    setting = res.scalar_one_or_none()

    if setting:

        setting.value = value

    else:

        session.add(Setting(key=key, value=value))


    await session.commit()
    await message.answer(f"✅ <b>{data['editing_label']}</b> успешно обновлен на:\n<code>{value}</code>", parse_mode="HTML")
    await cmd_admin(message, state, session)

