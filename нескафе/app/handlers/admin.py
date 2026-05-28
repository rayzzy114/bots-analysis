"""Админ-панель: правка ссылок/контактов и числовых настроек.

Вход — /admin (только для ADMIN_IDS). Меню инлайн (отдельно от пользовательских
reply-экранов). Смена значения сразу пишется в settings.json и применяется во
всех текстах без рестарта.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import constants as const
from ..runtime import AppContext
from ..states import AdminSG

router = Router(name="admin")


def _ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _kb(rows: list[list[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_home() -> InlineKeyboardMarkup:
    return _kb([
        [_ib("🔗 Ссылки / контакты", "a:links")],
        [_ib("⚙️ Настройки", "a:settings")],
        [_ib("✖ Закрыть", "a:close")],
    ])


def kb_links(settings) -> InlineKeyboardMarkup:
    rows = [[_ib(const.SETTING_LABELS[k], f"a:link:{k}")] for k in const.LINK_KEYS]
    rows.append([_ib("⬅️ В меню", "a:home")])
    return _kb(rows)


def kb_settings() -> InlineKeyboardMarkup:
    rows = [[_ib(const.SETTING_LABELS[k], f"a:num:{k}")] for k in const.NUMERIC_KEYS]
    rows.append([_ib("📉 Минимумы (RUB) по монетам", "a:mins")])
    rows.append([_ib("⬅️ В меню", "a:home")])
    return _kb(rows)


def kb_mins(settings) -> InlineKeyboardMarkup:
    rows = []
    for coin in const.COIN_KEYS:
        ticker = const.COINS[coin]["ticker"]
        rows.append([_ib(f"{ticker}: {settings.min_rub(coin):g} ₽", f"a:min:{coin}")])
    rows.append([_ib("⬅️ Назад", "a:settings")])
    return _kb(rows)


def kb_cancel(target: str) -> InlineKeyboardMarkup:
    return _kb([[_ib("Отмена", target)]])


def _links_body(settings) -> str:
    lines = ["🔗 <b>Ссылки / контакты</b>", "", "Тап по полю — задать новое значение.", ""]
    for k in const.LINK_KEYS:
        lines.append(f"• <b>{const.SETTING_LABELS[k]}</b>\n<code>{settings.get(k)}</code>")
    return "\n".join(lines)


def _settings_body(settings) -> str:
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"• {const.SETTING_LABELS['commission_percent']}: <code>{settings.commission_percent:g}</code>\n"
        f"• {const.SETTING_LABELS['cashback_percent']}: <code>{settings.cashback_percent:g}</code>\n"
        f"• {const.SETTING_LABELS['start_bonus']}: <code>{settings.start_bonus}</code>\n\n"
        "📉 Минимумы по монетам — в отдельном разделе."
    )


# === Вход ===================================================================
@router.message(Command("admin"))
async def open_admin(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not ctx.is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("🛠 <b>Админ-панель</b>\n\nВыберите раздел:", reply_markup=kb_home())


def _guard(cb: CallbackQuery, ctx: AppContext) -> bool:
    return ctx.is_admin(cb.from_user.id)


# === Навигация ==============================================================
@router.callback_query(F.data == "a:home")
async def cb_home(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    await state.clear()
    await cb.message.edit_text("🛠 <b>Админ-панель</b>\n\nВыберите раздел:", reply_markup=kb_home())
    await cb.answer()


@router.callback_query(F.data == "a:close")
async def cb_close(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    await state.clear()
    await cb.message.edit_text("Панель закрыта. /admin — открыть снова.")
    await cb.answer()


# === Ссылки / контакты ======================================================
@router.callback_query(F.data == "a:links")
async def cb_links(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    await state.clear()
    await cb.message.edit_text(
        _links_body(ctx.settings), reply_markup=kb_links(ctx.settings),
        disable_web_page_preview=True,
    )
    await cb.answer()


@router.callback_query(F.data.startswith("a:link:"))
async def cb_link_edit(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    key = cb.data[len("a:link:"):]
    if key not in const.LINK_KEYS:
        return await cb.answer()
    await state.set_state(AdminSG.waiting_link)
    await state.update_data(key=key)
    hint = ""
    if key == "ref_link_base":
        hint = "\n\n<i>Используйте {user_id} как подстановку, напр. https://site/go?ref={user_id}</i>"
    await cb.message.edit_text(
        f"✏️ <b>{const.SETTING_LABELS[key]}</b>\n\n"
        f"Текущее значение:\n<code>{ctx.settings.get(key)}</code>\n\n"
        f"Пришлите новое значение одним сообщением.{hint}",
        reply_markup=kb_cancel("a:links"), disable_web_page_preview=True,
    )
    await cb.answer()


@router.message(AdminSG.waiting_link, F.text)
async def msg_link_save(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not ctx.is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("key")
    if key not in const.LINK_KEYS:
        await state.clear()
        return
    value = message.text.strip()
    if not value:
        await message.answer("Пустое значение — попробуйте ещё раз.")
        return
    if key == "ref_link_base" and "{user_id}" not in value:
        await message.answer("Реф-ссылка должна содержать <code>{user_id}</code>. Попробуйте ещё раз.")
        return
    await ctx.settings.set(key, value)
    await state.clear()
    await message.answer(
        f"✅ {const.SETTING_LABELS[key]} обновлено.",
        reply_markup=kb_links(ctx.settings), disable_web_page_preview=True,
    )


# === Числовые настройки =====================================================
@router.callback_query(F.data == "a:settings")
async def cb_settings(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    await state.clear()
    await cb.message.edit_text(_settings_body(ctx.settings), reply_markup=kb_settings())
    await cb.answer()


@router.callback_query(F.data.startswith("a:num:"))
async def cb_num_edit(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    key = cb.data[len("a:num:"):]
    if key not in const.NUMERIC_KEYS:
        return await cb.answer()
    await state.set_state(AdminSG.waiting_numeric)
    await state.update_data(key=key)
    await cb.message.edit_text(
        f"✏️ <b>{const.SETTING_LABELS[key]}</b>\n\n"
        f"Текущее значение: <code>{ctx.settings.get(key)}</code>\n\n"
        f"Пришлите новое число.",
        reply_markup=kb_cancel("a:settings"),
    )
    await cb.answer()


@router.message(AdminSG.waiting_numeric, F.text)
async def msg_num_save(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not ctx.is_admin(message.from_user.id):
        return
    data = await state.get_data()
    key = data.get("key")
    if key not in const.NUMERIC_KEYS:
        await state.clear()
        return
    raw = message.text.strip().replace(",", ".")
    try:
        value: float | int = float(raw)
    except ValueError:
        await message.answer("Нужно число. Попробуйте ещё раз.")
        return
    if value < 0:
        await message.answer("Число не может быть отрицательным.")
        return
    if key == "cashback_percent" and value >= 100:
        await message.answer("Процент должен быть меньше 100.")
        return
    if key == "start_bonus":
        value = int(value)
    await ctx.settings.set(key, value)
    await state.clear()
    await message.answer(f"✅ {const.SETTING_LABELS[key]} обновлено.", reply_markup=kb_settings())


# === Минимумы по монетам ====================================================
@router.callback_query(F.data == "a:mins")
async def cb_mins(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    await state.clear()
    await cb.message.edit_text(
        "📉 <b>Минимумы обмена (RUB) по монетам</b>\n\nТап по монете — задать новое значение.",
        reply_markup=kb_mins(ctx.settings),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("a:min:"))
async def cb_min_edit(cb: CallbackQuery, state: FSMContext, ctx: AppContext) -> None:
    if not _guard(cb, ctx):
        return await cb.answer()
    coin = cb.data[len("a:min:"):]
    if coin not in const.COIN_KEYS:
        return await cb.answer()
    await state.set_state(AdminSG.waiting_min_rub)
    await state.update_data(coin=coin)
    ticker = const.COINS[coin]["ticker"]
    await cb.message.edit_text(
        f"✏️ Минимум обмена <b>{ticker}</b>\n\n"
        f"Текущее значение: <code>{ctx.settings.min_rub(coin):g}</code> ₽\n\n"
        f"Пришлите новое число (RUB).",
        reply_markup=kb_cancel("a:mins"),
    )
    await cb.answer()


@router.message(AdminSG.waiting_min_rub, F.text)
async def msg_min_save(message: Message, state: FSMContext, ctx: AppContext) -> None:
    if not ctx.is_admin(message.from_user.id):
        return
    data = await state.get_data()
    coin = data.get("coin")
    if coin not in const.COIN_KEYS:
        await state.clear()
        return
    raw = message.text.strip().replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        await message.answer("Нужно число. Попробуйте ещё раз.")
        return
    if value <= 0:
        await message.answer("Минимум должен быть больше нуля.")
        return
    await ctx.settings.set_min_rub(coin, value)
    await state.clear()
    await message.answer(
        f"✅ Минимум {const.COINS[coin]['ticker']} обновлён.", reply_markup=kb_mins(ctx.settings)
    )
