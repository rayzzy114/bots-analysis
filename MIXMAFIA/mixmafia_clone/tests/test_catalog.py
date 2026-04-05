"""Tests: FlowCatalog — address input detection and routing."""
from __future__ import annotations

from pathlib import Path

import pytest
from app.catalog import FlowCatalog


@pytest.fixture(scope="module")
def catalog() -> FlowCatalog:
    project_dir = Path(__file__).parents[1]
    return FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )


class TestAddressInputStates:
    def test_six_address_input_states_detected(self, catalog: FlowCatalog):
        addr_states = [sid for sid in catalog.states if catalog.is_address_input_state(sid)]
        assert len(addr_states) == 6

    def test_address_input_states_have_no_buttons(self, catalog: FlowCatalog):
        for sid in catalog.states:
            if catalog.is_address_input_state(sid):
                state = catalog.states[sid]
                assert not state.get("buttons"), f"Address state {sid} should have no buttons"
                assert not state.get("button_rows"), f"Address state {sid} should have no button_rows"

    def test_address_input_states_contain_vvedite_adres(self, catalog: FlowCatalog):
        for sid in catalog.states:
            if catalog.is_address_input_state(sid):
                text = catalog.states[sid].get("text", "")
                assert "Введите адрес" in text

    def test_get_address_input_next_returns_target(self, catalog: FlowCatalog):
        for sid in catalog.states:
            if catalog.is_address_input_state(sid):
                nxt = catalog.get_address_input_next(sid)
                assert nxt is not None, f"Address state {sid} has no next state"
                assert nxt in catalog.states, f"Target {nxt} not in states"

    def test_non_address_states_not_detected(self, catalog: FlowCatalog):
        start = catalog.start_state_id
        assert not catalog.is_address_input_state(start)
        if catalog.partner_state_id:
            assert not catalog.is_address_input_state(catalog.partner_state_id)

    def test_start_state_exists(self, catalog: FlowCatalog):
        assert catalog.start_state_id in catalog.states

    def test_welcome_state_exists(self, catalog: FlowCatalog):
        assert "4fdfa881597ed3208ee0144e67604ef9" in catalog.states


class TestGlobalRoutes:
    def test_receive_currency_routes_btc(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.receive_currency_state_id, "Чистые BTC")
        assert catalog.states[target]["text"].startswith("Введите адрес")
        assert "Вы выбрали получить: Чистые BTC" in catalog.states[target]["text"]

    def test_receive_currency_routes_eth(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.receive_currency_state_id, "Ethereum")
        assert catalog.states[target]["text"].startswith("Введите адрес")
        assert "Вы выбрали получить: Ethereum" in catalog.states[target]["text"]

    def test_receive_currency_routes_usdt_erc20(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.receive_currency_state_id, "Tether ERC-20")
        assert catalog.states[target]["text"].startswith("Введите адрес")
        assert "Вы выбрали получить: Tether ERC-20" in catalog.states[target]["text"]

    def test_receive_currency_routes_usdt_trc20(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.receive_currency_state_id, "Tether TRC-20")
        assert catalog.states[target]["text"].startswith("Введите адрес")
        assert "Вы выбрали получить: Tether TRC-20" in catalog.states[target]["text"]

    def test_receive_currency_routes_litecoin(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.receive_currency_state_id, "Litecoin")
        assert catalog.states[target]["text"].startswith("Введите адрес")
        assert "Вы выбрали получить: Litecoin" in catalog.states[target]["text"]

    def test_receive_currency_routes_monero(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.receive_currency_state_id, "Monero")
        assert catalog.states[target]["text"].startswith("Введите адрес")
        assert "Вы выбрали получить: Monero" in catalog.states[target]["text"]

    def test_clean_btc_available_from_order_state(self, catalog: FlowCatalog):
        target = catalog.resolve_action("317e051f4bc939ec52fca9a311c17f56", "🧹 Чистка BTC")
        assert target == catalog.receive_currency_state_id

    def test_partner_available_from_order_state(self, catalog: FlowCatalog):
        target = catalog.resolve_action("317e051f4bc939ec52fca9a311c17f56", "💵 Партнерам")
        assert target == catalog.partner_state_id

    def test_exchange_available_from_order_state(self, catalog: FlowCatalog):
        target = catalog.resolve_action("317e051f4bc939ec52fca9a311c17f56", "💼 Обмен")
        assert target == catalog.exchange_info_state_id

    def test_about_available_from_order_state(self, catalog: FlowCatalog):
        target = catalog.resolve_action("317e051f4bc939ec52fca9a311c17f56", "🎩 О нас")
        assert target == catalog.about_state_id

    def test_tariffs_button_has_explicit_route(self, catalog: FlowCatalog):
        target = catalog.resolve_action(catalog.about_state_id, "Тарифы")
        assert target == catalog.tariffs_state_id

    def test_back_from_reviews_returns_to_about(self, catalog: FlowCatalog):
        target = catalog.resolve_action(
            catalog.reviews_state_id,
            "Назад",
            history=[catalog.about_state_id, catalog.reviews_state_id],
        )
        assert target == catalog.about_state_id
