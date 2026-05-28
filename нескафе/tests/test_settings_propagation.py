"""Каждое админ-поле: смена настройки меняет рендер текста (правило skill)."""

from app import renderer, texts


async def test_operator_url_propagates(settings):
    await settings.set("operator_url", "https://t.me/NewOperator")
    # появляется в экранах с оператором
    for tmpl, extra in [
        (texts.ALREADY_IN_SYSTEM, {}),
        (texts.PARALLEL_UNAVAILABLE, {}),
        (
            texts.PAYMENT_DETAILS,
            dict(coin_emoji="🔹", coin_amount="3", ticker="LTC", address="addr",
                 rub="15 054", discount=0, cashback=76, order_id="x", active_until="y"),
        ),
    ]:
        out = renderer.render(tmpl, settings, **extra)
        assert "NewOperator" in out
        assert "ExchangeNeskafeExmoLTC" not in out


async def test_reviews_and_giveaways_propagate_to_keyboard(settings):
    from app import keyboards

    await settings.set("reviews_url", "https://t.me/NewReviews")
    await settings.set("giveaways_url", "https://t.me/NewGiveaways")
    kb = keyboards.kb_help_links(settings)
    urls = [btn.url for row in kb.inline_keyboard for btn in row]
    assert "https://t.me/NewReviews" in urls
    assert "https://t.me/NewGiveaways" in urls
    assert "https://t.me/Neskafe_Exchange" not in urls


async def test_site_url_propagates_with_display(settings):
    await settings.set("site_url", "https://neskafe.new/")
    out = renderer.render(texts.HELP_SAVE_SITE, settings)
    assert 'href="https://neskafe.new/"' in out
    assert "neskafe.new" in out          # видимый текст ссылки тоже обновился
    assert "nesk.bot" not in out
    # главное меню тоже тянет site_url
    menu = renderer.render_main_menu(settings)
    assert 'href="https://neskafe.new/"' in menu


async def test_ref_link_propagates(settings):
    await settings.set("ref_link_base", "https://new.site/r?id={user_id}")
    out = renderer.render(texts.ACCOUNT_BODY, settings, bonus_available="50.0",
                          bonus_used="0.0", ref_link=settings.ref_link(777), invited=0)
    assert "https://new.site/r?id=777" in out
    assert "nesk.bot/go" not in out


async def test_min_rub_propagates_to_menu(settings):
    await settings.set_min_rub("btc", 1234)
    menu = renderer.render_main_menu(settings)
    assert "обмен от 1,234" in menu
    assert "обмен от 795" not in menu


async def test_chat_and_news_propagate_to_help_panel(settings):
    from app import keyboards

    await settings.set("chat_url", "https://t.me/NewChat")
    await settings.set("news_url", "https://t.me/NewNews")
    kb = keyboards.kb_help_panel(settings)
    urls = [btn.url for row in kb.inline_keyboard for btn in row]
    assert "https://t.me/NewChat" in urls
    assert "https://t.me/NewNews" in urls


async def test_commission_propagates_to_calc(settings):
    from app import calc

    data = {"coin": "ltc", "rate": 100.0, "rub": 50000, "burn": False, "mode": "default"}
    await settings.set("commission_percent", 0)
    t0, _ = calc.render_calc(data, settings)
    await settings.set("commission_percent", 50)
    t1, _ = calc.render_calc(data, settings)
    # при комиссии 50% сумма к получению вдвое меньше
    assert "500 LTC" in t0
    assert "250 LTC" in t1
