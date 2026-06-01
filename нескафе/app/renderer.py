"""Подстановка значений в тексты.

render() кладёт в каждый шаблон админ-настройки (ссылки), поэтому смена
настройки сразу меняет рендер всех экранов. Числовые/суммовые значения
форматируются под стиль оригинала.
"""

from __future__ import annotations

from typing import Any

from .storage import SettingsStore

_EMOJI_DIGITS = {
    "0": "0️⃣", "1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣",
    "5": "5️⃣", "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣",
}
# Кнопки-номера id в списках кошельков (1️⃣ … 🔟)
ID_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def site_display(site_url: str) -> str:
    """`https://nesk.bot/` → `nesk.bot` (для видимого текста ссылки)."""
    s = site_url.split("://", 1)[-1]
    return s.rstrip("/")


def emoji_number(n: int | float) -> str:
    """`50` → `5️⃣0️⃣` (как в онбординге)."""
    return "".join(_EMOJI_DIGITS.get(ch, ch) for ch in str(int(n)))


def fmt_rub_space(value: float) -> str:
    """РУБ-суммы оплаты: пробел как разделитель тысяч (`50 000`)."""
    return f"{int(round(value)):,}".replace(",", " ")


def fmt_rub_comma(value: float) -> str:
    """Минимумы в таблице меню: запятая как разделитель тысяч (`48,670`)."""
    return f"{int(round(value)):,}"


def fmt_coin(amount: float, coin: str | None = None) -> str:
    """`0.00698029`, `3`, `2.66088919` — целое без дробной части, иначе до 8 знаков.

    USDT округляется до целого (решение пользователя: `950 USDT`, без хвоста).
    """
    if coin == "usdt":
        return str(int(round(amount)))
    if amount == int(amount):
        return str(int(amount))
    s = f"{amount:.8f}".rstrip("0").rstrip(".")
    return s or "0"


def base_context(settings: SettingsStore) -> dict[str, Any]:
    """Ссылочные значения, доступные во всех шаблонах."""
    return {
        "operator_url": settings.operator_url,
        "chat_url": settings.chat_url,
        "news_url": settings.news_url,
        "reviews_url": settings.reviews_url,
        "giveaways_url": settings.giveaways_url,
        "site_url": settings.site_url,
        "site_display": site_display(settings.site_url),
    }


def render(template: str, settings: SettingsStore, **extra: Any) -> str:
    ctx = base_context(settings)
    ctx.update(extra)
    return template.format(**ctx)


def render_main_menu(settings: SettingsStore) -> str:
    from . import texts

    return render(
        texts.MAIN_MENU,
        settings,
        min_btc=fmt_rub_comma(settings.min_rub("btc")),
        min_ltc=fmt_rub_comma(settings.min_rub("ltc")),
        min_usdt=fmt_rub_comma(settings.min_rub("usdt")),
        min_xmr=fmt_rub_comma(settings.min_rub("xmr")),
    )
