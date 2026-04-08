import asyncio
import os
import re
import sys

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dotenv import dotenv_values, load_dotenv, set_key

from ..constants import COINS, DEFAULT_LINKS, LINK_LABELS
from ..context import AppContext
from ..keyboards import kb_admin_delete_payment_method, kb_admin_panel, kb_admin_requisites
from ..states import TradeState
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_money, parse_admin_ids, parse_amount


def build_admin_router(ctx: AppContext) -> Router:
    router = Router(name="admin")

    def mask_value(key: str, value: str) -> str:
        if key == "BOT_TOKEN":
            if len(value) < 8:
                return "***"
            return value[:6] + "..." + value[-4:]
        return value

    def apply_runtime_from_env() -> None:
        env = dotenv_values(ctx.env_path)

        raw_admin_ids = (env.get("ADMIN_IDS") or "").strip()
        ctx.admin_ids = parse_admin_ids(raw_admin_ids)

        commission_raw = (env.get("DEFAULT_COMMISSION_PERCENT") or "").strip()
        parsed = parse_amount(commission_raw)
        if parsed is not None and 0 <= parsed <= 50:
            ctx.settings.set_commission(parsed)

        for link_key in DEFAULT_LINKS:
            env_key = f"{link_key.upper()}_LINK"
            value = (env.get(env_key) or "").strip()
            if value:
                ctx.settings.set_link(link_key, value)

    def admin_text() -> str:
        env = dotenv_values(ctx.env_path)
        rows = []
        for key in sorted(env):
            value = str(env.get(key) or "")
            rows.append(f"<code>{key}</code> = <code>{mask_value(key, value)}</code>")
        links = ctx.settings.all_links()
        links_rows = [f"{label}: {links.get(key, '-')}" for key, label in LINK_LABELS.items()]
        return (
            "<b>Админка</b>\n"
            f"Комиссия: <b>{ctx.settings.commission_percent:.2f}%</b>\n"
            f"Админов: <b>{len(ctx.admin_ids)}</b>\n\n"
            "<b>Ссылки:</b>\n"
            + "\n".join(links_rows)
            + "\n\n<b>.env переменные:</b>\n"
            + ("\n".join(rows) if rows else "<i>Файл .env пуст</i>")
            + "\n\nМожно менять любую переменную через кнопку <b>ENV KEY=VALUE</b>."
        )

    def requisites_mode_label() -> str:
        if ctx.settings.requisites_mode == "single":
            return "Единые"
        return ctx.settings.requisites_mode

    async def requisites_text() -> str:
        current_rates = await ctx.rates.get_rates()
        methods = ctx.settings.payment_methods()
        methods_rows = "\n".join(f"• {item}" for item in methods) if methods else "<i>Не заданы</i>"
        return (
            "💳 <b>Управление реквизитами</b>\n\n"
            f"├ Режим: ⚪ <b>{requisites_mode_label()} реквизиты</b>\n"
            f"├ Реквизиты: <code>{ctx.settings.requisites_value}</code>\n"
            f"├ Банк: <b>{ctx.settings.requisites_bank}</b>\n"
            f"├ Курс BTC: <b>{fmt_money(current_rates.get('btc', 0.0))} RUB</b>\n"
            f"└ Комиссия: <b>{ctx.settings.commission_percent:.2f}%</b>\n\n"
            "<b>Способы оплаты:</b>\n"
            f"{methods_rows}"
        )

    async def show_admin_panel(message: Message) -> None:
        await message.answer(admin_text(), reply_markup=kb_admin_panel(ctx.settings.commission_percent))

    async def show_requisites_panel(message: Message) -> None:
        await message.answer(
            await requisites_text(),
            reply_markup=kb_admin_requisites(
                commission_percent=ctx.settings.commission_percent,
                mode_label=requisites_mode_label(),
            ),
        )

    async def persist_env_value(key: str, value: str) -> None:
        set_key(
            dotenv_path=str(ctx.env_path),
            key_to_set=key,
            value_to_set=value,
            quote_mode="never",
        )
        load_dotenv(dotenv_path=ctx.env_path, override=True)
        apply_runtime_from_env()

    @router.message(Command("admin"))
    async def cmd_admin(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        await state.clear()
        await show_admin_panel(message)

    @router.callback_query(F.data == "admin:set_commission")
    async def admin_set_commission(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.update_data(admin_return_to="panel")
        await state.set_state(TradeState.waiting_admin_commission)
        await msg.answer("Отправьте новую комиссию в %, например: 2.5")

    @router.callback_query(F.data == "admin:req:commission")
    async def admin_req_set_commission(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.update_data(admin_return_to="requisites")
        await state.set_state(TradeState.waiting_admin_commission)
        await msg.answer("Отправьте новую комиссию в %, например: 2.5")

    @router.message(TradeState.waiting_admin_commission)
    async def admin_commission_value(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        value = parse_amount(message.text or "")
        if value is None or value < 0 or value > 50:
            await message.answer("Введите корректный % комиссии в диапазоне 0..50")
            return
        data = await state.get_data()
        await persist_env_value("DEFAULT_COMMISSION_PERCENT", str(value))
        await state.clear()
        if data.get("admin_return_to") == "requisites":
            await show_requisites_panel(message)
            return
        await show_admin_panel(message)

    @router.callback_query(F.data.startswith("admin:set_link:"))
    async def admin_set_link(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        key = (callback.data or "").split(":")[-1]
        if key not in LINK_LABELS:
            await callback.answer("Неизвестный ключ", show_alert=True)
            return
        await callback.answer()
        await state.set_state(TradeState.waiting_admin_link)
        await state.update_data(admin_link_key=key)
        await msg.answer(
            f"Отправьте новую ссылку для «{LINK_LABELS[key]}».\n"
            "Поддерживается https://... или t.me/..."
        )

    @router.message(TradeState.waiting_admin_link)
    async def admin_link_value(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        data = await state.get_data()
        key = data.get("admin_link_key")
        if key not in LINK_LABELS:
            await state.clear()
            await message.answer("Сессия админки сброшена.")
            return
        value = (message.text or "").strip()
        if value.startswith("t.me/"):
            value = "https://" + value
        if not re.match(r"^https?://", value):
            await message.answer("Нужна ссылка формата https://... или t.me/...")
            return
        await persist_env_value(f"{key.upper()}_LINK", value)
        await state.clear()
        await message.answer(f"Ссылка «{LINK_LABELS[key]}» обновлена.")
        await show_admin_panel(message)

    @router.callback_query(F.data == "admin:set_env")
    async def admin_set_env(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(TradeState.waiting_admin_env)
        await msg.answer(
            "Отправьте переменную в формате:\n"
            "<code>KEY=VALUE</code>\n\n"
            "Примеры:\n"
            "<code>ADMIN_IDS=123,456</code>\n"
            "<code>DEFAULT_COMMISSION_PERCENT=3.1</code>\n"
            "<code>FAQ_LINK=https://example.com</code>"
        )

    @router.message(TradeState.waiting_admin_env)
    async def admin_env_value(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        raw = (message.text or "").strip()
        if "=" not in raw:
            await message.answer("Неверный формат. Нужен <code>KEY=VALUE</code>")
            return
        key, value = raw.split("=", 1)
        key = key.strip().upper()
        value = value.strip()
        if not re.match(r"^[A-Z0-9_]+$", key):
            await message.answer("Неверный ключ. Разрешены A-Z, 0-9 и _.")
            return
        if key.endswith("_LINK") and value.startswith("t.me/"):
            value = "https://" + value
        old_token = os.getenv("BOT_TOKEN", "")
        await persist_env_value(key, value)
        await state.clear()

        new_token = os.getenv("BOT_TOKEN", "")
        await message.answer(
            f"Обновлено: <code>{key}</code> = <code>{mask_value(key, value)}</code>",
            reply_markup=kb_admin_panel(ctx.settings.commission_percent),
        )

        if key == "BOT_TOKEN" and new_token and new_token != old_token:
            await message.answer("BOT_TOKEN обновлён. Перезапускаю бота для применения...")
            await asyncio.sleep(1)
            os.execv(
                sys.executable,
                [sys.executable, str((ctx.env_path.parent / "main.py").resolve())],
            )

    @router.callback_query(F.data == "admin:requisites")
    async def admin_requisites(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await show_requisites_panel(msg)

    @router.callback_query(F.data == "admin:req:back")
    async def admin_requisites_back(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.clear()
        await show_admin_panel(msg)

    @router.callback_query(F.data == "admin:req:toggle_mode")
    async def admin_requisites_toggle_mode(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        if user_id is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer("Доступен режим «Единые реквизиты».", show_alert=True)

    @router.callback_query(F.data == "admin:req:edit_value")
    async def admin_requisites_edit_value(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(TradeState.waiting_admin_requisites_value)
        await msg.answer(
            "Отправьте новые реквизиты.\n"
            f"Текущее значение: <code>{ctx.settings.requisites_value}</code>"
        )

    @router.message(TradeState.waiting_admin_requisites_value)
    async def admin_requisites_value_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        value = (message.text or "").strip()
        if len(value) < 6 or len(value) > 128:
            await message.answer("Реквизиты должны быть длиной от 6 до 128 символов.")
            return
        ctx.settings.set_requisites_value(value)
        await state.clear()
        await message.answer("Реквизиты обновлены.")
        await show_requisites_panel(message)

    @router.callback_query(F.data == "admin:req:edit_bank")
    async def admin_requisites_edit_bank(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(TradeState.waiting_admin_requisites_bank)
        await msg.answer(
            "Отправьте новое название банка.\n"
            f"Текущее значение: <b>{ctx.settings.requisites_bank}</b>"
        )

    @router.message(TradeState.waiting_admin_requisites_bank)
    async def admin_requisites_bank_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        value = (message.text or "").strip()
        if len(value) < 2 or len(value) > 64:
            await message.answer("Название банка должно быть длиной от 2 до 64 символов.")
            return
        ctx.settings.set_requisites_bank(value)
        await state.clear()
        await message.answer("Банк обновлён.")
        await show_requisites_panel(message)

    @router.callback_query(F.data == "admin:req:add_method")
    async def admin_requisites_add_method(callback: CallbackQuery, state: FSMContext) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        await callback.answer()
        await state.set_state(TradeState.waiting_admin_payment_method_add)
        await msg.answer("Введите название нового способа оплаты.")

    @router.message(TradeState.waiting_admin_payment_method_add)
    async def admin_requisites_add_method_input(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None or not ctx.is_admin(user_id):
            await message.answer("Доступ запрещён.")
            return
        value = (message.text or "").strip()
        if len(value) < 2 or len(value) > 64:
            await message.answer("Название способа оплаты должно быть длиной от 2 до 64 символов.")
            return
        ctx.settings.add_payment_method(value)
        await state.clear()
        await message.answer(f"Способ оплаты добавлен: <b>{value}</b>")
        await show_requisites_panel(message)

    @router.callback_query(F.data == "admin:req:delete_method_menu")
    async def admin_requisites_delete_method_menu(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        methods = ctx.settings.payment_methods()
        if len(methods) <= 1:
            await callback.answer("Нельзя удалить единственный способ оплаты.", show_alert=True)
            return
        await callback.answer()
        await msg.answer(
            "Выберите способ оплаты для удаления:",
            reply_markup=kb_admin_delete_payment_method(methods),
        )

    @router.callback_query(F.data.startswith("admin:req:del:"))
    async def admin_requisites_delete_method(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        raw_index = (callback.data or "").split(":")[-1]
        if not raw_index.isdigit():
            await callback.answer("Некорректный индекс", show_alert=True)
            return
        index = int(raw_index)
        methods = ctx.settings.payment_methods()
        if index < 0 or index >= len(methods):
            await callback.answer("Способ не найден", show_alert=True)
            return
        method_name = methods[index]
        if not ctx.settings.delete_payment_method(index):
            await callback.answer("Нельзя удалить единственный способ оплаты.", show_alert=True)
            return
        await callback.answer("Удалено")
        await msg.answer(f"Способ оплаты удалён: <b>{method_name}</b>")
        await show_requisites_panel(msg)

    @router.callback_query(F.data == "admin:rates")
    async def admin_rates(callback: CallbackQuery) -> None:
        user_id = callback_user_id(callback)
        msg = callback_message(callback)
        if user_id is None or msg is None or not ctx.is_admin(user_id):
            await callback.answer("Нет доступа", show_alert=True)
            return
        current_rates = await ctx.rates.get_rates(force=True)
        await callback.answer("Курсы обновлены")
        lines = []
        for key, meta in COINS.items():
            symbol = meta["symbol"]
            lines.append(f"{symbol}: {fmt_money(current_rates.get(key, 0.0))} RUB")
        await msg.answer("🔄 Курсы обновлены:\n" + "\n".join(lines))

    return router
