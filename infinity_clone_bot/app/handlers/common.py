from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..constants import COINS
from ..context import AppContext
from ..keyboards import kb_back_module, kb_cancel, kb_captcha_fruits, kb_contacts, kb_main, kb_module
from ..media import send_screen
from ..telegram_helpers import callback_message, callback_user_id, message_user_id
from ..utils import fmt_coin, fmt_money


def build_common_router(ctx: AppContext, assets_dir: Path) -> Router:
    router = Router(name="common")

    def fmt_stat_rub(value: float) -> str:
        if float(value).is_integer():
            return str(int(value))
        return fmt_money(value)

    async def show_main(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_screen(
            message=message,
            assets_dir=assets_dir,
            text="💫 Выбирай кнопку — и в полёт за криптой!",
            asset="main",
            keyboard=kb_main(ctx.settings),
        )

    @router.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext) -> None:
        user_id = message_user_id(message)
        if user_id is None:
            await message.answer("Не удалось определить пользователя.")
            return
        profile = ctx.users.user(user_id)
        if not profile.get("captcha_passed", False):
            await state.clear()
            display_name = message.from_user.first_name if message.from_user and message.from_user.first_name else "друг"
            await message.answer(
                f"Привет {display_name}\n\nВыбери яблоко",
                reply_markup=kb_captcha_fruits(),
            )
            return
        await show_main(message, state)

    @router.callback_query(F.data.startswith("captcha:"))
    async def captcha_check(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        user_id = callback_user_id(callback)
        if msg is None or user_id is None:
            await callback.answer()
            return
        if ctx.users.captcha_passed(user_id):
            await callback.answer()
            await show_main(msg, state)
            return
        if callback.data == "captcha:apple":
            ctx.users.set_captcha_passed(user_id, True)
            await callback.answer("✅ Верно")
            await show_main(msg, state)
            return
        await callback.answer("❌ Неверно. Выбери яблоко", show_alert=True)

    @router.callback_query(F.data == "nav:main")
    async def nav_main(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        await callback.answer()
        if msg is None:
            return
        await show_main(msg, state)

    @router.callback_query(F.data == "menu:contacts")
    async def menu_contacts(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        await callback.answer()
        if msg is None:
            return
        await state.clear()
        text = (
            "📡 Канал – важные объявления и новости\n\n"
            "💬 Чат – общение, рулетки, игры\n\n"
            "📝 Отзывы – ваше мнение о полёте с нами\n\n"
            "🧑‍🚀 Менеджер – вопросы по сотрудничеству\n\n"
            "👽 Оператор – помощь по обменам\n\n"
            "📜 Условия – пользовательское соглашение"
        )
        await send_screen(msg, assets_dir, text, "contacts", kb_contacts(ctx.settings))

    @router.callback_query(F.data == "menu:module")
    async def menu_module(callback: CallbackQuery, state: FSMContext) -> None:
        msg = callback_message(callback)
        user_id = callback_user_id(callback)
        await callback.answer()
        if msg is None or user_id is None:
            return
        await state.clear()
        profile = ctx.users.user(user_id)
        referral = ctx.settings.link("review_form")
        text = (
            "🚀 Личный командный модуль\n\n"
            f"Ваш ID: {user_id}\n"
            f"Обменов всего: {profile['trades_total']} ({fmt_stat_rub(profile['turnover_rub'])} RUB)\n"
            f"Приглашено астронавтов: {profile['invited']}\n"
            "Уровень партнёрки: 1\n"
            f"Баланс бонусов: {fmt_stat_rub(profile['bonus_balance'])} RUB\n\n"
            f"Реф ссылка: {referral}"
        )
        await send_screen(msg, assets_dir, text, "module", kb_module())

    @router.callback_query(F.data == "contacts:review")
    async def contacts_review(callback: CallbackQuery) -> None:
        msg = callback_message(callback)
        await callback.answer()
        if msg is None:
            return
        await msg.answer(
            "Ваше мнение важно для нас! Поделитесь, пожалуйста, впечатлениями о работе сервиса "
            "или идеями по его совершенствованию.",
            reply_markup=kb_cancel(),
        )

    @router.callback_query(F.data == "module:history")
    async def module_history(callback: CallbackQuery) -> None:
        msg = callback_message(callback)
        user_id = callback_user_id(callback)
        await callback.answer()
        if msg is None or user_id is None:
            return
        profile = ctx.users.user(user_id)
        history = profile["history"]
        if not history:
            await send_screen(msg, assets_dir, "❗️ Вы не совершили ни одного обмена", "history", kb_back_module())
            return
        lines = [
            f"• {item['side']} {item['coin']}: {fmt_coin(item['amount_coin'])} / {fmt_money(item['amount_rub'])} RUB"
            for item in history[-10:][::-1]
        ]
        await msg.answer("<b>Последние обмены</b>\n\n" + "\n".join(lines), reply_markup=kb_back_module())

    @router.callback_query(F.data == "module:promo")
    async def module_promo(callback: CallbackQuery) -> None:
        msg = callback_message(callback)
        await callback.answer()
        if msg is None:
            return
        text = (
            "✨ Пилот, промокод в бой!\n\n"
            "• Вводи промокод\n"
            "• Жми «исп.промо» при обмене\n"
            "• Размер скидки = профит сервиса - процент промо\n\n"
            "🎫 Введи промокод и взлетай к экономии! 🎫"
        )
        await send_screen(msg, assets_dir, text, "promo", kb_back_module())

    @router.callback_query(F.data == "module:cashback")
    async def module_cashback(callback: CallbackQuery) -> None:
        msg = callback_message(callback)
        user_id = callback_user_id(callback)
        await callback.answer()
        if msg is None or user_id is None:
            return
        profile = ctx.users.user(user_id)
        text = (
            "🚀 Кешбэк по-галактически\n\n"
            "✨ Как это работает:\n"
            "• После каждого обмена 1 % от прибыли автоматически летит в ваш «доступный баланс»\n"
            "• Эти бонусы можно потратить как скидку при следующем обмене (кнопка \"Исп. баланс кошелька\")\n"
            "• Или вывести себе на BTC-кошелек через «Вывод бонусов»\n\n"
            "📊 Ваши показатели:\n"
            f"• Всего кешбэка получено: {fmt_stat_rub(profile['bonus_balance'])} RUB\n"
            f"• Баланс кешбэка: {fmt_stat_rub(profile['bonus_balance'])}  RUB\n"
            f"• Обменов совершено: {profile['trades_total']}"
        )
        await send_screen(msg, assets_dir, text, "cashback", kb_back_module())

    @router.callback_query(F.data == "module:partner")
    async def module_partner(callback: CallbackQuery) -> None:
        await callback.answer()

    @router.callback_query(F.data == "module:withdraw")
    async def module_withdraw(callback: CallbackQuery) -> None:
        await callback.answer()

    @router.message(Command("rates"))
    async def cmd_rates(message: Message) -> None:
        current_rates = await ctx.rates.get_rates(force=True)
        rows = [f"{meta['symbol']}: {fmt_money(current_rates.get(key, 0.0))}" for key, meta in COINS.items()]
        text = "<b>Текущие курсы (RUB)</b>\n" + "\n".join(rows)
        await message.answer(text)

    @router.message()
    async def fallback(message: Message, state: FSMContext) -> None:
        active = await state.get_state()
        if active:
            await message.answer("Используйте кнопки текущего сценария или /start для сброса.")
            return
        await message.answer("Нажмите /start")

    return router

