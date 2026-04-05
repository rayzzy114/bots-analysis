from __future__ import annotations

import re
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dotenv import dotenv_values

from ..constants import COINS
from ..context import AppContext
from ..keyboards import (
    kb_admin_panel,
    kb_admin_sell_wallets,
    links_help_lines,
)
from ..runtime import normalize_input_value, persist_env_value, visible_env_keys
from ..states import AdminState
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, parse_amount, safe_username

ADMIN_STATE_PREFIX = f"{AdminState.__name__}:"


def build_admin_router(ctx: AppContext) -> Router:
    router = Router(name="admin")
    env_keys_to_show = visible_env_keys(ctx.link_definitions, ctx.sell_wallet_labels)

    async def clear_admin_state_if_needed(state: FSMContext) -> None:
        current = await state.get_state()
        if current and current.startswith(ADMIN_STATE_PREFIX):
            await state.clear()

    async def show_panel(message: Message) -> None:
        env = dotenv_values(ctx.env_path)
        visible_items = [
            (key, "" if value is None else str(value))
            for key, value in sorted(env.items())
            if key.upper() in env_keys_to_show
        ]
        hidden_count = sum(1 for key in env if key.upper() not in env_keys_to_show)
        env_lines = [
            f"<code>{escape(key, quote=False)}</code> = <code>{escape(value, quote=False) or '-'}</code>"
            for key, value in visible_items
        ]
        if hidden_count:
            env_lines.append(f"<i>Скрыто ключей: {hidden_count}</i>")
        wallets = ctx.settings.all_sell_wallets()
        wallet_lines = "\n".join(
            f"{escape(label, quote=False)}: <code>{escape(wallets.get(key, '').strip(), quote=False) or '-'}</code>"
            for key, label in ctx.sell_wallet_labels.items()
        )
        text = (
            "<b>Админка</b>\n"
            f"Комиссия: <b>{ctx.settings.commission_percent:.2f}%</b>\n"
            f"Админов: <b>{len(ctx.admin_ids)}</b>\n\n"
            "<b>Ссылки:</b>\n"
            f"{links_help_lines(ctx.link_definitions, ctx.settings.all_links())}\n\n"
            + ('<b>Кошельки продажи:</b>\n' + wallet_lines + '\n\n' if ctx.sell_wallet_labels else '')
            + "<b>.env переменные:</b>\n"
            + ('\n'.join(env_lines) if env_lines else '<i>.env пуст</i>')
        )
        await message.answer(
            text,
            reply_markup=kb_admin_panel(
                ctx.settings.commission_percent,
                ctx.link_definitions,
                has_sell_wallets=bool(ctx.sell_wallet_labels),
            ),
        )

    async def show_sell_wallets_panel(message: Message) -> None:
        wallets = ctx.settings.all_sell_wallets()
        lines = [
            f"• {escape(label, quote=False)}: <code>{escape(wallets.get(key, '').strip(), quote=False) or '-'}</code>"
            for key, label in ctx.sell_wallet_labels.items()
        ]
        text = "🪙 <b>Кошельки продажи крипты</b>\n\n" + "\n".join(lines)
        await message.answer(text, reply_markup=kb_admin_sell_wallets(wallets, ctx.sell_wallet_labels))

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        await clear_admin_state_if_needed(state)
        await show_panel(message)

    @router.callback_query(F.data == "admin:set_commission")
    async def admin_set_commission(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_admin_commission)
        await msg.answer("Отправьте новую комиссию в %, например: 2.5")

    @router.message(AdminState.waiting_admin_commission)
    async def admin_commission_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        value = parse_amount(message.text or "", allow_zero=True)
        if value is None or value < 0 or value > 50:
            await message.answer("Введите корректную комиссию в диапазоне 0..50")
            return
        persist_env_value("DEFAULT_COMMISSION_PERCENT", str(value), ctx)
        await state.clear()
        await show_panel(message)

    @router.callback_query(F.data == "admin:set_env")
    async def admin_set_env(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_admin_env)
        await msg.answer("Отправьте переменную в формате:\n<code>KEY=VALUE</code>")

    @router.message(AdminState.waiting_admin_env)
    async def admin_env_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        raw = (message.text or "").strip()
        if "=" not in raw:
            await message.answer("Неверный формат. Нужен <code>KEY=VALUE</code>")
            return
        key, value = raw.split("=", 1)
        key = key.strip().upper()
        if not re.match(r"^[A-Z0-9_]+$", key):
            await message.answer("Неверный ключ. Разрешены A-Z, 0-9 и _.")
            return
        persist_env_value(key, value.strip(), ctx)
        await state.clear()
        shown = "-" if key not in env_keys_to_show else escape(value.strip(), quote=False) or "-"
        await message.answer(f"Обновлено: <code>{key}</code> = <code>{shown}</code>")
        await show_panel(message)

    @router.callback_query(F.data == "admin:sell_wallets")
    async def admin_sell_wallets(callback: CallbackQuery, state: FSMContext) -> None:
        if not ctx.sell_wallet_labels:
            await callback.answer("Кошельки продажи не настроены.", show_alert=True)
            return
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await clear_admin_state_if_needed(state)
        await show_sell_wallets_panel(msg)

    @router.callback_query(F.data == "admin:sell_wallets:back")
    async def admin_sell_wallets_back(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await clear_admin_state_if_needed(state)
        await show_panel(msg)

    @router.callback_query(F.data.startswith("admin:sell_wallet:set:"))
    async def admin_sell_wallet_set(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        key = (callback.data or "").split(":")[-1].strip().lower()
        if key not in ctx.sell_wallet_labels:
            await callback.answer("Неизвестный ключ", show_alert=True)
            return
        current = ctx.settings.sell_wallet(key)
        await callback.answer()
        await state.set_state(AdminState.waiting_admin_sell_wallet)
        await state.update_data(sell_wallet_key=key)
        await msg.answer(
            f"Отправьте новый кошелек для <b>{escape(ctx.sell_wallet_labels[key], quote=False)}</b>.\n"
            f"Текущее значение: <code>{escape(current, quote=False) or '-'}</code>\n"
            "Отправьте <code>-</code>, чтобы очистить значение."
        )

    @router.message(AdminState.waiting_admin_sell_wallet)
    async def admin_sell_wallet_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        data = await state.get_data()
        key = str(data.get("sell_wallet_key") or "").strip().lower()
        if key not in ctx.sell_wallet_labels:
            await state.clear()
            await message.answer("Сессия обновления кошелька сброшена.")
            return
        value = normalize_input_value(message.text or "")
        if value and len(value) < 10:
            await message.answer("Кошелек должен быть длиной от 10 до 256 символов или <code>-</code> для очистки.")
            return
        if not ctx.settings.set_sell_wallet(key, value):
            await message.answer("Не удалось сохранить кошелек.")
            return
        persist_env_value(f"SELL_WALLET_{key.upper()}", value, ctx)
        await state.clear()
        await message.answer(
            f"Кошелек для {escape(ctx.sell_wallet_labels[key], quote=False)} "
            f"{'очищен' if not value else 'обновлен'}."
        )
        await show_sell_wallets_panel(message)

    @router.callback_query(F.data.startswith("admin:set_link:"))
    async def admin_set_link(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        key = (callback.data or "").split(":")[-1]
        item = next((entry for entry in ctx.link_definitions if entry.key == key), None)
        if item is None:
            await callback.answer("Неизвестный ключ", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_admin_link)
        await state.update_data(link_key=key)
        await msg.answer(
            f"Отправьте новую ссылку для «{escape(item.label, quote=False)}».\n"
            "Поддерживается https://... или t.me/...\n"
            "Отправьте <code>-</code>, чтобы очистить значение."
        )

    @router.message(AdminState.waiting_admin_link)
    async def admin_link_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        data = await state.get_data()
        key = str(data.get("link_key") or "")
        item = next((entry for entry in ctx.link_definitions if entry.key == key), None)
        if item is None:
            await state.clear()
            await message.answer("Сессия обновления ссылки сброшена.")
            return
        value = normalize_input_value(message.text or "")
        if value.startswith("t.me/"):
            value = "https://" + value
        if value and not re.match(r"^https?://", value):
            await message.answer("Нужна ссылка формата https://..., t.me/... или <code>-</code> для очистки.")
            return
        persist_env_value(item.resolved_env_key, value, ctx)
        await state.clear()
        await message.answer(
            f"Ссылка «{escape(item.label, quote=False)}» "
            f"{'очищена' if not value else 'обновлена'}."
        )
        await show_panel(message)

    @router.callback_query(F.data == "admin:rates")
    async def admin_rates(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        rates = await ctx.rates.get_rates(force=True)
        lines = [
            f"{COINS['btc']['symbol']}: ${rates.get('btc', 0):,.0f}",
            f"{COINS['eth']['symbol']}: ${rates.get('eth', 0):,.0f}",
            f"{COINS['ltc']['symbol']}: ${rates.get('ltc', 0):,.2f}",
            f"{COINS['xmr']['symbol']}: ${rates.get('xmr', 0):,.2f}",
            f"{COINS['usdt']['symbol']}: ${rates.get('usdt', 1):.4f}",
        ]
        await callback.answer("Курсы обновлены")
        await msg.answer("🔄 Курсы обновлены:\n" + "\n".join(lines))

    if ctx.orders is not None:
        @router.callback_query(F.data.startswith("admin:order:confirm:"))
        async def admin_confirm_order(callback: CallbackQuery) -> None:
            user_id = callback_user_id(callback)
            msg = callback_message(callback)
            if user_id is None or msg is None or not ctx.is_admin(user_id):
                await callback.answer("Нет доступа", show_alert=True)
                return
            order_id = (callback.data or "").split(":")[-1]
            success, order = ctx.orders.confirm_order(order_id, user_id)
            if not success or order is None:
                await callback.answer("Нельзя подтвердить эту заявку.", show_alert=True)
                return
            await callback.answer("Выдача подтверждена")

            username = safe_username(order["username"])
            text = (
                "✅ Выдача подтверждена\n\n"
                f"📦 ID заказа: {order['order_id']}\n"
                f"👤 ID: {order['user_id']}\n"
                f"📝 Username: {username}\n"
                "👛 Кошелек:\n"
                f"{escape(order['wallet'], quote=False)}\n\n"
                f"💎 Крипта: {fmt_coin(order['coin_amount'])} {order['coin_symbol']}\n"
                f"💰 Сумма: {int(order['amount_rub'])} RUB\n"
                f"💳 Способ оплаты: {escape(order['payment_method'], quote=False)}"
            )
            await msg.edit_text(text)
            try:
                bot = callback.bot
                if bot is None:
                    return
                await bot.send_message(
                    chat_id=order["user_id"],
                    text=(
                        f"✅ Ваша заявка #{order['order_id']} подтверждена.\n"
                        "Средства отправлены. Спасибо за обмен."
                    ),
                )
            except Exception as e:
                print(f'Exception caught: {e}')

    return router
