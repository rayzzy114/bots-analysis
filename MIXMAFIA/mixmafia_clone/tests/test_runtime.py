"""Tests: runtime helpers for callback routing and captcha."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from admin_kit.storage import OrdersStore
from app.catalog import FlowCatalog
from app.runtime import (
    FlowRuntime,
    UserSession,
    _build_cancel_confirmation_state,
    _build_captcha_codes,
    _build_order_snapshot_state,
    _is_cancel_confirmation_state,
    _order_status_text,
    _parse_order_template_metadata,
    _should_inject_start_image,
)


class _DummySettings:
    commission_percent = 2.0

    def link(self, _key: str) -> str:
        return ""

    def all_links(self) -> dict[str, str]:
        return {}

    def all_sell_wallets(self) -> dict[str, str]:
        return {}


class _DummyRates:
    async def get_rates(self, force: bool = False) -> dict[str, float]:
        return {}

    async def get_rates_rub(self, force: bool = False) -> dict[str, float]:
        return {"btc": 8_000_000.0, "eth": 300_000.0, "ltc": 9_500.0, "xmr": 15_000.0, "usdt": 87.0}


class _CaptureMessage:
    def __init__(self, user_id: int = 12345, username: str = "tester"):
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.chat = SimpleNamespace(id=user_id)
        self.message_id = 100
        self.calls: list[dict[str, object]] = []

    async def answer(self, text: str | None = None, reply_markup=None, **kwargs):
        self.calls.append({"text": text or "", "reply_markup": reply_markup, **kwargs})
        self.message_id += 1
        return self

    async def answer_photo(self, photo, caption: str | None = None, reply_markup=None, **kwargs):
        self.calls.append({"caption": caption or "", "reply_markup": reply_markup, "photo": photo, **kwargs})
        self.message_id += 1
        return self


@pytest.fixture(scope="module")
def runtime() -> FlowRuntime:
    project_dir = Path(__file__).parents[1]
    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )
    app_context = SimpleNamespace(settings=_DummySettings(), rates=_DummyRates(), orders=None)
    return FlowRuntime(project_dir=project_dir, catalog=catalog, app_context=app_context)


def test_source_state_prefers_message_mapping(runtime: FlowRuntime):
    runtime.message_state_ids[(777, 42)] = "317e051f4bc939ec52fca9a311c17f56"
    resolved = runtime._source_state_id(
        session_state_id="9d7af31161437907176c05ca0ebbd35f",
        chat_id=777,
        message_id=42,
    )
    assert resolved == "317e051f4bc939ec52fca9a311c17f56"


def test_source_state_falls_back_to_session(runtime: FlowRuntime):
    resolved = runtime._source_state_id(
        session_state_id="317e051f4bc939ec52fca9a311c17f56",
        chat_id=1,
        message_id=99999,
    )
    assert resolved == "317e051f4bc939ec52fca9a311c17f56"


def test_captcha_always_contains_rfp6p_once():
    codes = _build_captcha_codes()
    assert codes.count("rfp6p") == 1
    assert len(codes) == 4
    assert len(set(codes)) == 4
    assert all(len(code) == 5 for code in codes)


def test_start_lightning_state_stays_text_only(runtime: FlowRuntime):
    start_state = runtime.catalog.states[runtime.catalog.start_state_id]
    assert start_state["text"] == "⚡"
    assert not _should_inject_start_image(start_state)


def test_parse_order_template_metadata(runtime: FlowRuntime):
    state = runtime.catalog.states["317e051f4bc939ec52fca9a311c17f56"]
    parsed = _parse_order_template_metadata(state)
    assert parsed is not None
    assert parsed["service_requisites"] == "bc1qnx30rjntzmr0huuz0cs5uegf0vd45ttud5huaw"
    assert parsed["wallet"] == (
        "47Kv7Szy7ePGBgoYtfXCEH2R4peJsmNfEhD8zQ1sEgBRNiN5Xmt"
        "6bp8W96nUZ9Ea1cXrkA2hkESxkSKuJMzH9qkNDHwaLU4"
    )
    assert parsed["currency_title"] == "Monero"


def test_cancelled_history_snapshot_preserves_formatting(runtime: FlowRuntime):
    state = runtime.catalog.states["317e051f4bc939ec52fca9a311c17f56"]
    snapshot = _build_order_snapshot_state(
        state=state,
        order_id="4321856",
        wallet="47Kv7Szy7ePGBgoYtfXCEH2R4peJsmNfEhD8zQ1sEgBRNiN5Xmt6bp8W96nUZ9Ea1cXrkA2hkESxkSKuJMzH9qkNDHwaLU4",
        status_text="Отменен",
        include_transactions=False,
    )
    assert snapshot["buttons"] == []
    assert snapshot["button_rows"] == []
    assert "⚡️Заявка №<strong>4321856</strong>" in snapshot["text_html"]
    assert "Статус: <strong>Отменен</strong>" in snapshot["text_html"]
    assert (
        "<code>47Kv7Szy7ePGBgoYtfXCEH2R4peJsmNfEhD8zQ1sEgBRNiN5Xmt6bp8W96nUZ9Ea1cXrkA2hkESxkSKuJMzH9qkNDHwaLU4</code>"
        in snapshot["text_html"]
    )
    assert "Валюта: <strong>Monero</strong>" in snapshot["text_html"]
    assert "Комиссия сервиса: <strong>1.5%</strong>" in snapshot["text_html"]
    assert "Минимальная сумма обмена: <strong>0.001 BTC</strong>" in snapshot["text_html"]
    assert "Транзакции:" not in snapshot["text_html"]


def test_live_order_snapshot_can_keep_buttons(runtime: FlowRuntime):
    state = runtime.catalog.states["c9b22348761f7d08315e2c20904c8f58"]
    snapshot = _build_order_snapshot_state(
        state=state,
        order_id="1531854",
        wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
        status_text="Ожидает оплаты",
        include_transactions=True,
        drop_buttons=False,
    )
    assert snapshot["buttons"]
    assert snapshot["button_rows"]
    assert "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb" in snapshot["text"]


def test_runtime_builds_live_order_state_from_stored_order(runtime: FlowRuntime):
    session = runtime.sessions.setdefault(
        12345,
        runtime.sessions.get(12345)
        or SimpleNamespace(
            state_id="c9b22348761f7d08315e2c20904c8f58",
            history=[],
            history_page=0,
            selected_currency_title="Tether TRC-20",
            entered_wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            current_order_id="1531854",
        ),
    )
    order = {
        "order_id": "1531854",
        "user_id": 12345,
        "username": "tester",
        "wallet": "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
        "coin_symbol": "Tether TRC-20",
        "coin_amount": 0.0,
        "amount_rub": 0.0,
        "payment_method": "",
        "bank": "",
        "status": "pending_payment",
        "created_at": 0,
        "updated_at": 0,
        "confirmed_by": None,
    }

    state = runtime._build_order_state_for_order(
        state_id="c9b22348761f7d08315e2c20904c8f58",
        order=order,
        drop_buttons=False,
    )

    assert "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb" in state["text"]
    assert "TYJrM2XU96VYhfjZphSeJb2dHawx7QFG9M" not in state["text"]
    assert "Комиссия сервиса: <strong>1.5%</strong>" not in state["text_html"]
    assert "Комиссия сервиса: <strong>2" in state["text_html"]
    assert state["button_rows"]
    assert session.current_order_id == "1531854"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("pending_payment", "Ожидает оплаты"),
        ("paid", "Ожидает оплаты"),
        ("confirmed", "Подтвержден"),
        ("cancelled", "Отменен"),
    ],
)
def test_order_status_text_mapping(status: str, expected: str):
    assert _order_status_text(status) == expected


def test_cancel_confirmation_state_replaces_order_id(runtime: FlowRuntime):
    base_state = runtime.catalog.states["f0c7778067a0c6183d26cbb4b867bbc4"]
    assert _is_cancel_confirmation_state(base_state)
    state = _build_cancel_confirmation_state(state=base_state, order_id="999888")
    assert state["text"] == "Обмен #999888 отменен"
    assert state["text_html"] == "Обмен #999888 отменен"
    assert state["button_rows"]


def test_cancelled_order_goes_to_history_snapshot(tmp_path: Path):
    project_dir = Path(__file__).parents[1]
    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )
    orders = OrdersStore(tmp_path / "orders.json")
    app_context = SimpleNamespace(settings=_DummySettings(), rates=_DummyRates(), orders=orders)
    runtime = FlowRuntime(project_dir=project_dir, catalog=catalog, app_context=app_context)
    message = _CaptureMessage()

    order = orders.create_order(
        user_id=12345,
        username="tester",
        wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
        coin_symbol="Tether TRC-20",
        coin_amount=0.0,
        amount_rub=0.0,
        payment_method="",
        bank="",
    )
    runtime.sessions[12345] = UserSession(
        state_id="c9b22348761f7d08315e2c20904c8f58",
        history=["c9b22348761f7d08315e2c20904c8f58"],
        selected_currency_title="Tether TRC-20",
        entered_wallet=order["wallet"],
        current_order_id=order["order_id"],
    )

    cancelled = runtime._cancel_current_order(12345)

    assert cancelled is True
    assert orders.get_order(order["order_id"])["status"] == "cancelled"
    assert runtime.sessions[12345].current_order_id == order["order_id"]

    message.calls.clear()
    asyncio.run(runtime._send_state_by_id(message, "f0c7778067a0c6183d26cbb4b867bbc4", user_id=12345))

    cancel_texts = [str(call.get("text", "")) for call in message.calls]
    assert any(f"Обмен #{order['order_id']} отменен" in text for text in cancel_texts)

    message.calls.clear()
    asyncio.run(runtime._send_history_order(message, order["order_id"], requester_user_id=12345))

    history_texts = [str(call.get("text", "")) for call in message.calls]
    assert any(f"Заявка №<strong>{order['order_id']}</strong>" in text for text in history_texts)
    assert any("Статус: <strong>Отменен</strong>" in text for text in history_texts)
    assert all("Транзакции:" not in text for text in history_texts)


def test_cancel_rejected_for_non_pending_order(tmp_path: Path):
    project_dir = Path(__file__).parents[1]
    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )
    orders = OrdersStore(tmp_path / "orders.json")
    app_context = SimpleNamespace(settings=_DummySettings(), rates=_DummyRates(), orders=orders)
    runtime = FlowRuntime(project_dir=project_dir, catalog=catalog, app_context=app_context)

    order = orders.create_order(
        user_id=12345,
        username="tester",
        wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
        coin_symbol="Tether TRC-20",
        coin_amount=0.0,
        amount_rub=0.0,
        payment_method="",
        bank="",
    )
    orders.mark_paid(order["order_id"])
    runtime.sessions[12345] = UserSession(
        state_id="c9b22348761f7d08315e2c20904c8f58",
        history=["c9b22348761f7d08315e2c20904c8f58"],
        selected_currency_title="Tether TRC-20",
        entered_wallet=order["wallet"],
        current_order_id=order["order_id"],
    )

    assert runtime._cancel_current_order(12345) is False
    assert orders.get_order(order["order_id"])["status"] == "paid"


def test_minimum_amount_dynamically_calculated_from_rates():
    """When user sees an order template, the minimum BTC amount should be
    10000 RUB / BTC_RUB_RATE, computed from coingecko rates — not hardcoded."""
    from app.runtime import MINIMUM_RUB

    project_dir = Path(__file__).parents[1]
    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )
    rates = _DummyRates()
    app_context = SimpleNamespace(settings=_DummySettings(), rates=rates, orders=None)
    rt = FlowRuntime(project_dir=project_dir, catalog=catalog, app_context=app_context)

    # Pick an order template state that has "Минимальная сумма обмена: 0.001 BTC"
    state_id = "317e051f4bc939ec52fca9a311c17f56"
    base_state = dict(catalog.states[state_id])
    assert "Минимальная сумма обмена:" in str(base_state.get("text_html"))

    # Apply the override
    asyncio.run(rt._apply_minimum_amount_override(base_state))

    btc_rub = 8_000_000.0  # from _DummyRates.get_rates_rub
    expected_min = MINIMUM_RUB / btc_rub
    expected_str = f"{expected_min:.4f}".rstrip("0").rstrip(".")

    # Verify all text fields got updated
    assert f"Минимальная сумма обмена: {expected_str} BTC" in base_state["text"]
    assert f"Минимальная сумма обмена: <strong>{expected_str} BTC</strong>" in base_state["text_html"]
    assert f"Минимальная сумма обмена: **{expected_str} BTC**" in base_state["text_markdown"]
    # Old hardcoded value must be gone
    assert "0.001 BTC" not in base_state["text"]
