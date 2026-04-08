import random
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from ..constants import COINS, SELL_BUTTON_TO_COIN
from ..context import AppContext
from ..keyboards import (
    kb_antispam_fire,
    kb_buy_menu,
    kb_cabinet_menu,
    kb_calc_menu,
    kb_contacts,
    kb_main_menu,
    kb_sell_menu,
    kb_sell_order_actions,
    kb_wallet_history_status,
    kb_wallet_menu,
)
from ..states import UserState
from ..telegram_helpers import answer_photo_with_retry, message_user_id
from ..utils import fmt_coin, fmt_money, parse_amount


def build_flow_router(ctx: AppContext, assets_dir: str) -> Router:
    router = Router(name="flow")
    assets_path = Path(assets_dir)

    @router.message(StateFilter("*"), F.text == "/start")
    @router.message(StateFilter("*"), CommandStart())
    async def start_cmd(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is not None and ctx.users.antispam_passed(user_id):
            await state.clear()
            await answer_photo_with_retry(
                message=message,
                photo_path=assets_path / "menu_main.jpg",
                caption="⬇ Выберите меню ниже:",
                reply_markup=kb_main_menu(),
            )
            return
        await state.set_state(UserState.waiting_antispam_fire)
        await message.answer(
            "Сработала антиспам система!\n"
            "❗ ВЫБЕРИТЕ ОГОНЬ, ЧТОБЫ ПРОДОЛЖИТЬ ❗\n"
            "Бот не будет реагировать на сообщения до корректного ввода",
            reply_markup=kb_antispam_fire(),
        )

    @router.message(UserState.waiting_antispam_fire, F.text == "🔥")
    async def antispam_ok(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is not None:
            ctx.users.mark_antispam_passed(user_id)
        await state.clear()
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "menu_main.jpg",
            caption="⬇ Выберите меню ниже:",
            reply_markup=kb_main_menu(),
        )

    @router.message(UserState.waiting_antispam_fire)
    async def antispam_wrong(message: Message) -> None:
        await message.answer("Выберите 🔥", reply_markup=kb_antispam_fire())

    @router.message(F.text == "⬅️ Назад")
    async def back_main(message: Message, state: FSMContext) -> None:
        await state.clear()
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "menu_main.jpg",
            caption="⬇ Выберите меню ниже:",
            reply_markup=kb_main_menu(),
        )

    @router.message(F.text == "❌ Отмена")
    async def cancel_to_main(message: Message, state: FSMContext) -> None:
        await state.clear()
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "menu_main.jpg",
            caption="⬇ Выберите меню ниже:",
            reply_markup=kb_main_menu(),
        )

    @router.message(F.text == "BITMAGNIT MIX")
    async def bitmagnit_mix(message: Message) -> None:
        await message.answer(
            "Выплатим вам чистые монеты на любую биржу!\n\n"
            "Не работаем с мошенничеством, вымогательством, воровством, взломом, "
            "финансированием тер-ма, эксплуатацией дет-й\n\n"
            "@Bitmagnit_support",
            reply_markup=kb_main_menu(),
        )

    @router.message(F.text == "💸 Мой кошелек")
    async def wallet_menu(message: Message) -> None:
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "wallet_menu.jpg",
            caption=(
                "👜 Это твой личный кошелек!\n\n"
                "Здесь ты можешь:\n"
                "    ✅ узнать адреса для депозита\n"
                "    ✅ посмотреть исторю транзакций\n"
                "    ✅ узнать свой баланс"
            ),
            reply_markup=kb_wallet_menu(),
        )

    @router.message(F.text == "📚 История транзакций")
    async def wallet_history(message: Message) -> None:
        await message.answer("Выберите статус транзакций:", reply_markup=kb_wallet_history_status())

    @router.message(F.text == "ОТПРАВЛЕНО")
    async def wallet_sent(message: Message) -> None:
        await message.answer("У вас нет транзакций на отправок <b>BTC</b>", reply_markup=kb_wallet_menu())

    @router.message(F.text == "ПОЛУЧЕНО")
    async def wallet_received(message: Message) -> None:
        await message.answer("У вас нет транзакций на депозитов <b>BTC</b>", reply_markup=kb_wallet_menu())

    @router.message(F.text == "💰 Баланс")
    async def wallet_balance(message: Message) -> None:
        await message.answer(
            "💰 Твой баланс\n\n"
            "BTC - <b>0.000000</b>\n\n"
            "LTC - <b>0.000000</b>\n\n"
            "XMR - <b>0.000000</b>\n\n"
            "USDT - <b>0.00</b>\n\n"
            "TRX - <b>0.00</b>\n\n"
            "ETH - <b>0.000000</b>",
            reply_markup=kb_wallet_menu(),
        )

    @router.message(F.text == "📩 Получить адреса")
    async def wallet_addresses(message: Message) -> None:
        await message.answer(
            "💵 Твои адреса для депозита:\n\n"
            "<b>BTC</b> -\nbc1qufyvwvq39w7udfu8mvurult7wfydddvtldjrsz\n\n"
            "<b>LTC</b> -\nltc1qe5ul4ytn2dzrle7q02fut768nwg94eadrp3mz\n\n"
            "<b>XMR</b> -\n87Y6k8x1u2E7iM4n9wQ7sP3a1zN8fR5tV2cB6kL9pM3x\n\n"
            "<b>USDT(TRC20)</b> -\nTR7NHqJ7kz8XB8Gae6Gv5Ry162rx69n4sl\n\n"
            "<b>TRX</b> -\nTQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE\n\n"
            "<b>ETH</b> -\n0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            reply_markup=kb_wallet_menu(),
        )

    @router.message(F.text == "🔄 Отправить валюту")
    async def wallet_send(message: Message) -> None:
        await message.answer("Функция отправки валюты временно недоступна.", reply_markup=kb_wallet_menu())

    @router.message(F.text == "📈 Купить")
    async def buy_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "buy_choose_coin.jpg",
            caption="Выберите валюту",
            reply_markup=kb_buy_menu(),
        )

    @router.message(F.text == "📉 Продать")
    async def sell_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "sell_choose_coin.jpg",
            caption="Выберите валюту",
            reply_markup=kb_sell_menu(),
        )

    @router.message(F.text == "🧮 Калькулятор")
    async def calc_start(message: Message, state: FSMContext) -> None:
        await state.set_state(UserState.waiting_calc_amount)
        await message.answer("Выберите валюту", reply_markup=kb_calc_menu())

    @router.message(F.text.in_({"BTC", "LTC", "XMR", "USDT", "TRX", "ETH"}))
    async def calc_coin_selected(message: Message, state: FSMContext) -> None:
        await state.update_data(calc_coin=(message.text or "").lower())
        await state.set_state(UserState.waiting_calc_amount)
        await message.answer(f"Введите значение для <b>{message.text}</b> в <b>РУБЛЯХ</b>")

    @router.message(UserState.waiting_calc_amount)
    async def calc_amount(message: Message, state: FSMContext) -> None:
        parsed = parse_amount(message.text or "")
        if parsed is None:
            await message.answer("⚠️ Введите корректную сумму (например: 1000 или 0.01 btc).")
            return
        amount = parsed.value
        data = await state.get_data()
        coin = str(data.get("calc_coin", "xmr"))
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin, 1.0)

        # If input was in coin, calculate RUB. If in RUB (or unknown), calculate coin.
        is_coin_input = False
        if parsed.currency == "RUB":
            is_coin_input = False
        elif parsed.currency in (coin.upper(), "BTC", "LTC", "ETH", "XMR", "TRX", "USDT"):
            is_coin_input = True
        else:
            # Guess: if amount < 5, assume coin
            is_coin_input = amount < 5

        if is_coin_input:
            rub_amount = amount * rate
            coin_amount = amount
        else:
            rub_amount = amount
            coin_amount = amount / max(rate, 0.0000001)

        await message.answer(
            f"💰 <b>Результат расчета:</b>\n\n"
            f"💵 <b>{fmt_money(rub_amount)} RUB</b>\n"
            f"🪙 <b>{fmt_coin(coin_amount)} {COINS[coin]['symbol']}</b>\n\n"
            f"📊 Курс: 1 {COINS[coin]['symbol']} = {fmt_money(rate)} RUB",
            reply_markup=kb_cabinet_menu(),
        )
        await state.clear()

    @router.message(F.text == "💻 Личный кабинет")
    async def cabinet(message: Message) -> None:
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "cabinet_profile.jpg",
            caption=(
                "Ваш уникальный ID: <b>6131246501</b>\n"
                "Количество обменов: <b>0</b>\n"
                "Количество рефералов: <b>0</b>\n"
                "Количество рефералов с обменами:\n"
                "Реферальный уровень: <b>1 (3%)</b>\n"
                "Реферальный счет: <b>0 RUB</b>\n"
                "Кешбэк: <b>0 RUB</b>\n\n"
                "Ваша реферальная ссылка:\n"
                "https://telegram.me/BITMAGNIT_BOT?start=6131246501"
            ),
            reply_markup=kb_cabinet_menu(),
        )

    @router.message(F.text == "🎰 Испытай удачу")
    async def cabinet_luck(message: Message) -> None:
        discount = random.randint(10, 35)
        await message.answer(
            f"Вы испытали удачу 🤑! Теперь ваша скидка составляет <b>{discount} RUB</b>",
            reply_markup=kb_cabinet_menu(),
        )

    @router.message(F.text == "Вывести кешбек")
    async def cabinet_cashback(message: Message) -> None:
        await message.answer(
            "⛔️ Минимальная сумма вывода <b>1000 RUB</b>\n"
            "💳 Ваш кешбек: <b>0 RUB</b>",
            reply_markup=kb_cabinet_menu(),
        )

    @router.message(F.text == "Вывести реф. счет")
    async def cabinet_ref(message: Message) -> None:
        await message.answer(
            "⛔️ Минимальная сумма вывода <b>1000 RUB</b>\n"
            "💳 Ваш счет: <b>0 RUB</b>",
            reply_markup=kb_cabinet_menu(),
        )

    @router.message(F.text == "🏷 Промокод")
    async def cabinet_promo(message: Message, state: FSMContext) -> None:
        await state.set_state(UserState.waiting_promo)
        await message.answer("Введите промокод ниже:")

    @router.message(UserState.waiting_promo)
    async def cabinet_promo_input(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("⛔️ Некорректный промокод, попробуйте еще раз", reply_markup=kb_cabinet_menu())

    @router.message(F.text == "📱 Контакты")
    async def contacts(message: Message) -> None:
        caption = ctx.settings.process_text("⬇ Наши контакты")
        await answer_photo_with_retry(
            message=message,
            photo_path=assets_path / "contacts.jpg",
            caption=caption,
            reply_markup=kb_contacts(ctx.settings.all_links()),
        )

    @router.message(F.text.in_(set(SELL_BUTTON_TO_COIN.keys())))
    async def sell_choose_coin(message: Message, state: FSMContext) -> None:
        coin = SELL_BUTTON_TO_COIN[message.text or ""]
        symbol = COINS[coin]["symbol"]
        await state.set_state(UserState.waiting_sell_amount)
        await state.update_data(sell_coin=coin)
        await message.answer(f"ВВОДИ СУММУ В <b>{symbol}</b>:\nпример: <b>0.001</b>")

    @router.message(UserState.waiting_sell_amount)
    async def sell_amount(message: Message, state: FSMContext) -> None:
        parsed = parse_amount(message.text or "")
        if parsed is None:
            await message.answer("⚠️ Введите корректную сумму (например: 0.01 btc).")
            return

        amount = parsed.value
        data = await state.get_data()
        coin = str(data.get("sell_coin", "btc"))
        symbol = COINS[coin]["symbol"]
        rates = await ctx.rates.get_rates()
        rate = rates.get(coin, 1.0)

        # Detect if input is in RUB or Coin
        is_coin_input = True
        if parsed.currency == "RUB":
            is_coin_input = False
        elif parsed.currency in (coin.upper(), "BTC", "LTC", "ETH", "XMR", "TRX", "USDT"):
            is_coin_input = True
        else:
            # For selling, if amount > 5 assume RUB, else coin
            is_coin_input = amount < 5

        if is_coin_input:
            coin_amount = amount
            base_rub = amount * rate
        else:
            base_rub = amount
            coin_amount = amount / max(rate, 0.0000001)

        commission_percent = ctx.settings.commission_percent
        # For selling, usually we pay LESS rub than the market rate, so it's minus commission
        rub_amount = base_rub * (1 - commission_percent / 100)
        rub_int = int(round(rub_amount))

        await state.update_data(
            sell_amount_coin=coin_amount,
            sell_amount_rub=rub_int,
            sell_symbol=symbol,
            sell_method="Номер карты",
        )
        await state.set_state(UserState.waiting_sell_requisites)
        await message.answer(
            f"💰 <b>Вы продаете:</b> {fmt_coin(coin_amount)} {symbol}\n"
            f"💵 <b>Вы получите:</b> {fmt_money(rub_int)} RUB\n\n"
            f"💳 Введите номер карты для получения выплаты (16 цифр):"
        )

    @router.message(UserState.waiting_sell_requisites)
    async def sell_requisites(message: Message, state: FSMContext) -> None:
        requisites = (message.text or "").strip()
        card_digits = "".join(ch for ch in requisites if ch.isdigit())
        if len(card_digits) != 16:
            await message.answer(
                "⛔ Номер карты должен содержать 16 цифр.\n\n"
                "Попробуй ввести номер карты еще раз."
            )
            return
        data = await state.get_data()
        amount_coin = float(data.get("sell_amount_coin", 0))
        amount_rub = int(data.get("sell_amount_rub", 0))
        symbol = str(data.get("sell_symbol", "BTC"))
        user_id = message.from_user.id if message.from_user else 0

        order = ctx.orders.create_order(
            user_id=user_id,
            username=(message.from_user.username if message.from_user else "") or "",
            wallet=card_digits,
            coin_symbol=symbol,
            coin_amount=amount_coin,
            amount_rub=amount_rub,
            payment_method=str(data.get("sell_method", "Номер карты")),
            bank="BTC сеть",
        )
        await state.clear()
        await message.answer(
            f"К оплате: <b>{fmt_coin(amount_coin)} {symbol}</b>\n"
            f"Получишь: <b>{amount_rub} RUB</b>\n"
            f"Реквизиты: {card_digits}",
            reply_markup=kb_sell_order_actions(order["order_id"]),
        )

    return router
