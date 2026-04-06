from __future__ import annotations

import asyncio
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dotenv import dotenv_values

from ..context import AppContext
from ..keyboards import (
    kb_admin_panel,
    links_help_lines,
)
from ..runtime import CLEAR_MARKERS, normalize_input_value, persist_env_value, visible_env_keys
from ..states import AdminState
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, is_safe_html_fragment, parse_amount, preferred_html_text, safe_username

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
        
        text = (
            "<b>Админка</b>\n"
            f"Спред (наценка): <b>{ctx.settings.commission_percent:.2f}%</b>\n"
            f"Админов: <b>{len(ctx.admin_ids)}</b>\n\n"
            "<b>Ссылки:</b>\n"
            f"{links_help_lines(ctx.link_definitions, ctx.settings.all_links())}\n\n"
            "<b>.env переменные:</b>\n"
            f"{chr(10).join(env_lines) if env_lines else '<i>.env пуст</i>'}"
        )
        await message.answer(
            text,
            reply_markup=kb_admin_panel(
                ctx.settings.commission_percent,
                ctx.link_definitions,
                has_sell_wallets=False,
            ),
        )

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
        await msg.answer("Отправьте новый спред (наценку) в %, например: 5.0")

    @router.message(AdminState.waiting_admin_commission)
    async def admin_commission_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        value = parse_amount(message.text or "", allow_zero=True)
        if value is None or value < 0 or value > 50:
            await message.answer("Введите корректное значение спреда в диапазоне 0..50")
            return
        persist_env_value("RATE_SPREAD_PERCENT", str(value), ctx)
        await ctx.rates.get_rates(force=True)
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

    @router.callback_query(F.data == "admin:broadcast")
    async def admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(AdminState.waiting_admin_broadcast)
        await msg.answer("Отправьте сообщение для рассылки всем пользователям.\n"
                         "Поддерживается текст, фото и разметка.")

    @router.message(AdminState.waiting_admin_broadcast)
    async def admin_broadcast_input(message: Message, state: FSMContext, bot: Bot) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещен.")
            return
        
        if ctx.users is None:
            await message.answer("Ошибка: UsersStore не инициализирован.")
            await state.clear()
            return

        users = list(ctx.users.data.keys())
        await message.answer(f"🚀 Начинаю рассылку на {len(users)} пользователей...")
        
        success = 0
        failed = 0
        
        for uid_str in users:
            try:
                target_id = int(uid_str)
                if message.photo:
                    await bot.send_photo(target_id, message.photo[-1].file_id, caption=message.caption)
                else:
                    await bot.send_message(target_id, message.text or "")
                success += 1
            except Exception:
                failed += 1
            
            # Avoid flood limits for larger lists
            if (success + failed) % 20 == 0:
                await asyncio.sleep(0.5)

        await message.answer(f"✅ Рассылка завершена!\n"
                             f"Успешно: {success}\n"
                             f"Ошибок: {failed}")
        await state.clear()
        await show_panel(message)

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
        if key == "support":
            await msg.answer(
                f"Отправьте HTML-блок для «{escape(item.label, quote=False)}».\n"
                "Можно использовать несколько ссылок и переносы строк.\n"
                "Пример: <code>&lt;a href=\"https://t.me/..\"&gt;Ознакомиться&lt;/a&gt;</code>\n"
                "Отправьте <code>-</code>, чтобы очистить значение."
            )
        else:
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
        raw_value = preferred_html_text(message.text, message.html_text)
        value = normalize_input_value(raw_value)
        if key == "support":
            if raw_value.lower() in CLEAR_MARKERS:
                value = ""
            elif not value:
                await message.answer("Нужен HTML-блок или <code>-</code> для очистки.")
                return
            elif not is_safe_html_fragment(value):
                await message.answer(
                    "HTML-блок должен содержать только текст, переносы строк, "
                    "<code>&lt;a href=\"...\"&gt;...&lt;/a&gt;</code> и <code>&lt;br&gt;</code>."
                )
                return
        else:
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
        spread = ctx.settings.commission_percent / 100.0
        def base_value(value: object) -> str:
            try:
                base = float(str(value).replace(",", ".").replace(" ", ""))
            except (TypeError, ValueError):
                return "—"
            if not spread:
                return f"{base:.2f}"
            return f"{base / (1.0 + spread):.2f}"
        rub_idr = rates.get("rub_idr", 0)
        rub_idr_inv = int(round(1.0 / rub_idr)) if rub_idr and rub_idr < 1 else int(round(rub_idr))
        lines = [
            f"Спред: {ctx.settings.commission_percent:.2f}%",
            "",
            "🇹🇭 Таиланд",
            f"  USDT/THB: {base_value(rates.get('usdt_thb'))} -> {rates.get('usdt_thb', '—')}",
            f"  RUB/THB: {base_value(rates.get('rub_thb'))} -> {rates.get('rub_thb', '—')}",
            "🇨🇳 Китай",
            f"  USDT/CNY: {base_value(rates.get('usdt_cny'))} -> {rates.get('usdt_cny', '—')}",
            f"  RUB/CNY: {base_value(rates.get('rub_cny'))} -> {rates.get('rub_cny', '—')}",
            "🇦🇪 Дубай",
            f"  USDT/AED: {base_value(rates.get('usdt_aed'))} -> {rates.get('usdt_aed', '—')}",
            f"  RUB/AED: {base_value(rates.get('rub_aed'))} -> {rates.get('rub_aed', '—')}",
            "🇮🇩 Бали",
            f"  USDT/IDR: {base_value(rates.get('usdt_idr'))} -> {rates.get('usdt_idr', '—')}",
            f"  1 RUB = {rub_idr_inv} IDR",
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
