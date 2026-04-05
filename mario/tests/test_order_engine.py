from __future__ import annotations

from pathlib import Path

import pytest

from app.models import QuoteRecord
from app.order_engine import OrderEngine

pytestmark = pytest.mark.unit


def test_order_engine_create_update_and_render(tmp_path: Path) -> None:
    engine = OrderEngine(store_path=tmp_path / "orders.json", ttl_seconds=900)
    quote = QuoteRecord(
        state_id="q1",
        operation="sell",
        coin="BTC",
        coin_amount=0.015,
        rub_amount=84905,
        net_amount=None,
    )
    order = engine.create_order(
        user_id=1,
        operation="sell",
        coin="BTC",
        input_amount=0.015,
        quote=quote,
        payment_method="📱СБП",
        wallet_or_requisites="79000000000",
    )
    assert order.order_id
    assert order.status == "created"

    template = (
        "✅Заявка №1771774402917\n"
        "Продаете: 0.015 btc\n"
        "📲СБП реквизиты: 79045678990\n"
        "Получаете: 84905 ₽\n"
        "Реквизиты для перевода btc: bc1abc"
    )
    rendered = engine.render_order_text(template, order)
    assert order.order_id in rendered
    assert "79000000000" in rendered

    updated = engine.update_status(order.order_id, "paid")
    assert updated is not None
    assert updated.status == "paid"
    assert engine.render_status_text(updated) == "Реквизиты найдены."


def test_render_order_text_preserves_html_and_decodes_emoji(tmp_path: Path) -> None:
    engine = OrderEngine(store_path=tmp_path / "orders.json", ttl_seconds=900)
    quote = QuoteRecord(
        state_id="q_usdt",
        operation="sell",
        coin="USDT",
        coin_amount=100.0,
        rub_amount=8751.0,
        net_amount=None,
    )
    order = engine.create_order(
        user_id=7,
        operation="sell",
        coin="USDT",
        input_amount=100.0,
        quote=quote,
        payment_method="📱СБП",
        wallet_or_requisites="79001234567",
    )

    template_html = (
        "✅<strong>Заявка №</strong><code>1771774494291</code>\n\n"
        "<strong>Продаете</strong>: 2500 usdt\n"
        "<strong>📲СБП реквизиты</strong>: <code>79045678990</code>\n\n"
        "\\uD83D\\uDCB5<strong>Получаете</strong>: <code>216218 ₽</code>\n"
        "<strong>Реквизиты для перевода usdt:</strong>\n\n"
        "<code>TVL7QeX1aLQX5d5fyFXpighpncmfzskXdp</code>\n\n"
        "⏳<strong>Заявка действительна</strong>: 15 минут"
    )

    rendered = engine.render_order_text(
        template_html,
        order,
        merchant_requisites="TVL7QeXiaLQX5d5fyFXpighpncmf2skXdp",
        template_sold_amount_raw="2500 usdt",
        template_payout_rub=216218.0,
        template_requisites_value="TVL7QeX1aLQX5d5fyFXpighpncmfzskXdp",
    )

    assert "💵" in rendered
    assert "<strong>Продаете</strong>: 100 usdt" in rendered
    assert "<code>8751 ₽</code>" in rendered
    assert "<code>79001234567</code>" in rendered
    assert "TVL7QeXiaLQX5d5fyFXpighpncmf2skXdp" in rendered


def test_render_order_text_buy_does_not_invert_amounts(tmp_path: Path) -> None:
    engine = OrderEngine(store_path=tmp_path / "orders.json", ttl_seconds=900)
    quote = QuoteRecord(
        state_id="q_buy_btc",
        operation="buy",
        coin="BTC",
        coin_amount=1.0,
        rub_amount=2_550_000.0,
        net_amount=None,
    )
    order = engine.create_order(
        user_id=11,
        operation="buy",
        coin="BTC",
        input_amount=2_550_000.0,
        quote=quote,
        payment_method="📱СБП",
        wallet_or_requisites="79000000000",
    )
    template = (
        "✅Заявка №1771774402917\n\n"
        "Продаете: 0.015 btc\n"
        "📲СБП реквизиты: 79045678990\n\n"
        "Получаете: 84905 ₽\n"
        "Реквизиты для перевода btc:\n\n"
        "bc1q3crqafv94waln9uzj7t03vp2a3qqsehztsg893\n"
    )
    rendered = engine.render_order_text(
        template,
        order,
        template_sold_amount_raw="0.015 btc",
        template_payout_rub=84905.0,
        template_requisites_value="bc1q3crqafv94waln9uzj7t03vp2a3qqsehztsg893",
    )

    assert "Продаете: 1 btc" in rendered
    assert "Получаете: 2550000 ₽" in rendered


def test_render_buy_order_text_is_dynamic(tmp_path: Path) -> None:
    engine = OrderEngine(store_path=tmp_path / "orders.json", ttl_seconds=900)
    quote = QuoteRecord(
        state_id="q_buy_usdt",
        operation="buy",
        coin="USDT",
        coin_amount=100.0,
        rub_amount=8751.0,
        net_amount=None,
    )
    order = engine.create_order(
        user_id=12,
        operation="buy",
        coin="USDT",
        input_amount=8751.0,
        quote=quote,
        payment_method="📱СБП",
        wallet_or_requisites="TVL7QeXiaLQX5d5fyFXpighpncmf2skXdp",
    )
    plain, html = engine.render_buy_order_text(order, merchant_requisites="2200 0000 0000 0000")

    assert "Покупаете: 100 usdt" in plain
    assert "К оплате: 8751 ₽" in plain
    assert "2200 0000 0000 0000" in plain
    assert "<strong>Покупаете</strong>: 100 usdt" in html


def test_create_buy_order_uses_effective_input_amount_and_rounds_rub_text(tmp_path: Path) -> None:
    engine = OrderEngine(store_path=tmp_path / "orders.json", ttl_seconds=900)
    quote = QuoteRecord(
        state_id="q_buy_btc",
        operation="buy",
        coin="BTC",
        coin_amount=0.0005,
        rub_amount=3268.7701933333333,
        net_amount=2451.577645,
    )
    order = engine.create_order(
        user_id=99,
        operation="buy",
        coin="BTC",
        input_amount=3105.3316836666663,
        quote=quote,
        payment_method="📱СБП",
        wallet_or_requisites="walletX",
    )

    assert order.pay_amount == pytest.approx(3105.3316836666663)
    plain, html = engine.render_buy_order_text(order, merchant_requisites="2200 0000 0000 0000")
    assert "К оплате: 3105 ₽" in plain
    assert "<code>3105 ₽</code>" in html
    assert ".331683" not in plain
