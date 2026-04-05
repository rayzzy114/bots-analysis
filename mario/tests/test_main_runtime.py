from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.live_quote import SELL_PAYOUT_RATIO
from app.models import QuoteRecord
from main import CloneRuntime, _collect_reload_snapshot


class DummyMessage:
    def __init__(self) -> None:
        self.answers: list[tuple[str, dict[str, object]]] = []

    async def answer(self, text: str, **kwargs: object) -> None:
        self.answers.append((text, kwargs))


def _settings(project_dir: Path, tmp_path: Path) -> Settings:
    return Settings(
        project_dir=project_dir,
        bot_token="test-token",
        debug=False,
        hot_reload=False,
        hot_reload_interval_seconds=1.0,
        session_history_limit=30,
        order_ttl_seconds=900,
        log_level="INFO",
        admin_ids=set(),
        default_commission_percent=2.5,
        rate_cache_ttl_seconds=45,
        delete_webhook_on_start=False,
        search_delay_seconds=1,
        raw_dir=project_dir / "data" / "raw",
        compiled_dir=tmp_path / "compiled",
        media_dir=project_dir / "assets" / "media",
        orders_store_path=tmp_path / "runtime_orders.json",
        sessions_store_path=tmp_path / "runtime_sessions.json",
        admin_settings_path=tmp_path / "admin_settings.json",
        media_file_id_cache_path=tmp_path / "runtime_media_file_ids.json",
    )


def _runtime(tmp_path: Path) -> CloneRuntime:
    project_dir = Path(__file__).resolve().parents[1]
    return CloneRuntime(_settings(project_dir, tmp_path))


def test_back_uses_history_instead_of_default_next(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)

    back_state_id = next(
        sid
        for sid, state in runtime.states.items()
        if "Назад" in (state.get("interactive_actions") or [])
        and "button:Назад" not in runtime.transition_engine.by_state.get(sid, {})
    )

    user_id = 123
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.history = [runtime.entry_state_id, back_state_id]
    session.current_state_id = back_state_id

    sent: list[str] = []

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        sent.append(state_id)
        current_session.push_state(state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(object(), user_id, "Назад", is_text_input=False))

    assert sent == [runtime.entry_state_id]
    assert session.current_state_id == runtime.entry_state_id


def test_hot_reload_snapshot_tracks_env_and_python(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    py_file = app_dir / "main.py"
    py_file.write_text("print('ok')\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("A=1\n", encoding="utf-8")

    snapshot_before = _collect_reload_snapshot(tmp_path)

    (app_dir / "new.py").write_text("print('new')\n", encoding="utf-8")
    snapshot_after = _collect_reload_snapshot(tmp_path)

    assert snapshot_before != snapshot_after


def test_amount_prompt_invalid_input_does_not_fall_back_to_static_flow(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 500
    prompt_state = runtime.replay_calc.prompt_states["buy"]["LTC"]
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "buy"
    session.pending_coin = "LTC"
    session.last_quote_state_id = None
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, _session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)

    msg = DummyMessage()
    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(msg, user_id, "abc", is_text_input=True))

    assert sent_states == []
    assert msg.answers and msg.answers[-1][0] == "Невалидное значение."
    assert session.current_state_id == prompt_state
    assert session.last_quote_state_id is None


def test_amount_prompt_numeric_uses_dynamic_values_not_dataset_defaults(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 501
    prompt_state = runtime.replay_calc.prompt_states["buy"]["LTC"]
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "buy"
    session.pending_coin = "LTC"
    captured: list[tuple[str, str | None, str | None]] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"ltc": 10_000.0}

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        text_html = kwargs.get("text_override")
        text_plain = kwargs.get("text_override_plain")
        captured.append(
            (
                state_id,
                text_html if isinstance(text_html, str) else None,
                text_plain if isinstance(text_plain, str) else None,
            )
        )
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "300", is_text_input=True))

    assert captured
    quote_text = (captured[0][1] or captured[0][2] or "")
    assert "Сумма к оплате: 300 ₽" in quote_text
    assert "2550" not in quote_text
    assert "0.42889" not in quote_text
    assert session.last_quote_rub_amount is not None
    assert int(round(session.last_quote_rub_amount)) == 300


def test_new_quote_clears_previous_order_id(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 502
    prompt_state = runtime.replay_calc.prompt_states["sell"]["BTC"]
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "sell"
    session.pending_coin = "BTC"
    session.last_order_id = "old-order-id"

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"btc": 6_000_000.0}

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "0.01", is_text_input=True))

    assert session.last_order_id is None


def test_auto_chain_does_not_jump_from_order_searching_to_menu(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 503
    searching_state = next(
        sid
        for sid, state in runtime.states.items()
        if state.get("kind") == "order_searching"
        and "system:auto" in runtime.transition_engine.by_state.get(sid, {})
    )
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = searching_state
    session.history = [runtime.entry_state_id, searching_state]
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, _session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime._auto_chain(DummyMessage(), session))

    assert sent_states == []
    assert session.current_state_id == searching_state


def test_auto_chain_ignores_default_next_without_system_auto(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    blocked_kinds = {
        "buy_amount_prompt",
        "sell_amount_prompt",
        "wallet_prompt",
        "order_searching",
        "order_found",
        "order_cancelled",
    }
    candidate_state = None
    for sid, state in runtime.states.items():
        if sid not in runtime.transition_engine.default_next:
            continue
        if "system:auto" in runtime.transition_engine.by_state.get(sid, {}):
            continue
        if state.get("interactive_actions"):
            continue
        if str(state.get("kind") or "") in blocked_kinds:
            continue
        candidate_state = sid
        break
    if candidate_state is None:
        pytest.skip("No state with default_next fallback-only transition found in fixture flow.")

    user_id = 1503
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = candidate_state
    session.history = [runtime.entry_state_id, candidate_state]
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, _session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime._auto_chain(DummyMessage(), session))

    assert sent_states == []
    assert session.current_state_id == candidate_state


def test_amount_prompt_does_not_force_fallback_transition(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1510
    prompt_state = runtime.replay_calc.prompt_states["buy"]["LTC"]
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "buy"
    session.pending_coin = "LTC"
    sent_states: list[str] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"ltc": 10_000.0}

    original_resolve_next = runtime.transition_engine.resolve_next

    def resolve_next_fallback_only(
        state_id: str,
        *,
        action_text: str = "",
        is_text_input: bool = False,
        session_history: list[str] | None = None,
    ) -> tuple[str | None, str]:
        if not action_text and not is_text_input:
            return runtime.entry_state_id, "fallback:default_next"
        return original_resolve_next(
            state_id,
            action_text=action_text,
            is_text_input=is_text_input,
            session_history=session_history,
        )

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime.transition_engine.resolve_next = resolve_next_fallback_only  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "300", is_text_input=True))

    assert len(sent_states) == 1


def test_wallet_input_starts_search_and_creates_runtime_buy_order(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 504
    wallet_prompt = next(sid for sid, state in runtime.states.items() if state.get("kind") == "wallet_prompt")
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = wallet_prompt
    session.history = [runtime.entry_state_id, wallet_prompt]
    session.pending_operation = "buy"
    session.pending_coin = "LTC"
    session.pending_payment_method = "📱СБП"
    session.last_quote_state_id = "40e326a580739cc43dcab2c8da179721"
    session.last_quote_coin_amount = 0.42889
    session.last_quote_rub_amount = 2550.0
    session.last_quote_net_amount = 1774.0
    session.last_order_id = None
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)
        current_session.push_state(state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "LTC_WALLET_123", is_text_input=True))

    assert sent_states and sent_states[0] == runtime.search_wait_state_id
    assert session.last_order_id is not None
    order = runtime.orders.by_id(session.last_order_id)
    assert order is not None
    assert order.operation == "buy"
    assert runtime.entry_state_id not in sent_states
    runtime._cancel_search_task(user_id)


def test_render_runtime_order_text_buy_is_not_template_hardcoded(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 505
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.pending_operation = "buy"
    session.pending_coin = "USDT"
    session.pending_wallet = "TVL7QeXiaLQX5d5fyFXpighpncmf2skXdp"
    session.pending_payment_method = "📱СБП"
    session.last_quote_state_id = "7e31b306d6f92ae341f59de08ffb89d3"
    session.last_quote_coin_amount = 100.0
    session.last_quote_rub_amount = 8751.0
    session.last_quote_net_amount = None

    order = runtime._ensure_runtime_order(user_id, session)
    assert order is not None
    text_plain, text_html, _state_id = runtime._render_runtime_order_text(order)

    assert "Покупаете: 100 usdt" in text_plain
    assert "К оплате: 8751 ₽" in text_plain
    assert "2500 usdt" not in text_plain
    assert "216218 ₽" not in text_plain
    assert "Покупаете" in text_html


def test_sell_order_card_uses_admin_crypto_wallet(tmp_path: Path) -> None:
    settings_path = tmp_path / "admin_settings.json"
    settings_path.write_text(
        """
{
  "requisites": {
    "mode": "single",
    "single_bank": "Сбербанк",
    "single_value": "2200 0000 0000 0000",
    "payment_methods": ["СБП"],
    "split_by_method": {
      "СБП": {"bank": "Сбербанк", "value": "2200 0000 0000 0000"}
    },
    "crypto_wallets": {
      "BTC": "bc1qadminwalletforbtcsell"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    runtime = _runtime(tmp_path)
    quote = QuoteRecord(
        state_id="qs",
        operation="sell",
        coin="BTC",
        coin_amount=0.02,
        rub_amount=90_000.0,
        net_amount=None,
    )
    order = runtime.orders.create_order(
        user_id=1701,
        operation="sell",
        coin="BTC",
        input_amount=0.02,
        quote=quote,
        payment_method="СБП",
        wallet_or_requisites="79001112233",
    )

    rendered_plain, rendered_html, _state_id = runtime._render_runtime_order_text(order)
    rendered = f"{rendered_plain}\n{rendered_html}"
    assert "bc1qadminwalletforbtcsell" in rendered


def test_amount_prompt_accepts_comma_decimal(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 506
    prompt_state = runtime.replay_calc.prompt_states["sell"]["BTC"]
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "sell"
    session.pending_coin = "BTC"

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"btc": 6_000_000.0}

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "0,01", is_text_input=True))

    assert session.last_quote_coin_amount is not None
    assert 0.0099 < session.last_quote_coin_amount < 0.0101
    assert session.last_quote_rub_amount is not None
    assert int(round(session.last_quote_rub_amount)) == 48000


@pytest.mark.e2e
def test_admin_commission_update_affects_runtime_quote_and_promo(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["buy"]["BTC"]
    user_id = 1601
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    captured: list[dict[str, str]] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"btc": 7_500_000.0}

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        state = runtime.get_state(state_id)
        html = kwargs.get("text_override")
        plain = kwargs.get("text_override_plain")
        captured.append(
            {
                "kind": str(state.get("kind") or ""),
                "html": html if isinstance(html, str) else "",
                "plain": plain if isinstance(plain, str) else "",
            }
        )
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    def run_once(commission_percent: float) -> tuple[float, str]:
        runtime.admin_settings.set_commission(commission_percent)
        session.current_state_id = prompt_state
        session.history = [runtime.entry_state_id, prompt_state]
        session.pending_operation = "buy"
        session.pending_coin = "BTC"
        session.pending_amount_raw = None
        session.pending_wallet = None
        session.last_quote_state_id = None
        session.last_quote_coin_amount = None
        session.last_quote_rub_amount = None
        session.last_quote_net_amount = None
        session.last_order_id = None
        captured.clear()

        asyncio.run(runtime.handle_action(DummyMessage(), user_id, "2550", is_text_input=True))
        assert captured and captured[0]["kind"] == "quote"
        assert session.last_quote_net_amount is not None

        promo_pair = runtime._render_promo_confirm_text(session)
        assert promo_pair is not None
        _, promo_plain = promo_pair
        return float(session.last_quote_net_amount), promo_plain

    low_net, low_promo = run_once(2.5)
    high_net, high_promo = run_once(10.0)

    assert runtime._current_commission() == pytest.approx(10.0)
    assert low_net > high_net
    assert "2537" in low_promo
    assert "2499" in high_promo

    reloaded = _runtime(tmp_path)
    assert reloaded._current_commission() == pytest.approx(10.0)


@pytest.mark.e2e
def test_promo_choice_affects_payment_amount_in_method_step(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["buy"]["BTC"]
    user_id = 1610
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    runtime.admin_settings.set_commission(30.0)

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"btc": 7_500_000.0}

    runtime._current_rates = fake_rates  # type: ignore[method-assign]

    def run_once(promo_action: str) -> str:
        captured: list[dict[str, str]] = []
        session.current_state_id = prompt_state
        session.history = [runtime.entry_state_id, prompt_state]
        session.pending_operation = "buy"
        session.pending_coin = "BTC"
        session.pending_amount_raw = None
        session.pending_wallet = None
        session.last_quote_state_id = None
        session.last_quote_coin_amount = None
        session.last_quote_rub_amount = None
        session.last_quote_net_amount = None
        session.last_order_id = None

        async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
            state = runtime.get_state(state_id)
            html = kwargs.get("text_override")
            plain = kwargs.get("text_override_plain")
            captured.append(
                {
                    "kind": str(state.get("kind") or ""),
                    "html": html if isinstance(html, str) else "",
                    "plain": plain if isinstance(plain, str) else "",
                }
            )
            current_session.push_state(state_id, runtime.settings.session_history_limit)
            op, state_coin = runtime._state_coin_context(state_id)
            if op:
                current_session.pending_operation = op
                current_session.pending_coin = state_coin

        runtime._send_state = fake_send_state  # type: ignore[method-assign]
        asyncio.run(runtime.handle_action(DummyMessage(), user_id, "9000", is_text_input=True))
        asyncio.run(runtime.handle_action(DummyMessage(), user_id, promo_action, is_text_input=False))

        pay_rows = [row for row in captured if row["kind"] == "payment_method_select"]
        assert pay_rows, f"payment_method_select was not sent for action={promo_action}"
        return pay_rows[-1]["plain"] or pay_rows[-1]["html"]

    with_promo_text = run_once("Использовать промокод")
    without_promo_text = run_once("Не использовать промокод")

    assert "Нужно перевести: 8460 ₽" in with_promo_text
    assert "Нужно перевести: 9000 ₽" in without_promo_text


def test_wallet_input_starts_search_and_creates_runtime_sell_order(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 507
    wallet_prompt = next(sid for sid, state in runtime.states.items() if state.get("kind") == "wallet_prompt")
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = wallet_prompt
    session.history = [runtime.entry_state_id, wallet_prompt]
    session.pending_operation = "sell"
    session.pending_coin = "BTC"
    session.pending_payment_method = "📱СБП"
    session.last_quote_state_id = "980df86a1c1d3205a2b3605740d4bece"
    session.last_quote_coin_amount = 0.015
    session.last_quote_rub_amount = 84899.0
    session.last_quote_net_amount = None
    session.last_order_id = None
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)
        current_session.push_state(state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "79001112233", is_text_input=True))

    assert sent_states and sent_states[0] == runtime.search_wait_state_id
    assert session.last_order_id is not None
    order = runtime.orders.by_id(session.last_order_id)
    assert order is not None
    assert order.operation == "sell"
    runtime._cancel_search_task(user_id)


def test_auto_chain_does_not_jump_from_order_found_or_cancelled(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    blocked_kinds = {"order_found", "order_cancelled"}
    blocked_states = [
        sid for sid, state in runtime.states.items() if str(state.get("kind") or "") in blocked_kinds
    ]
    assert blocked_states
    for idx, state_id in enumerate(blocked_states, start=1):
        user_id = 600 + idx
        session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
        session.current_state_id = state_id
        session.history = [runtime.entry_state_id, state_id]
        sent_states: list[str] = []

        async def fake_send_state(_msg: object, _session: object, sid: str, **_kwargs: object) -> None:
            sent_states.append(sid)

        runtime._send_state = fake_send_state  # type: ignore[method-assign]
        asyncio.run(runtime._auto_chain(DummyMessage(), session))
        assert sent_states == []


@pytest.mark.e2e
@pytest.mark.parametrize("coin", ["BTC", "LTC", "USDT", "TRX"])
def test_e2e_buy_all_coins_dynamic_payment_text(tmp_path: Path, coin: str) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["buy"][coin]
    user_id = 700 + hash(coin) % 100
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "buy"
    session.pending_coin = coin
    captured: list[dict[str, str]] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {
            "btc": 5_800_000.0,
            "ltc": 9_500.0,
            "usdt": 98.0,
            "trx": 21.0,
            "xmr": 25_000.0,
            "eth": 250_000.0,
            "sol": 10_000.0,
        }

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        state = runtime.get_state(state_id)
        html = kwargs.get("text_override")
        plain = kwargs.get("text_override_plain")
        captured.append(
            {
                "kind": str(state.get("kind") or ""),
                "html": html if isinstance(html, str) else "",
                "plain": plain if isinstance(plain, str) else "",
                "state_id": state_id,
            }
        )
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "3000", is_text_input=True))

    assert session.last_quote_state_id is not None
    assert session.last_quote_rub_amount is not None
    expected_rub = int(round(session.last_quote_rub_amount))
    assert expected_rub > 0
    assert captured and captured[0]["kind"] == "quote"
    quote_text = captured[0]["plain"] or captured[0]["html"]
    assert f"{expected_rub} ₽" in quote_text
    assert "2550 ₽" not in quote_text
    assert "238837 ₽" not in quote_text

    current_state = runtime.get_state(session.current_state_id)
    if str(current_state.get("kind") or "") == "payment_method_select":
        payment_rows = [row for row in captured if row["kind"] == "payment_method_select"]
        assert payment_rows
        payment_text = payment_rows[0]["plain"] or payment_rows[0]["html"]
        assert f"Нужно перевести: {expected_rub} ₽" in payment_text
        assert "Покупка" in payment_text
        assert "2550 ₽" not in payment_text
        assert "238837 ₽" not in payment_text
        assert "0.00033" not in payment_text
        return

    actions = list(current_state.get("interactive_actions") or [])
    promo_action = ""
    for action in actions:
        next_state, _ = runtime.transition_engine.resolve_next(
            session.current_state_id,
            action_text=action,
            is_text_input=False,
            session_history=session.history,
        )
        if not next_state:
            continue
        if str(runtime.get_state(next_state).get("kind") or "") == "payment_method_select":
            promo_action = action
            break
    if not promo_action and "Не использовать промокод" in actions:
        promo_action = "Не использовать промокод"
    assert promo_action, f"No path to payment_method_select for coin={coin}, actions={actions}"
    captured.clear()
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, promo_action, is_text_input=False))

    payment_rows = [row for row in captured if row["kind"] == "payment_method_select"]
    assert payment_rows
    payment_text = payment_rows[0]["plain"] or payment_rows[0]["html"]
    expected_payment_rub = expected_rub
    if promo_action == "Использовать промокод":
        promo_ratio = max(0.0, 1.0 - ((runtime._current_commission() * 0.2) / 100.0))
        expected_payment_rub = int(round(float(session.last_quote_rub_amount or expected_rub) * promo_ratio))
    assert f"Нужно перевести: {expected_payment_rub} ₽" in payment_text
    assert "Покупка" in payment_text
    assert "2550 ₽" not in payment_text
    assert "238837 ₽" not in payment_text
    assert "0.00033" not in payment_text

    # Continue to wallet/info and verify dynamic amount there too.
    wallet_like: list[dict[str, str]] = []
    for _ in range(3):
        current_state = runtime.get_state(session.current_state_id)
        next_actions = [
            action
            for action in (current_state.get("interactive_actions") or [])
            if action != "Назад"
        ]
        if not next_actions:
            break
        action = "Не использовать промокод" if "Не использовать промокод" in next_actions else next_actions[0]
        captured.clear()
        asyncio.run(runtime.handle_action(DummyMessage(), user_id, action, is_text_input=False))
        wallet_like = [row for row in captured if row["kind"] in {"wallet_prompt", "info"}]
        if wallet_like:
            break

    assert wallet_like, f"wallet/info step not reached for coin={coin}"
    wallet_text = " ".join((row["plain"] or row["html"]) for row in wallet_like)
    assert "2550" not in wallet_text
    assert "0.00033" not in wallet_text


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("coin", "user_input", "rate_key", "rate_value"),
    [
        ("BTC", "0.01", "btc", 6_100_000.0),
        ("LTC", "1.2", "ltc", 9_200.0),
        ("USDT", "120", "usdt", 97.0),
        ("XMR", "0.2", "xmr", 24_000.0),
    ],
)
def test_e2e_sell_all_coins_dynamic_quote_amounts(
    tmp_path: Path,
    coin: str,
    user_input: str,
    rate_key: str,
    rate_value: float,
) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["sell"][coin]
    user_id = 800 + hash(coin) % 100
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "sell"
    session.pending_coin = coin
    captured: list[dict[str, str]] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {
            "btc": 5_500_000.0,
            "ltc": 8_800.0,
            "usdt": 95.0,
            "trx": 20.0,
            "xmr": 22_000.0,
            rate_key: rate_value,
        }

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        state = runtime.get_state(state_id)
        html = kwargs.get("text_override")
        plain = kwargs.get("text_override_plain")
        captured.append(
            {
                "kind": str(state.get("kind") or ""),
                "html": html if isinstance(html, str) else "",
                "plain": plain if isinstance(plain, str) else "",
            }
        )
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    asyncio.run(runtime.handle_action(DummyMessage(), user_id, user_input, is_text_input=True))

    assert captured and captured[0]["kind"] == "quote"
    assert session.last_quote_coin_amount is not None
    assert session.last_quote_rub_amount is not None
    expected_rub = float(user_input.replace(",", ".")) * rate_value * SELL_PAYOUT_RATIO
    assert int(round(session.last_quote_rub_amount)) == int(round(expected_rub))
    quote_text = captured[0]["plain"] or captured[0]["html"]
    assert "Сумма к получению:" in quote_text
    assert "2550 ₽" not in quote_text
    assert "0.00033" not in quote_text
    promo_rows = [row for row in captured if row["kind"] == "promo_confirm"]
    if promo_rows:
        promo_text = promo_rows[0]["plain"] or promo_rows[0]["html"]
        expected_rub = int(round(session.last_quote_rub_amount or 0.0))
        assert str(expected_rub) in promo_text
        assert "2550 " not in promo_text
        assert "84899 " not in promo_text


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("coin", "rate_key", "rate_value"),
    [
        ("BTC", "btc", 6_000_000.0),
        ("LTC", "ltc", 9_000.0),
        ("USDT", "usdt", 100.0),
        ("XMR", "xmr", 23_000.0),
    ],
)
def test_e2e_sell_integer_input_is_coin_not_rub(
    tmp_path: Path,
    coin: str,
    rate_key: str,
    rate_value: float,
) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["sell"][coin]
    user_id = 900 + hash(coin) % 100
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "sell"
    session.pending_coin = coin
    captured: list[dict[str, str]] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {
            "btc": 5_500_000.0,
            "ltc": 8_800.0,
            "usdt": 95.0,
            "trx": 20.0,
            "xmr": 22_000.0,
            rate_key: rate_value,
        }

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        state = runtime.get_state(state_id)
        html = kwargs.get("text_override")
        plain = kwargs.get("text_override_plain")
        captured.append(
            {
                "kind": str(state.get("kind") or ""),
                "html": html if isinstance(html, str) else "",
                "plain": plain if isinstance(plain, str) else "",
            }
        )
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "9000", is_text_input=True))

    assert captured and captured[0]["kind"] == "quote"
    assert session.last_quote_coin_amount is not None
    assert int(round(session.last_quote_coin_amount)) == 9000
    assert session.last_quote_rub_amount is not None
    assert int(round(session.last_quote_rub_amount)) == int(round(9000 * rate_value * SELL_PAYOUT_RATIO))
    quote_text = captured[0]["plain"] or captured[0]["html"]
    assert "Сумма к получению:" in quote_text
    assert "Сумма к оплате: 9000 " in quote_text
    assert "Сумма к получению: 9000 ₽" not in quote_text


@pytest.mark.e2e
def test_e2e_sell_btc_small_coin_input_not_zero(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["sell"]["BTC"]
    user_id = 998
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "sell"
    session.pending_coin = "BTC"
    captured: list[str] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"btc": 6_000_000.0, "ltc": 8_800.0, "usdt": 95.0, "trx": 20.0, "xmr": 22_000.0}

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        text = kwargs.get("text_override_plain") or kwargs.get("text_override") or ""
        captured.append(str(text))
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "0.05", is_text_input=True))

    assert session.last_quote_coin_amount is not None
    assert abs(session.last_quote_coin_amount - 0.05) < 1e-9
    assert session.last_quote_rub_amount is not None
    assert int(round(session.last_quote_rub_amount)) == 240000
    joined = "\n".join(captured)
    assert "Сумма к получению: 0 ₽" not in joined
    assert "Сумма к оплате: 0.00000001 btc" not in joined


@pytest.mark.e2e
def test_sell_prompt_ignores_stale_pending_operation_and_uses_sell_logic(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["sell"]["BTC"]
    user_id = 999
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "buy"  # stale data from previous branch
    session.pending_coin = "BTC"
    captured: list[str] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"btc": 6_000_000.0}

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        text = kwargs.get("text_override_plain") or kwargs.get("text_override") or ""
        captured.append(str(text))
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "1", is_text_input=True))

    assert session.pending_operation == "sell"
    assert captured
    quote_text = captured[0]
    assert "Сумма к получению: 4800000 ₽" in quote_text
    assert "Сумма к оплате: 1 btc" in quote_text
    assert "Сумма к оплате: 1 ₽" not in quote_text


@pytest.mark.e2e
@pytest.mark.parametrize(
    ("coin", "user_input", "rate_key", "rate_value"),
    [
        ("BTC", "0.02", "btc", 6_100_000.0),
        ("LTC", "1.2", "ltc", 9_200.0),
        ("USDT", "120", "usdt", 97.0),
        ("XMR", "0.2", "xmr", 24_000.0),
    ],
)
def test_e2e_sell_all_coins_dynamic_until_order_card(
    tmp_path: Path,
    coin: str,
    user_input: str,
    rate_key: str,
    rate_value: float,
) -> None:
    runtime = _runtime(tmp_path)
    prompt_state = runtime.replay_calc.prompt_states["sell"][coin]
    user_id = 1100 + hash(coin) % 100
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "sell"
    session.pending_coin = coin
    captured: list[dict[str, str]] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {
            "btc": 5_500_000.0,
            "ltc": 8_800.0,
            "usdt": 95.0,
            "trx": 20.0,
            "xmr": 22_000.0,
            rate_key: rate_value,
        }

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **kwargs: object) -> None:
        state = runtime.get_state(state_id)
        html = kwargs.get("text_override")
        plain = kwargs.get("text_override_plain")
        captured.append(
            {
                "kind": str(state.get("kind") or ""),
                "state_id": state_id,
                "html": html if isinstance(html, str) else "",
                "plain": plain if isinstance(plain, str) else "",
            }
        )
        current_session.push_state(state_id, runtime.settings.session_history_limit)
        op, state_coin = runtime._state_coin_context(state_id)
        if op:
            current_session.pending_operation = op
            current_session.pending_coin = state_coin

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]

    # amount prompt -> quote (and possibly promo auto-step)
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, user_input, is_text_input=True))
    assert captured and captured[0]["kind"] == "quote"
    assert session.last_quote_rub_amount is not None
    expected_rub = int(round(session.last_quote_rub_amount))
    quote_text = captured[0]["plain"] or captured[0]["html"]
    assert str(expected_rub) in quote_text
    assert "2550 ₽" not in quote_text
    assert "0.00033" not in quote_text

    # Move forward until requisites prompt.
    for _ in range(4):
        current = runtime.get_state(session.current_state_id)
        current_kind = str(current.get("kind") or "")
        if current_kind == "info":
            break
        actions = [x for x in (current.get("interactive_actions") or []) if x != "Назад"]
        if not actions:
            break
        action = "Не использовать промокод" if "Не использовать промокод" in actions else actions[0]
        asyncio.run(runtime.handle_action(DummyMessage(), user_id, action, is_text_input=False))

    current = runtime.get_state(session.current_state_id)
    assert str(current.get("kind") or "") == "info"
    info_rows = [row for row in captured if row["kind"] == "info"]
    assert info_rows
    info_text = info_rows[-1]["plain"] or info_rows[-1]["html"]
    assert f"{expected_rub} ₽" in info_text
    assert "2550 ₽" not in info_text
    assert "84899 ₽" not in info_text

    # Enter requisites -> searching -> runtime order card should stay dynamic.
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "79001112233", is_text_input=True))
    assert any(row["kind"] == "order_searching" for row in captured)
    assert session.last_order_id is not None
    order = runtime.orders.by_id(session.last_order_id)
    assert order is not None
    assert order.operation == "sell"
    assert order.coin == coin
    rendered_plain, rendered_html, _state_id = runtime._render_runtime_order_text(order)
    rendered = f"{rendered_plain}\n{rendered_html}"
    assert str(expected_rub) in rendered
    assert "2550 ₽" not in rendered
    assert "2500 usdt" not in rendered
    assert "216218 ₽" not in rendered
    runtime._cancel_search_task(user_id)


def test_paid_action_does_not_add_non_flow_screenshot_prompt(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1201
    state_id = next(
        sid
        for sid, state in runtime.states.items()
        if "Оплатил" in (state.get("interactive_actions") or [])
        and runtime.transition_engine.resolve_next(
            sid,
            action_text="Оплатил",
            is_text_input=False,
            session_history=[sid],
        )[0]
    )
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = state_id
    session.history = [runtime.entry_state_id, state_id]

    async def fake_send_state(_msg: object, current_session: object, next_state_id: str, **_kwargs: object) -> None:
        current_session.push_state(next_state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    msg = DummyMessage()
    asyncio.run(runtime.handle_action(msg, user_id, "Оплатил", is_text_input=False))

    assert not msg.answers


def test_paid_action_goes_directly_to_receipt_prompt(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1202
    state_id = next(
        sid
        for sid, state in runtime.states.items()
        if str(state.get("kind") or "") == "order_card"
        and "Оплатил" in (state.get("interactive_actions") or [])
        and runtime.transition_engine.resolve_next(
            sid,
            action_text="Оплатил",
            is_text_input=False,
            session_history=[sid],
        )[0]
    )
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = state_id
    session.history = [runtime.entry_state_id, state_id]
    quote = QuoteRecord(
        state_id="quote",
        operation="buy",
        coin="BTC",
        coin_amount=0.001,
        rub_amount=5000.0,
        net_amount=None,
    )
    order = runtime.orders.create_order(
        user_id=user_id,
        operation="buy",
        coin="BTC",
        input_amount=5000.0,
        quote=quote,
        payment_method="СБП",
        wallet_or_requisites="bc1qtest",
    )
    session.last_order_id = order.order_id

    sent_states: list[str] = []

    async def fake_send_state(_msg: object, current_session: object, next_state_id: str, **_kwargs: object) -> None:
        sent_states.append(next_state_id)
        current_session.push_state(next_state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "Оплатил", is_text_input=False))

    assert runtime.receipt_prompt_state_id is not None
    assert sent_states == [runtime.receipt_prompt_state_id]
    paid_order = runtime.orders.by_id(order.order_id)
    assert paid_order is not None
    assert paid_order.status == "paid"


def test_payment_methods_state_uses_admin_settings_methods(tmp_path: Path) -> None:
    settings_path = tmp_path / "admin_settings.json"
    settings_path.write_text(
        """
{
  "requisites": {
    "mode": "split",
    "single_bank": "Сбербанк",
    "single_value": "2200 0000 0000 0000",
    "payment_methods": ["СБП", "Карта РФ"],
    "split_by_method": {
      "СБП": {"bank": "Сбербанк", "value": "79000000000"},
      "Карта РФ": {"bank": "Тинькофф", "value": "2200000000000000"}
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    runtime = _runtime(tmp_path)
    payment_state = next(sid for sid, state in runtime.states.items() if state.get("kind") == "payment_method_select")
    actions = list(runtime.get_state(payment_state).get("interactive_actions") or [])

    assert actions == ["СБП", "Карта РФ", "Назад"]


def test_selecting_admin_payment_method_sets_pending_method(tmp_path: Path) -> None:
    settings_path = tmp_path / "admin_settings.json"
    settings_path.write_text(
        """
{
  "requisites": {
    "mode": "split",
    "single_bank": "Сбербанк",
    "single_value": "2200 0000 0000 0000",
    "payment_methods": ["СБП", "Карта РФ"],
    "split_by_method": {
      "СБП": {"bank": "Сбербанк", "value": "79000000000"},
      "Карта РФ": {"bank": "Тинькофф", "value": "2200000000000000"}
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    runtime = _runtime(tmp_path)
    user_id = 1203
    payment_state = next(sid for sid, state in runtime.states.items() if state.get("kind") == "payment_method_select")
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = payment_state
    session.history = [runtime.entry_state_id, payment_state]
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, current_session: object, next_state_id: str, **_kwargs: object) -> None:
        sent_states.append(next_state_id)
        current_session.push_state(next_state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "Карта РФ", is_text_input=False))

    assert session.pending_payment_method == "Карта РФ"
    assert sent_states


def test_photo_notification_is_forwarded_to_admins(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    sender_id = 1301
    runtime.admin_ctx.admin_ids = {1301, 2301}
    session = runtime.sessions.get_or_create(sender_id, runtime.entry_state_id)
    session.last_order_id = "order-42"

    class FakeBot:
        def __init__(self) -> None:
            self.messages: list[tuple[int, str]] = []
            self.forwards: list[tuple[int, int, int]] = []

        async def send_message(self, chat_id: int, text: str, **_kwargs: object) -> None:
            self.messages.append((chat_id, text))

        async def forward_message(self, chat_id: int, from_chat_id: int, message_id: int) -> None:
            self.forwards.append((chat_id, from_chat_id, message_id))

    fake_bot = FakeBot()
    fake_msg = SimpleNamespace(
        from_user=SimpleNamespace(id=sender_id, username="alice", first_name="Alice", last_name=None),
        chat=SimpleNamespace(id=sender_id),
        message_id=77,
    )

    asyncio.run(runtime.notify_admins_about_media(fake_bot, fake_msg, media_kind="photo"))

    assert len(fake_bot.messages) == 2
    assert {chat_id for chat_id, _text in fake_bot.messages} == {1301, 2301}
    assert all("Пользователь отправил фото" in text for _chat_id, text in fake_bot.messages)
    assert all("ID: 1301" in text for _chat_id, text in fake_bot.messages)
    assert all("Заявка: order-42" in text for _chat_id, text in fake_bot.messages)
    assert sorted(fake_bot.forwards) == [(1301, 1301, 77), (2301, 1301, 77)]


def test_photo_receipt_acknowledgement_for_paid_order(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1302
    quote = QuoteRecord(
        state_id="quote",
        operation="buy",
        coin="BTC",
        coin_amount=0.001,
        rub_amount=5000.0,
        net_amount=None,
    )
    order = runtime.orders.create_order(
        user_id=user_id,
        operation="buy",
        coin="BTC",
        input_amount=5000.0,
        quote=quote,
        payment_method="СБП",
        wallet_or_requisites="bc1qtest",
    )
    runtime.orders.update_status(order.order_id, "paid")
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.last_order_id = order.order_id

    class FakeBot:
        async def send_message(self, chat_id: int, text: str, **_kwargs: object) -> None:
            _ = (chat_id, text)

        async def forward_message(self, chat_id: int, from_chat_id: int, message_id: int) -> None:
            _ = (chat_id, from_chat_id, message_id)

    class FakeMessage:
        def __init__(self) -> None:
            self.answers: list[str] = []
            self.from_user = SimpleNamespace(id=user_id, username="alice", first_name="Alice", last_name=None)
            self.chat = SimpleNamespace(id=user_id)
            self.message_id = 88

        async def answer(self, text: str, **_kwargs: object) -> None:
            self.answers.append(text)

    fake_msg = FakeMessage()
    asyncio.run(runtime.notify_admins_about_media(FakeBot(), fake_msg, media_kind="photo"))

    assert fake_msg.answers
    assert "Чек принят" in fake_msg.answers[-1]


def test_main_menu_bonus_aliases_to_lottery_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1401
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = runtime.entry_state_id
    session.history = [runtime.entry_state_id]
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, current_session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)
        current_session.push_state(state_id, runtime.settings.session_history_limit)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "🎰Бонус🎰", is_text_input=False))

    lottery_state, reason = runtime.transition_engine.resolve_next(
        runtime.entry_state_id,
        action_text="🤑Большой розыгрыш🤑",
        is_text_input=False,
        session_history=[runtime.entry_state_id],
    )
    assert reason.startswith("action:")
    assert lottery_state is not None
    assert sent_states == [lottery_state]
    assert session.current_state_id == lottery_state


def test_main_menu_history_no_fallback_to_buy_menu(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1402
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = runtime.entry_state_id
    session.history = [runtime.entry_state_id]
    msg = DummyMessage()

    asyncio.run(runtime.handle_action(msg, user_id, "История сделок", is_text_input=False))

    next_state, reason = runtime.transition_engine.resolve_next(
        runtime.entry_state_id,
        action_text="История сделок",
        is_text_input=False,
        session_history=[runtime.entry_state_id],
    )
    assert next_state is None
    assert reason == "fallback:unresolved"
    assert msg.answers == []
    assert session.current_state_id == runtime.entry_state_id


def test_history_empty_toast_text(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1405
    assert runtime.history_empty_toast_text(user_id) == "Вы не совершили ни одной сделки."


def test_main_menu_history_outputs_runtime_orders_when_present(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1403
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = runtime.entry_state_id
    session.history = [runtime.entry_state_id]

    quote_buy = QuoteRecord(
        state_id="qb",
        operation="buy",
        coin="BTC",
        coin_amount=0.0015,
        rub_amount=9000.0,
        net_amount=None,
    )
    runtime.orders.create_order(
        user_id=user_id,
        operation="buy",
        coin="BTC",
        input_amount=9000.0,
        quote=quote_buy,
        payment_method="📱СБП",
        wallet_or_requisites="bc1qqqq",
    )

    quote_sell = QuoteRecord(
        state_id="qs",
        operation="sell",
        coin="USDT",
        coin_amount=120.0,
        rub_amount=11640.0,
        net_amount=None,
    )
    runtime.orders.create_order(
        user_id=user_id,
        operation="sell",
        coin="USDT",
        input_amount=120.0,
        quote=quote_sell,
        payment_method="📱СБП",
        wallet_or_requisites="79000000000",
    )

    msg = DummyMessage()
    asyncio.run(runtime.handle_action(msg, user_id, "История сделок", is_text_input=False))

    assert msg.answers
    text = msg.answers[-1][0]
    assert "📚 История сделок" in text
    assert "Покупка BTC: 0.0015 | 9000 ₽" in text
    assert "Продажа USDT: 120 | 11640 ₽" in text
    assert session.current_state_id == runtime.entry_state_id


def test_main_menu_lottery_follows_flow_transition(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1404
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = runtime.entry_state_id
    session.history = [runtime.entry_state_id]
    sent_states: list[str] = []

    async def fake_send_state(_msg: object, _session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)

    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    msg = DummyMessage()
    asyncio.run(runtime.handle_action(msg, user_id, "🤑Большой розыгрыш🤑", is_text_input=False))

    next_state, reason = runtime.transition_engine.resolve_next(
        runtime.entry_state_id,
        action_text="🤑Большой розыгрыш🤑",
        is_text_input=False,
        session_history=[runtime.entry_state_id],
    )
    assert reason.startswith("action:")
    assert next_state is not None
    assert sent_states == [next_state]
    assert msg.answers == []
    assert session.current_state_id == runtime.entry_state_id


def test_calculator_button_shows_live_rate_and_does_not_replay_state(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1501
    prompt_state = runtime.replay_calc.prompt_states["buy"]["LTC"]
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = prompt_state
    session.history = [runtime.entry_state_id, prompt_state]
    session.pending_operation = "buy"
    session.pending_coin = "LTC"

    msg = DummyMessage()
    sent_states: list[str] = []

    async def fake_rates(*, force: bool = False) -> dict[str, float]:
        _ = force
        return {"ltc": 4000.0}

    async def fake_send_state(_msg: object, _session: object, state_id: str, **_kwargs: object) -> None:
        sent_states.append(state_id)

    runtime._current_rates = fake_rates  # type: ignore[method-assign]
    runtime._send_state = fake_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(msg, user_id, "Калькулятор", is_text_input=False))

    assert sent_states == []
    assert msg.answers
    text = msg.answers[-1][0]
    assert "Калькулятор Litecoin" in text
    assert "1 LTC = 4000 ₽" in text
    assert session.current_state_id == prompt_state


def test_back_to_quote_uses_last_runtime_quote_values(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1502
    quote_state = next(sid for sid, state in runtime.states.items() if state.get("kind") == "quote")
    payment_state = next(sid for sid, state in runtime.states.items() if state.get("kind") == "payment_method_select")
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = payment_state
    session.history = [runtime.entry_state_id, quote_state, payment_state]
    session.pending_operation = "buy"
    session.pending_coin = "LTC"
    session.last_quote_state_id = quote_state
    session.last_quote_coin_amount = 2.26636314
    session.last_quote_rub_amount = 9000.0
    session.last_quote_net_amount = 6300.0

    captured_overrides: list[str] = []

    async def fake_renderer_send_state(_msg: object, _state: object, **kwargs: object) -> None:
        text_plain = kwargs.get("text_override_plain")
        if isinstance(text_plain, str):
            captured_overrides.append(text_plain)

    runtime.renderer.send_state = fake_renderer_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "Назад", is_text_input=False))

    assert captured_overrides
    rendered = captured_overrides[-1]
    assert "Сумма к оплате: 9000 ₽" in rendered
    assert "Сумма к получению: 2.26636314 Litecoin" in rendered
    assert "2550" not in rendered
    assert session.current_state_id == quote_state


@pytest.mark.parametrize(
    ("operation", "coin", "coin_amount", "rub_amount", "net_amount", "expected_lines"),
    [
        ("buy", "BTC", 0.0015, 9000.0, 8700.0, ("Сумма к получению: 0.0015 Bitcoin", "Сумма к оплате: 9000 ₽")),
        ("buy", "USDT", 120.0, 11760.0, 11466.0, ("Сумма к получению: 120 USDT(trc20)", "Сумма к оплате: 11760 ₽")),
        ("sell", "XMR", 0.2, 4800.0, None, ("Сумма к получению: 4800 ₽", "Сумма к оплате: 0.2 xmr")),
        ("sell", "LTC", 1.25, 11250.0, None, ("Сумма к получению: 11250 ₽", "Сумма к оплате: 1.25 ltc")),
    ],
)
def test_back_to_quote_uses_runtime_values_for_multiple_coins(
    tmp_path: Path,
    operation: str,
    coin: str,
    coin_amount: float,
    rub_amount: float,
    net_amount: float | None,
    expected_lines: tuple[str, str],
) -> None:
    runtime = _runtime(tmp_path)
    user_id = 1510 + hash((operation, coin)) % 1000
    quote_state = next(sid for sid, state in runtime.states.items() if state.get("kind") == "quote")
    payment_state = next(sid for sid, state in runtime.states.items() if state.get("kind") == "payment_method_select")
    session = runtime.sessions.get_or_create(user_id, runtime.entry_state_id)
    session.current_state_id = payment_state
    session.history = [runtime.entry_state_id, quote_state, payment_state]
    session.pending_operation = operation
    session.pending_coin = coin
    session.last_quote_state_id = quote_state
    session.last_quote_coin_amount = coin_amount
    session.last_quote_rub_amount = rub_amount
    session.last_quote_net_amount = net_amount

    captured_overrides: list[str] = []

    async def fake_renderer_send_state(_msg: object, _state: object, **kwargs: object) -> None:
        text_plain = kwargs.get("text_override_plain")
        if isinstance(text_plain, str):
            captured_overrides.append(text_plain)

    runtime.renderer.send_state = fake_renderer_send_state  # type: ignore[method-assign]
    asyncio.run(runtime.handle_action(DummyMessage(), user_id, "Назад", is_text_input=False))

    assert captured_overrides
    rendered = captured_overrides[-1]
    assert expected_lines[0] in rendered
    assert expected_lines[1] in rendered
    assert "2550" not in rendered
    assert session.current_state_id == quote_state
