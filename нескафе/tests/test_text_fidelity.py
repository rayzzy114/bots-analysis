"""Рендер ключевых экранов == дословный HTML из clone_spec_screens.md."""

from app import renderer, texts


def test_calc_body_matches_spec(settings):
    # экран 4252a6fa06
    expected = (
        "<code>🔸 Сумма к получению :  0.00698029 BTC\n"
        "🇷🇺 Сумма к оплате    :  50 000 RUB\n"
        "│\n"
        "├─&gt; кэшбэк 💸: 251\n"
        "╰─&gt; скидка 💎: 0</code>"
    )
    out = renderer.render(
        texts.CALC_BODY, settings, coin_emoji="🔸", coin_amount="0.00698029",
        ticker="BTC", rub="50 000", cashback=251, discount=0,
    )
    assert out == expected


def test_payment_details_matches_spec(settings):
    # новый формат: реквизиты/банк (tap-to-copy в <code>), без «к ОПЕРАТОРУ» и без «(копируется)»
    expected = (
        "<strong>К получению:</strong>\n"
        "<code>│\n"
        "├─</code>🔹&gt;<code>3</code> <code>LTC</code>\n"
        "<code>│\n"
        "╰─</code>⏩️&gt;<code>moQ3AJUMFTar9VomjWWsHWK8RFxJjjoZLh</code>\n"
        "\n"
        "\n"
        "<strong>К оплате:</strong>\n"
        "\n"
        "<code>├─</code> Реквизиты: <code>0000 0000 0000 0000</code>\n"
        "<code>│</code>\n"
        "<code>├─</code> Банк: <code>Сбербанк</code>\n"
        "<code>│</code>\n"
        "<code>├─</code> Сумма:  15 054 RUB 🇷🇺\n"
        "<code>├</code>\n"
        "<code>╰─</code>💸 скидка: 50  |  кэшбэк: 76\n"
        "\n"
        "\n"
        "заявка <code>6a1887d118bd309b79d51449</code>\n"
        "активна до 21:37 28/05 MSK"
    )
    out = renderer.render(
        texts.PAYMENT_DETAILS, settings, coin_emoji="🔹", coin_amount="3", ticker="LTC",
        address="moQ3AJUMFTar9VomjWWsHWK8RFxJjjoZLh",
        requisites="0000 0000 0000 0000", bank="Сбербанк",
        payable="15 054", discount=50, cashback=76,
        order_id="6a1887d118bd309b79d51449", active_until="21:37 28/05 MSK",
    )
    assert out == expected


def test_choose_coin_text(settings):
    assert texts.CHOOSE_COIN == "⚙️ Выберите валюту:"


def test_main_menu_structure(settings):
    out = renderer.render_main_menu(settings)
    assert out.startswith('<a href="https://nesk.bot/"><strong>Neskafe Exchange</strong></a>')
    assert "<strong>Выберите нужный раздел 👇🏼</strong>" in out
