from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.config import Settings, load_settings
from app.order_engine import OrderEngine
from app.session_store import SessionStore
from main import CloneRuntime

pytestmark = pytest.mark.unit


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


def _operator_url(runtime: CloneRuntime) -> str | None:
    for state in runtime.states.values():
        rows = state.get("button_rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, list):
                continue
            for btn in row:
                if not isinstance(btn, dict):
                    continue
                if str(btn.get("type") or "") != "KeyboardButtonUrl":
                    continue
                if "оператор" not in str(btn.get("text") or "").lower():
                    continue
                return str(btn.get("url") or "")
    return None


def test_load_settings_ignores_invalid_numeric_env_values(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "BOT_TOKEN=test-token",
                "HOT_RELOAD_INTERVAL_SECONDS=abc",
                "SESSION_HISTORY_LIMIT=oops",
                "ORDER_TTL_SECONDS=nope",
                "DEFAULT_COMMISSION_PERCENT=bad",
                "RATE_CACHE_TTL_SECONDS=none",
                "SEARCH_DELAY_SECONDS=nan",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    settings = load_settings(tmp_path)

    assert settings.hot_reload_interval_seconds == pytest.approx(1.0)
    assert settings.session_history_limit == 30
    assert settings.order_ttl_seconds == 900
    assert settings.default_commission_percent == pytest.approx(2.5)
    assert settings.rate_cache_ttl_seconds == 45
    assert settings.search_delay_seconds == 15


def test_session_store_recovers_from_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "runtime_sessions.json"
    path.write_text("{broken", encoding="utf-8")

    store = SessionStore(path, history_limit=30)

    assert store.get_or_create(1, "entry").current_state_id == "entry"
    assert json.loads(path.read_text(encoding="utf-8")) == {"sessions": []}


def test_order_engine_recovers_from_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "runtime_orders.json"
    path.write_text("{broken", encoding="utf-8")

    engine = OrderEngine(path, ttl_seconds=900)

    assert engine.by_id("missing") is None
    assert json.loads(path.read_text(encoding="utf-8")) == {"orders": []}


def test_order_engine_expire_overdue_tolerates_invalid_expiry(tmp_path: Path) -> None:
    path = tmp_path / "runtime_orders.json"
    payload = {
        "orders": [
            {
                "order_id": "1",
                "user_id": 1,
                "operation": "buy",
                "coin": "BTC",
                "input_amount": 1.0,
                "output_amount": 1.0,
                "pay_amount": 1.0,
                "net_amount": None,
                "payment_method": "СБП",
                "wallet_or_requisites": "x",
                "status": "created",
                "created_at": "2024-01-01T00:00:00+00:00",
                "expires_at": "bad-date",
                "updated_at": "2024-01-01T00:00:00+00:00",
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    engine = OrderEngine(path, ttl_seconds=900)

    engine.expire_overdue()

    order = engine.by_id("1")
    assert order is not None
    assert order.status == "expired"


def test_runtime_repairs_invalid_session_state_in_handle_action(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    sessions_path = tmp_path / "runtime_sessions.json"
    sessions_path.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "user_id": 42,
                        "current_state_id": "bad_state",
                        "history": ["bad_state"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    runtime = CloneRuntime(_settings(project_dir, tmp_path))
    msg = DummyMessage()

    asyncio.run(runtime.handle_action(msg, 42, "hello", is_text_input=True))

    session = runtime.sessions.get_or_create(42, runtime.entry_state_id)
    assert session.current_state_id in runtime.states
    assert session.history
    assert all(state_id in runtime.states for state_id in session.history)


def test_runtime_link_update_hook_applies_links_without_restart(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    runtime = CloneRuntime(_settings(project_dir, tmp_path))
    new_operator = "https://example.com/new-operator"

    runtime.admin_settings.set_link("operator", new_operator)
    runtime.admin_ctx.notify_links_updated()

    assert _operator_url(runtime) == new_operator
