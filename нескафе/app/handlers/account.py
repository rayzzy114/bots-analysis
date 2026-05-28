"""Личный кабинет + сохранённые кошельки CRUD (clone_spec §7.3)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from .. import constants as const
from .. import keyboards as kb
from .. import renderer, texts
from ..renderer import ID_EMOJI
from ..runtime import AppContext
from ..states import WalletsSG
from .exchange import _valid_address
from .start import show_main_menu

router = Router(name="account")

COIN_BY_WALLET_BTN = {v: k for k, v in kb.COIN_WALLET_BTN.items()}


# === Личный кабинет =========================================================
@router.message(F.text == kb.BTN_ACCOUNT)
async def account(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    user = ctx.users.get(str(message.from_user.id), {})
    await message.answer(
        renderer.render(texts.ACCOUNT_TITLE, ctx.settings),
        reply_markup=kb.kb_operator(ctx.settings),
    )
    await message.answer(
        renderer.render(
            texts.ACCOUNT_BODY, ctx.settings,
            bonus_available=f"{float(user.get('bonus_available', ctx.settings.start_bonus)):.1f}",
            bonus_used=f"{float(user.get('bonus_used', 0)):.1f}",
            ref_link=ctx.settings.ref_link(message.from_user.id),
            invited=int(user.get("invited", 0)),
        ),
        reply_markup=kb.kb_account(), disable_web_page_preview=True,
    )


@router.message(F.text == kb.BTN_BONUS_HISTORY)
async def bonus_history(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await message.answer(texts.BONUS_HISTORY_EMPTY, reply_markup=kb.kb_back_home())


@router.message(F.text == kb.BTN_SAVED_WALLETS)
async def saved_wallets(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.set_state(WalletsSG.choose_coin)
    await message.answer(texts.WALLETS_INTRO, reply_markup=kb.kb_wallets_choose_coin())


# === Список адресов выбранной монеты ========================================
def _render_list(ctx: AppContext, user_id: int, coin: str) -> str:
    ticker = const.COINS[coin]["ticker"]
    items = ctx.wallets.list_for(user_id, coin)
    if not items:
        return renderer.render(texts.WALLETS_LIST_EMPTY, ctx.settings, ticker=ticker)
    blocks = [renderer.render(texts.WALLETS_LIST_HEADER, ctx.settings, ticker=ticker)]
    for i, it in enumerate(items):
        blocks.append(renderer.render(
            texts.WALLETS_LIST_ITEM, ctx.settings,
            id_emoji=ID_EMOJI[i] if i < len(ID_EMOJI) else f"#{i+1}",
            label=it.get("label", ""), address=it.get("address", ""),
        ))
    return "\n\n".join(blocks)


async def _show_list(message: Message, state: FSMContext, ctx: AppContext, coin: str) -> None:
    await state.set_state(WalletsSG.browsing)
    await state.update_data(wallet_coin=coin)
    await message.answer(_render_list(ctx, message.from_user.id, coin), reply_markup=kb.kb_wallets_list())


@router.message(WalletsSG.choose_coin, F.text.in_(set(COIN_BY_WALLET_BTN)))
async def choose_wallet_coin(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await _show_list(message, state, ctx, COIN_BY_WALLET_BTN[message.text])


@router.message(WalletsSG.choose_coin, F.text == kb.BTN_BACK)
async def wallets_back_to_account(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await account(message, state, ctx)


# === Добавление адреса ======================================================
@router.message(WalletsSG.browsing, F.text == kb.BTN_ADD)
async def wallet_add(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.set_state(WalletsSG.waiting_address)
    await message.answer(texts.WALLET_ADD_PROMPT, reply_markup=kb.kb_back())


@router.message(WalletsSG.waiting_address, F.text == kb.BTN_BACK)
async def wallet_add_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    await _show_list(message, state, ctx, data["wallet_coin"])


@router.message(WalletsSG.waiting_address, F.text)
async def wallet_add_address(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    address = message.text.strip()
    if not _valid_address(coin, address):
        await message.answer(texts.WALLET_INVALID)
        await message.answer(texts.TRY_AGAIN, reply_markup=kb.kb_back())
        return
    await state.set_state(WalletsSG.waiting_label)
    await state.update_data(pending_address=address)
    await message.answer(texts.WALLET_LABEL_PROMPT, reply_markup=kb.kb_skip())


@router.message(WalletsSG.waiting_label, F.text)
async def wallet_add_label(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    label = "" if message.text == kb.BTN_SKIP else message.text.strip()
    await ctx.wallets.add(message.from_user.id, coin, data["pending_address"], label)
    await _show_list(message, state, ctx, coin)


# === Удаление адреса ========================================================
@router.message(WalletsSG.browsing, F.text == kb.BTN_DELETE)
async def wallet_delete(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    items = ctx.wallets.list_for(message.from_user.id, coin)
    await state.set_state(WalletsSG.waiting_delete_id)
    await message.answer(
        renderer.render(texts.WALLET_DELETE_PROMPT, ctx.settings, ticker=const.COINS[coin]["ticker"]),
        reply_markup=kb.kb_wallet_delete(len(items)),
    )


@router.message(WalletsSG.waiting_delete_id, F.text == kb.BTN_BACK)
async def wallet_delete_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    await _show_list(message, state, ctx, data["wallet_coin"])


@router.message(WalletsSG.waiting_delete_id, F.text)
async def wallet_delete_pick(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    items = ctx.wallets.list_for(message.from_user.id, coin)
    if message.text not in ID_EMOJI[:len(items)]:
        await message.answer(texts.WALLET_NOT_FOUND_EMOJI)
        await message.answer(texts.WALLET_NOT_FOUND)
        return
    idx = ID_EMOJI.index(message.text)
    it = items[idx]
    await state.update_data(delete_idx=idx)
    await message.answer(
        renderer.render(texts.WALLET_DELETE_CONFIRM, ctx.settings,
                        ticker=const.COINS[coin]["ticker"],
                        address=it.get("address", ""), label=it.get("label", "")),
        reply_markup=kb.kb_yes_no(),
    )


@router.message(WalletsSG.waiting_delete_id, F.text == kb.BTN_YES)
async def wallet_delete_confirm(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    idx = data.get("delete_idx")
    if idx is not None:
        await ctx.wallets.delete(message.from_user.id, coin, idx)
        await message.answer(texts.WALLET_DELETED)
    await _show_list(message, state, ctx, coin)


@router.message(WalletsSG.waiting_delete_id, F.text == kb.BTN_NO)
async def wallet_delete_cancel(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    await _show_list(message, state, ctx, data["wallet_coin"])


# === Переименование =========================================================
@router.message(WalletsSG.browsing, F.text == kb.BTN_RENAME)
async def wallet_rename(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    items = ctx.wallets.list_for(message.from_user.id, coin)
    if not items:
        await message.answer(texts.WALLET_NOT_FOUND_EMOJI)
        await message.answer(texts.WALLET_NOT_FOUND)
        return
    await state.set_state(WalletsSG.waiting_rename_id)
    await message.answer(
        renderer.render(texts.WALLET_DELETE_PROMPT, ctx.settings, ticker=const.COINS[coin]["ticker"]),
        reply_markup=kb.kb_wallet_delete(len(items)),
    )


@router.message(WalletsSG.waiting_rename_id, F.text == kb.BTN_BACK)
async def wallet_rename_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    await _show_list(message, state, ctx, data["wallet_coin"])


@router.message(WalletsSG.waiting_rename_id, F.text)
async def wallet_rename_pick(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    items = ctx.wallets.list_for(message.from_user.id, coin)
    if message.text not in ID_EMOJI[:len(items)]:
        await message.answer(texts.WALLET_NOT_FOUND_EMOJI)
        await message.answer(texts.WALLET_NOT_FOUND)
        return
    await state.update_data(rename_idx=ID_EMOJI.index(message.text))
    await state.set_state(WalletsSG.waiting_rename)
    await message.answer("🖋 Введите новое название:", reply_markup=kb.kb_back())


@router.message(WalletsSG.waiting_rename, F.text == kb.BTN_BACK)
async def wallet_rename_text_back(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    await _show_list(message, state, ctx, data["wallet_coin"])


@router.message(WalletsSG.waiting_rename, F.text)
async def wallet_rename_text(message: Message, state: FSMContext, ctx: AppContext) -> None:
    data = await state.get_data()
    coin = data["wallet_coin"]
    idx = data.get("rename_idx")
    items = ctx.wallets.list_for(message.from_user.id, coin)
    if idx is not None and 0 <= idx < len(items):
        items[idx]["label"] = message.text.strip()
        await ctx.wallets.put(str(message.from_user.id),
                              {**ctx.wallets.get(str(message.from_user.id), {}), coin: items})
    await _show_list(message, state, ctx, coin)


# === Навигация назад/домой внутри кабинета ==================================
@router.message(WalletsSG.browsing, F.text == kb.BTN_BACK)
async def list_back_to_choose(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.set_state(WalletsSG.choose_coin)
    await message.answer(texts.WALLETS_INTRO, reply_markup=kb.kb_wallets_choose_coin())


@router.message(F.text == kb.BTN_BACK)
async def back_to_menu(message: Message, state: FSMContext, ctx: AppContext) -> None:
    await state.clear()
    await show_main_menu(message, ctx)
