"""Обмен: валюта → сумма (калькулятор) → адрес → оплата (clone_spec §7.2)."""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .. import calc as calc_mod
from .. import constants as const
from .. import keyboards as kb
from .. import media, renderer, texts, utils
from ..runtime import AppContext
from ..states import AddCoinSG, ExchangeSG
from .start import show_main_menu

log = logging.getLogger(__name__)
router = Router(name="exchange")

MSK = timezone(timedelta(hours=3))
COIN_BY_BUTTON = {v: k for k, v in kb.COIN_BTN.items()}

# держим ссылки на фоновые задачи (⏳-транзиент), чтобы их не собрал GC
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


# --- helpers ----------------------------------------------------------------
def _order_id() -> str:
    return secrets.token_hex(12)


def _active_until() -> str:
    return (datetime.now(MSK) + timedelta(minutes=30)).strftime("%H:%M %d/%m MSK")


def _valid_address(coin: str, address: str) -> bool:
    a = address.strip()
    if " " in a or len(a) < 16:
        return False
    lengths = {"btc": (26, 62), "ltc": (26, 48), "xmr": (90, 110), "usdt": (30, 60)}
    lo, hi = lengths.get(coin, (16, 120))
    return lo <= len(a) <= hi


async def _show_calc(message: Message, state: FSMContext, ctx: AppContext, *, edit: bool) -> None:
    data = await state.get_data()
    text, markup = calc_mod.render_calc(data, ctx.settings)
    if edit and data.get("calc_msg_id"):
        try:
            await message.bot.edit_message_text(
                text, chat_id=message.chat.id, message_id=data["calc_msg_id"], reply_markup=markup
            )
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("calc edit failed: %s", exc)
    sent = await message.answer(text, reply_markup=markup)
    await state.update_data(calc_msg_id=sent.message_id)


async def _start_amount(message: Message, state: FSMContext, ctx: AppContext, coin: str) -> None:
    try:
        rate = await ctx.rates.get(coin)
    except Exception as exc:  # noqa: BLE001
        log.warning("rate fetch failed for %s: %s", coin, exc)
        rate = 0.0
    bonus = int(ctx.users.get(str(message.from_user.id), {}).get("bonus_available", ctx.settings.start_bonus))
    await state.set_state(ExchangeSG.waiting_amount)
    await state.update_data(coin=coin, rate=rate, rub=0, burn=False, mode="default",
                            pad="", unit="coin", bonus_available=bonus, calc_msg_id=None)
    await message.answer(
        renderer.render(texts.ENTER_AMOUNT, ctx.settings, ticker=const.COINS[coin]["ticker"]),
        reply_markup=kb.REMOVE,
    )
    await _show_calc(message, state, ctx, edit=False)


# === Старт обмена ===========================================================
@router.message(F.text == kb.BTN_NEW_EXCHANGE)
@router.message(F.text == kb.BTN_NEW_EXCHANGE2)
async def new_exchange(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await message.answer(
        renderer.render(texts.EXCHANGE_CLARIFY, ctx.settings),
        reply_markup=kb.kb_operator(ctx.settings),
    )
    await message.answer(texts.CHOOSE_COIN, reply_markup=kb.kb_choose_coin())


@router.message(F.text.in_(set(COIN_BY_BUTTON)))
async def choose_coin(message: Message, state: FSMContext, ctx: AppContext) -> None:
    coin = COIN_BY_BUTTON[message.text]
    if coin == "usdt":
        # доп. шаг скидки только у USDT
        await message.answer(renderer.render(texts.USDT_DISCOUNT, ctx.settings))
        await utils.human_delay()  # «активирую скидку» 2–4 c
        await message.answer(texts.USDT_DISCOUNT_OK)
    await _start_amount(message, state, ctx, coin)


@router.message(F.text == kb.BTN_NO_OTHER)
async def need_other(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.set_state(AddCoinSG.waiting_name)
    await message.answer(
        renderer.render(texts.NEED_OTHER_TITLE, ctx.settings),
        reply_markup=kb.kb_operator(ctx.settings),
    )
    await message.answer(texts.NEED_OTHER_BODY, reply_markup=kb.kb_back())


@router.message(AddCoinSG.waiting_name, F.text == kb.BTN_BACK)
async def need_other_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)


@router.message(AddCoinSG.waiting_name, F.text)
async def need_other_name(message: Message, state: FSMContext, ctx: AppContext) -> None:
    name = message.text.strip()
    await state.clear()
    await message.answer(
        renderer.render(texts.NEED_OTHER_ACCEPTED, ctx.settings, name=name),
    )
    await show_main_menu(message, ctx)


# === Калькулятор ============================================================
@router.message(ExchangeSG.waiting_amount, F.text == kb.BTN_BACK)
async def amount_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await new_exchange(message, state, ctx)


@router.message(ExchangeSG.waiting_amount, F.text)
async def amount_input(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    parsed = calc_mod.parse_amount(message.text, data["coin"], data["rate"], ctx.settings.min_rub(data["coin"]))
    # убрать введённую сумму из истории чата (как в оригинале — суммы не копятся)
    await utils.safe_delete(message)
    if parsed is None:
        return
    rub, _ = parsed
    await state.update_data(rub=rub, pad="")
    await _show_calc(message, state, ctx, edit=True)


@router.callback_query(ExchangeSG.waiting_amount, F.data.startswith("calc:"))
async def calc_cb(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    action = cb.data[len("calc:"):]
    coin, rate = data["coin"], float(data["rate"])
    min_rub = ctx.settings.min_rub(coin)
    unit = data.get("unit", "coin")

    if action == "old":
        await state.update_data(mode="pad")
    elif action == "min":
        # МИН ОБМЕН задаёт брутто-сумму = минимум (в рублях); набор сбрасываем
        await state.update_data(rub=min_rub, pad="")
        _spawn(utils.transient_message(cb.message, text="🧮"))  # счёты мелькают ~2с
    elif action == "burn":
        await state.update_data(burn=not data.get("burn", False))
        _spawn(utils.transient_message(cb.message, sticker=media.burn_sticker()))  # заяц ~2с
    elif action == "unit":
        # переключение монета↔RUB: начинаем ввод заново в новом режиме
        await state.update_data(unit="rub" if unit == "coin" else "coin", pad="", rub=0)
    elif action in ("digit", "dot", "back") or action.startswith("digit:"):
        pad = data.get("pad", "")
        if action.startswith("digit:"):
            pad += action.split(":", 1)[1]
        elif action == "dot":
            pad = pad if "." in pad else (pad + ".")
        elif action == "back":
            pad = pad[:-1]
        rub = 0.0
        if pad and pad != ".":
            try:
                val = float(pad)
                # COIN-режим: набор = монета → брутто = монета×курс; RUB-режим: брутто = рубли
                rub = val * rate if unit == "coin" else val
            except ValueError:
                rub = 0.0
        await state.update_data(pad=pad, rub=rub)
    elif action == "nav_back":
        await cb.answer()
        await utils.safe_delete(cb.message)
        await new_exchange(cb.message, state, ctx)
        return
    elif action == "done":
        if float(data.get("rub", 0)) < min_rub:
            return await cb.answer(texts.ALERT_BELOW_MIN, show_alert=True)
        await _go_to_address(cb, state, ctx)
        return

    fresh = await state.get_data()
    text, markup = calc_mod.render_calc(fresh, ctx.settings)
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:  # noqa: BLE001
        pass
    await cb.answer()


# === Адрес ==================================================================
async def _go_to_address(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    rub = float(data["rub"])
    coin = data["coin"]
    discount = int(data.get("bonus_available", 0)) if data.get("burn") else 0
    cashback = calc_mod.cashback_for(rub, ctx.settings.cashback_percent)
    await state.set_state(ExchangeSG.waiting_address)
    await state.update_data(rub=rub, discount=discount, cashback=cashback)
    await cb.answer()
    # если есть сохранённые адреса этой монеты — предложить их кнопками (issue 5)
    saved = [w.get("address", "") for w in ctx.wallets.list_for(cb.from_user.id, coin)
             if w.get("address")]
    markup = kb.kb_saved_addresses(saved) if saved else kb.kb_back()
    await cb.message.answer(
        renderer.render(texts.ENTER_ADDRESS, ctx.settings, ticker=const.COINS[coin]["ticker"]),
        reply_markup=markup,
    )


@router.message(ExchangeSG.waiting_address, F.text == kb.BTN_BACK)
async def address_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    await _start_amount(message, state, ctx, data["coin"])


@router.message(ExchangeSG.waiting_address, F.text.in_({kb.BTN_START_EXCHANGE}))
async def address_start(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await _create_order(message, state, ctx)


@router.message(ExchangeSG.waiting_address, F.text.in_({kb.BTN_REMEMBER_ADDR}))
async def address_remember(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    if data.get("address"):
        await ctx.wallets.add(message.from_user.id, data["coin"], data["address"])
    await message.answer(texts.ADDRESS_REMEMBERED, reply_markup=kb.kb_address_remembered())


@router.message(ExchangeSG.waiting_address, F.text.in_({kb.BTN_FORGET_ADDR}))
async def address_forget(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await message.answer(
        texts.WALLET_VALID, reply_markup=kb.kb_address_valid()
    )


@router.message(ExchangeSG.waiting_address, F.text)
async def address_input(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["coin"]
    address = message.text.strip()
    # порядок как в записи: статус → ⏳ → стикер 💻 → результат
    checking = await message.answer(texts.WALLET_CHECKING)
    _spawn(utils.transient_hourglass(message, reply_to=checking.message_id))
    await utils.send_sticker(message, const.STICKER_WALLET_CHECK)
    await utils.human_delay()  # «проверка» 2–4 c
    await utils.safe_delete(checking)  # убрать «Проверка кошелька...» после проверки (issue 8)
    if _valid_address(coin, address):
        await state.update_data(address=address)
        await message.answer(texts.WALLET_VALID, reply_markup=kb.kb_address_valid())
    else:
        await message.answer(texts.WALLET_INVALID)
        await message.answer(texts.TRY_AGAIN, reply_markup=kb.kb_back())


# === Оплата =================================================================
async def _create_order(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["coin"]
    rub = float(data["rub"])
    rate = float(data["rate"])
    order_id = _order_id()
    active_until = _active_until()
    await state.set_state(ExchangeSG.awaiting_payment)
    await state.update_data(order_id=order_id, active_until=active_until)
    await ctx.orders.put(order_id, {
        "user_id": message.from_user.id, "coin": coin, "rub": rub,
        "address": data.get("address", ""), "status": "awaiting_payment",
    })
    quote = calc_mod.build_quote(
        coin, rub, rate, ctx.settings.commission_percent,
        ctx.settings.cashback_percent, int(data.get("discount", 0)),
    )
    await message.answer(
        renderer.render(texts.EXCHANGE_WAIT_PAYMENT, ctx.settings),
        reply_markup=kb.kb_operator(ctx.settings),
    )
    # реквизиты выдаём не моментально: ⏳ + пауза 2–4 с (issue 1)
    _spawn(utils.transient_hourglass(message))
    await utils.human_delay()
    await message.answer(
        renderer.render(
            texts.PAYMENT_DETAILS, ctx.settings,
            coin_emoji=const.COINS[coin]["emoji"],
            coin_amount=renderer.fmt_coin(quote.coin_amount, coin),
            ticker=const.COINS[coin]["ticker"], address=data.get("address", ""),
            requisites=ctx.settings.requisites, bank=ctx.settings.bank,
            payable=renderer.fmt_rub_space(quote.payable),
            discount=quote.discount, cashback=quote.cashback,
            order_id=order_id, active_until=active_until,
        ),
        reply_markup=kb.kb_payment(),
    )
    await message.answer(texts.PAYMENT_HINT)


@router.message(ExchangeSG.awaiting_payment, F.text == kb.BTN_CHECK_PAYMENT)
async def check_payment(message: Message, state: FSMContext, ctx: AppContext) -> None:
    # стикер 🏃 + «Проверка оплаты...»; через 5 с убираем статус и просим чек (issue 10)
    await utils.send_sticker(message, const.STICKER_PAYMENT_CHECK)
    checking = await message.answer(texts.PAYMENT_CHECKING, reply_markup=kb.kb_payment_checking())
    _spawn(utils.transient_hourglass(message, reply_to=checking.message_id))
    await asyncio.sleep(5)  # «Проверка оплаты...» висит ровно 5 с
    await utils.safe_delete(checking)
    # §9: просим скрин/PDF чека о переводе; снимаем нижние кнопки «отменить обмен/…» (issue 11)
    await message.answer(texts.PROOF_REQUEST, reply_markup=kb.REMOVE)
    await state.set_state(ExchangeSG.awaiting_proof)


@router.message(ExchangeSG.awaiting_payment, F.text == kb.BTN_RECENT)
@router.message(ExchangeSG.awaiting_proof, F.text == kb.BTN_RECENT)
async def recent_orders(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await message.answer(
        renderer.render(texts.PARALLEL_UNAVAILABLE, ctx.settings),
        reply_markup=kb.kb_payment_checking(),
    )


@router.message(ExchangeSG.awaiting_payment, F.text == kb.BTN_CANCEL_EXCHANGE)
@router.message(ExchangeSG.awaiting_proof, F.text == kb.BTN_CANCEL_EXCHANGE)
async def cancel_ask(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await message.answer(texts.CANCEL_CONFIRM, reply_markup=kb.kb_cancel_confirm())


@router.callback_query(F.data == "go:main")
async def cb_go_main(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    # инлайн-кнопка «🏠 Главное меню» на финальном «Спасибо…» (issue 3)
    await cb.answer()
    await state.clear()
    await show_main_menu(cb.message, ctx)


@router.message(F.text == kb.BTN_YES2)
async def cancel_yes(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)


@router.message(F.text == kb.BTN_BACK2)
async def cancel_no(message: Message, state: FSMContext, ctx: AppContext) -> None:
    # вернуться к экрану оплаты
    data = await state.get_data()
    if data.get("order_id"):
        await message.answer(texts.PAYMENT_CHECKING, reply_markup=kb.kb_payment())
    else:
        await show_main_menu(message, ctx)


@router.message(ExchangeSG.awaiting_proof, F.document | F.photo)
async def receive_proof(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    order_id = data.get("order_id", "?")
    coin = data.get("coin", "?")
    rub = float(data.get("rub", 0))
    rate = float(data.get("rate", 0))
    discount = int(data.get("discount", 0))
    quote = calc_mod.build_quote(coin, rub, rate, ctx.settings.commission_percent,
                                 ctx.settings.cashback_percent, discount) if rate else None
    coin_amount = renderer.fmt_coin(quote.coin_amount, coin) if quote else "?"
    payable = renderer.fmt_rub_space(quote.payable if quote else rub)
    ticker = const.COINS.get(coin, {}).get("ticker", coin)
    u = message.from_user
    username = f"@{u.username}" if u.username else "—"

    summary = (
        "📥 <b>Подтверждение оплаты</b>\n"
        f"Заявка: <code>{order_id}</code>\n"
        f"Клиент: <code>{u.id}</code> {username}\n"
        f"Монета: <b>{ticker}</b>\n"
        f"К оплате: <b>{payable} ₽</b>\n"
        f"К получению: <b>{coin_amount} {ticker}</b>\n"
        f"Скидка: {discount}  |  Комиссия: {ctx.settings.commission_percent:g}%\n"
        f"Адрес: <code>{data.get('address', '')}</code>"
    )
    # уведомить администраторов: сводка + сам файл
    for admin_id in ctx.admin_ids:
        try:
            await message.bot.send_message(admin_id, summary)
            await message.forward(admin_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("notify admin %s failed: %s", admin_id, exc)
    # ответ пользователю: «Спасибо…» с кнопками Оператор / Главное меню (issue 3)
    await message.answer(texts.PROOF_RECEIVED, reply_markup=kb.kb_proof_done(ctx.settings))


@router.message(ExchangeSG.awaiting_proof, F.text)
async def proof_need_file(message: Message, state: FSMContext, ctx: AppContext) -> None:
    # прислали текст вместо файла — напоминаем (кнопки отмена/недавние обработаны выше)
    await message.answer(texts.PROOF_NEED_FILE, reply_markup=kb.kb_payment_checking())
