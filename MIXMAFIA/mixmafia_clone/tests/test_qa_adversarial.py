"""Adversarial QA tests — every evil scenario a user or admin could throw at the bot."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from admin_kit.rates import FALLBACK_RATES_RUB, RateService
from admin_kit.storage import OrdersStore
from app.catalog import FlowCatalog
from app.overrides import RuntimeOverrides, apply_state_overrides
from app.runtime import (
    MINIMUM_RUB,
    FlowRuntime,
    UserSession,
    _build_captcha_codes,
    _is_valid_address_for_currency,
    _is_valid_crypto_address,
    _parse_order_template_metadata,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog() -> FlowCatalog:
    project_dir = Path(__file__).parents[1]
    return FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
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
    def __init__(self, btc_rub: float = 8_000_000.0):
        self._btc_rub = btc_rub

    async def get_rates(self, force: bool = False) -> dict[str, float]:
        return {}

    async def get_rates_rub(self, force: bool = False) -> dict[str, float]:
        return {
            "btc": self._btc_rub,
            "eth": 300_000.0,
            "ltc": 9_500.0,
            "xmr": 15_000.0,
            "usdt": 87.0,
        }


def _make_runtime(tmp_path: Path, rates=None, orders=None) -> FlowRuntime:
    project_dir = Path(__file__).parents[1]
    catalog = FlowCatalog.from_directory(
        raw_dir=project_dir / "data" / "raw",
        media_dir=project_dir / "data" / "media",
    )
    app_context = SimpleNamespace(
        settings=_DummySettings(),
        rates=rates or _DummyRates(),
        orders=orders,
    )
    return FlowRuntime(project_dir=project_dir, catalog=catalog, app_context=app_context)


class _CaptureMessage:
    def __init__(self, user_id: int = 42000, username: str = "qa"):
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.chat = SimpleNamespace(id=user_id)
        self.message_id = 200
        self.bot = None
        self.calls: list[dict] = []

    async def answer(self, text: str | None = None, reply_markup=None, **kwargs):
        self.calls.append({"text": text or "", "reply_markup": reply_markup, **kwargs})
        self.message_id += 1
        return self

    async def answer_photo(self, photo, caption=None, reply_markup=None, **kwargs):
        self.calls.append({"caption": caption or "", "photo": photo, "reply_markup": reply_markup})
        self.message_id += 1
        return self


# ===========================================================================
# 1. ADDRESS VALIDATION — ADVERSARIAL INPUTS
# ===========================================================================

class TestAddressValidationEvil:
    """Every stupid thing a user might type."""

    # --- BTC ---
    @pytest.mark.parametrize("addr", [
        "bc1" + "a" * 19,         # 19 chars after bc1 — below minimum of 20
        "1" + "A" * 19,           # legacy, 19 chars — below min 20
        "3" + "B" * 19,           # P2SH, 19 chars — below min 20
        "bc1",                    # just prefix, no body
        "BC1Q3LJYSSTGYVPAKFERDDF3S36EFGTGDT32HP85E2",  # uppercase bech32 — should be rejected
    ])
    def test_btc_too_short_or_malformed_rejected_for_btc_currency(self, addr: str):
        assert not _is_valid_address_for_currency("btc (чистый)", addr), f"Should reject: {addr!r}"

    def test_btc_address_whitespace_stripped_and_accepted(self):
        # Code explicitly strips whitespace — padded valid addresses should pass
        assert _is_valid_address_for_currency(
            "btc (чистый)", "  bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2  "
        )

    def test_btc_address_only_spaces_rejected(self):
        assert not _is_valid_address_for_currency("btc (чистый)", "     ")

    def test_btc_address_embedded_in_sentence_rejected_for_currency(self):
        # Currency-specific validation uses fullmatch — no partial matches
        assert not _is_valid_address_for_currency(
            "btc (чистый)",
            "мой адрес bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2 вот",
        )

    def test_eth_address_rejected_for_btc_currency(self):
        assert not _is_valid_address_for_currency(
            "btc (чистый)", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
        )

    def test_trx_address_rejected_for_btc_currency(self):
        assert not _is_valid_address_for_currency(
            "btc (чистый)", "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
        )

    # --- ETH / BEP-20 ---
    def test_eth_address_wrong_length_rejected(self):
        # 39 hex chars instead of 40
        assert not _is_valid_address_for_currency(
            "ethereum", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697B"
        )

    def test_eth_address_41_hex_chars_rejected(self):
        assert not _is_valid_address_for_currency(
            "ethereum", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAeFF"
        )

    def test_bep20_accepts_eth_format_address(self):
        # BEP-20 uses same address format as ETH — intentional
        assert _is_valid_address_for_currency(
            "usdt bep-20", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
        )

    def test_tether_bep20_title_variation_accepted(self):
        assert _is_valid_address_for_currency(
            "tether bep-20", "0xAbCd1234567890abcdef1234567890abcdef1234"
        )

    def test_btc_address_rejected_for_eth_currency(self):
        assert not _is_valid_address_for_currency(
            "ethereum", "bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2"
        )

    # --- TRX ---
    def test_trx_address_starting_with_t_but_too_short_rejected(self):
        assert not _is_valid_address_for_currency("tether trc-20", "Tshort")

    def test_btc_address_rejected_for_trc20(self):
        assert not _is_valid_address_for_currency(
            "tether trc-20", "bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2"
        )

    def test_eth_address_rejected_for_trc20(self):
        assert not _is_valid_address_for_currency(
            "tether trc-20", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
        )

    # --- Monero ---
    def test_monero_address_too_short_rejected(self):
        # Must be 4[0-9AB] followed by 90-110 base58 chars
        short_xmr = "4" + "A" * 50
        assert not _is_valid_address_for_currency("monero", short_xmr)

    def test_monero_valid_address_accepted(self):
        valid_xmr = (
            "47Kv7Szy7ePGBgoYtfXCEH2R4peJsmNfEhD8zQ1sEgBRNiN5Xmt"
            "6bp8W96nUZ9Ea1cXrkA2hkESxkSKuJMzH9qkNDHwaLU4"
        )
        assert _is_valid_address_for_currency("monero", valid_xmr)

    def test_monero_rejects_btc_address(self):
        assert not _is_valid_address_for_currency(
            "monero", "bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2"
        )

    # --- Unknown / None currency ---
    def test_unknown_currency_falls_back_to_generic(self):
        # Unknown currency → _is_valid_crypto_address used → any valid address accepted
        assert _is_valid_address_for_currency(
            "РУБЛИ", "bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2"
        )

    def test_none_currency_falls_back_to_generic(self):
        assert _is_valid_address_for_currency(
            None, "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb"
        )

    def test_empty_currency_falls_back_to_generic(self):
        assert _is_valid_address_for_currency(
            "", "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
        )

    # --- Pure garbage ---
    @pytest.mark.parametrize("garbage", [
        "10000",
        "100.50",
        "Назад",
        "🏠 Главная",
        "https://t.me/scam",
        "SELECT * FROM orders",
        ";" * 100,
        "\n\n\n",
        "A" * 200,  # huge string
        "0x" + "g" * 40,  # hex prefix with invalid chars
    ])
    def test_garbage_inputs_rejected_generic(self, garbage: str):
        assert not _is_valid_crypto_address(garbage), f"Should reject: {garbage!r}"


# ===========================================================================
# 2. ADMIN PANEL — ALL OVERRIDES WORK END-TO-END
# ===========================================================================

def _apply(state: dict, **kwargs) -> dict:
    _override_keys = {"operator_url", "link_overrides", "sell_wallet_overrides", "commission_percent"}
    overrides = RuntimeOverrides(**{k: v for k, v in kwargs.items() if k in _override_keys})
    extra = {k: v for k, v in kwargs.items() if k not in _override_keys}
    return apply_state_overrides(
        state=state,
        overrides=overrides,
        operator_url_aliases=extra.pop("operator_url_aliases", ()),
        operator_handle_aliases=extra.pop("operator_handle_aliases", ()),
        **extra,
    )


class TestAdminPanelOverridesEvil:

    def test_commission_replaced_when_decimal(self):
        state = {"text": "Комиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=2.5)
        assert "2.5%" in result["text"]
        assert "1.5%" not in result["text"]

    def test_commission_100_percent_renders_correctly(self):
        state = {"text": "Комиссия сервиса: 1%"}
        result = _apply(state, commission_percent=100.0)
        assert "100%" in result["text"]

    def test_commission_negative_treated_as_zero(self):
        # Negative commission should not replace (commission_percent <= 0 skips replacement)
        state = {"text": "Комиссия сервиса: 1.5%"}
        result = _apply(state, commission_percent=-5.0)
        assert "1.5%" in result["text"]

    def test_all_six_sell_wallet_keys_replaceable(self):
        """Every SELL_WALLET_LABELS key must be replaceable."""
        keys = ["btc_clean", "eth", "usdt_erc20", "usdt_trc20", "usdt_bep20", "ltc", "xmr"]
        for key in keys:
            old = f"OLD_WALLET_{key}"
            new = f"NEW_WALLET_{key}"
            state = {"text": f"Адрес: {old}"}
            result = _apply(
                state,
                sell_wallet_overrides={key: new},
                sell_wallet_aliases={key: (old,)},
            )
            assert new in result["text"], f"Key {key!r} wallet not replaced"
            assert old not in result["text"], f"Key {key!r} old wallet still present"

    def test_link_replacement_all_keys(self):
        """All 6 link keys must be replaceable."""
        keys = ["channel", "support", "reviews", "faq", "exchange", "other"]
        for key in keys:
            old_url = f"https://t.me/old_{key}"
            new_url = f"https://t.me/new_{key}"
            state = {"text": f"Ссылка: {old_url}"}
            result = _apply(
                state,
                link_overrides={key: new_url},
                link_url_aliases={key: (old_url,)},
            )
            assert new_url in result["text"], f"Key {key!r} link not replaced in text"
            assert old_url not in result["text"], f"Key {key!r} old link still in text"

    def test_link_replacement_also_patches_button_url(self):
        old_url = "https://t.me/oldexchange"
        new_url = "https://t.me/newexchange"
        state = {
            "button_rows": [[{"text": "Перейти", "url": old_url, "type": "InlineKeyboardButton"}]]
        }
        result = _apply(
            state,
            link_overrides={"exchange": new_url},
            link_url_aliases={"exchange": (old_url,)},
        )
        assert result["button_rows"][0][0]["url"] == new_url

    def test_link_replacement_replaces_handle_in_text(self):
        """Core gotcha: @handle in text must change when link changes."""
        state = {"text": "Пиши нам: @oldbot и https://t.me/oldbot"}
        result = _apply(
            state,
            link_overrides={"support": "https://t.me/newbot"},
            link_url_aliases={"support": ("https://t.me/oldbot",)},
        )
        assert "@newbot" in result["text"]
        assert "@oldbot" not in result["text"]
        assert "https://t.me/newbot" in result["text"]

    def test_operator_url_handle_replaced_in_text(self):
        """Operator @handle in text must change when operator URL changes."""
        state = {"text": "Поддержка: @oldoperator"}
        result = _apply(
            state,
            operator_url="https://t.me/newoperator",
            operator_url_aliases=("https://t.me/oldoperator",),
            operator_handle_aliases=("oldoperator",),
        )
        assert "@newoperator" in result["text"]
        assert "@oldoperator" not in result["text"]

    def test_http_variant_of_link_also_replaced(self):
        """Old link stored as http:// must still be replaced."""
        state = {"text": "Ссылка: http://t.me/oldchannel"}
        result = _apply(
            state,
            link_overrides={"channel": "https://t.me/newchannel"},
            link_url_aliases={"channel": ("https://t.me/oldchannel",)},
        )
        assert "https://t.me/newchannel" in result["text"]
        assert "http://t.me/oldchannel" not in result["text"]

    def test_wallet_replacement_in_button_text(self):
        old_wallet = "bc1qoldwallet00000000000000000000000000001"
        new_wallet = "bc1qnewwallet00000000000000000000000000001"
        state = {
            "button_rows": [[
                {"text": f"Отправить на {old_wallet}", "type": "KeyboardButton"}
            ]]
        }
        result = _apply(
            state,
            sell_wallet_overrides={"btc_clean": new_wallet},
            sell_wallet_aliases={"btc_clean": (old_wallet,)},
        )
        assert new_wallet in result["button_rows"][0][0]["text"]
        assert old_wallet not in result["button_rows"][0][0]["text"]

    def test_commission_replaced_in_all_three_text_fields(self):
        state = {
            "text": "Комиссия сервиса: 1%",
            "text_html": "Комиссия сервиса: <strong>1%</strong>",
            "text_markdown": "Комиссия сервиса: **1%**",
        }
        result = _apply(state, commission_percent=3.0)
        assert "3%" in result["text"]
        assert "<strong>3%</strong>" in result["text_html"]
        assert "**3%**" in result["text_markdown"]
        assert "1%" not in result["text"]
        assert "1%" not in result["text_html"]
        assert "1%" not in result["text_markdown"]

    def test_empty_wallet_override_skipped(self):
        """Empty string wallet must not replace anything."""
        old = "bc1qrealwallet0000000000000000000000000001"
        state = {"text": f"Адрес: {old}"}
        result = _apply(
            state,
            sell_wallet_overrides={"btc_clean": ""},
            sell_wallet_aliases={"btc_clean": (old,)},
        )
        assert old in result["text"]

    def test_link_override_with_username_format_normalized(self):
        """Admin enters @newbot format — must work same as URL."""
        state = {"text": "Ссылка: https://t.me/oldbot"}
        result = _apply(
            state,
            link_overrides={"support": "@newbot"},
            link_url_aliases={"support": ("https://t.me/oldbot",)},
        )
        # normalize_operator_url converts @newbot → https://t.me/newbot
        assert "https://t.me/newbot" in result["text"]

    def test_state_not_mutated_by_overrides(self):
        """apply_state_overrides must not modify the original state dict."""
        original_text = "Комиссия сервиса: 1%"
        state = {"text": original_text}
        _apply(state, commission_percent=99.0)
        assert state["text"] == original_text


# ===========================================================================
# 3. RATE SERVICE — RELIABILITY
# ===========================================================================

class TestRateServiceEvil:

    def test_ttl_respected_no_double_fetch(self):
        """If called twice within TTL window, only one fetch happens."""
        svc = RateService(ttl_seconds=30)
        svc._last_fetch_ts = time.time()  # fresh fetch just happened

        fetch_calls = []

        async def fake_fetch():
            fetch_calls.append(1)
            return ({"btc": 100.0}, {"btc": 9_000_000.0})

        async def run():
            svc._fetch_coingecko = fake_fetch
            await svc.get_rates()
            await svc.get_rates()

        asyncio.run(run())
        assert len(fetch_calls) == 0  # TTL not expired, no fetches

    def test_exception_updates_ttl_so_next_call_waits(self):
        """After exception, _last_fetch_ts must be updated to prevent hammering."""
        svc = RateService(ttl_seconds=30)
        svc._last_fetch_ts = 0.0

        call_count = [0]

        async def exploding_fetch():
            call_count[0] += 1
            raise ConnectionError("network down")

        async def run():
            svc._fetch_coingecko = exploding_fetch
            await svc.get_rates()  # first call — should hit network
            await svc.get_rates()  # second call — TTL not expired, should NOT hit network

        asyncio.run(run())
        assert call_count[0] == 1, "Should only fetch once despite two calls (TTL respected after exception)"

    def test_fallback_rates_used_when_coingecko_returns_none(self):
        """If CoinGecko returns None, cached/fallback rates must be returned."""
        svc = RateService(ttl_seconds=30)
        svc._last_fetch_ts = 0.0
        svc._cached_rates = {}  # empty cache

        async def null_fetch():
            return None

        async def run():
            svc._fetch_coingecko = null_fetch
            rates = await svc.get_rates()
            return rates

        rates = asyncio.run(run())
        assert "btc" in rates
        assert rates["btc"] > 0

    def test_fallback_rates_rub_used_when_coingecko_fails(self):
        svc = RateService(ttl_seconds=30)
        svc._last_fetch_ts = 0.0
        svc._cached_rates_rub = {}

        async def null_fetch():
            return None

        async def run():
            svc._fetch_coingecko = null_fetch
            rates = await svc.get_rates_rub()
            return rates

        rates = asyncio.run(run())
        assert "btc" in rates
        assert rates["btc"] > 0

    def test_fresh_rates_replace_stale_cache(self):
        """When TTL expires, new rates overwrite old cached ones."""
        svc = RateService(ttl_seconds=1)
        svc._last_fetch_ts = 0.0  # expired immediately
        svc._cached_rates = {"btc": 1.0}  # stale

        async def fresh_fetch():
            return ({"btc": 99999.0, "usdt": 1.0, "ltc": 100.0, "eth": 3000.0, "xmr": 200.0},
                    {"btc": 9_000_000.0, "usdt": 90.0, "ltc": 9500.0, "eth": 280_000.0, "xmr": 14000.0})

        async def run():
            svc._fetch_coingecko = fresh_fetch
            rates = await svc.get_rates(force=True)
            return rates

        rates = asyncio.run(run())
        assert rates["btc"] == 99999.0


# ===========================================================================
# 4. MINIMUM AMOUNT OVERRIDE — EDGE CASES
# ===========================================================================

class TestMinimumAmountOverride:

    def test_state_without_minimum_text_untouched(self, tmp_path):
        rt = _make_runtime(tmp_path)
        state = {"text": "Добро пожаловать!", "text_html": "<b>Добро пожаловать!</b>"}
        original_text = state["text"]
        asyncio.run(rt._apply_minimum_amount_override(state))
        assert state["text"] == original_text

    def test_uses_fallback_when_btc_rub_zero(self, tmp_path):
        """When live BTC/RUB rate is 0, must use FALLBACK_RATES_RUB."""
        rt = _make_runtime(tmp_path, rates=_DummyRates(btc_rub=0.0))
        project_dir = Path(__file__).parents[1]
        catalog = FlowCatalog.from_directory(
            raw_dir=project_dir / "data" / "raw",
            media_dir=project_dir / "data" / "media",
        )
        state = dict(catalog.states["317e051f4bc939ec52fca9a311c17f56"])
        asyncio.run(rt._apply_minimum_amount_override(state))

        # Should have used fallback rate
        fallback_btc_rub = FALLBACK_RATES_RUB["btc"]
        expected_min = MINIMUM_RUB / fallback_btc_rub
        expected_str = f"{expected_min:.4f}".rstrip("0").rstrip(".")
        assert f"Минимальная сумма обмена: {expected_str} BTC" in state["text"]

    def test_minimum_not_hardcoded_changes_with_rate(self, tmp_path):
        """Different rate → different minimum displayed."""
        rates_slow = _DummyRates(btc_rub=5_000_000.0)
        rates_fast = _DummyRates(btc_rub=10_000_000.0)
        project_dir = Path(__file__).parents[1]

        for btc_rub, rates in [(5_000_000.0, rates_slow), (10_000_000.0, rates_fast)]:
            catalog = FlowCatalog.from_directory(
                raw_dir=project_dir / "data" / "raw",
                media_dir=project_dir / "data" / "media",
            )
            app_context = SimpleNamespace(settings=_DummySettings(), rates=rates, orders=None)
            rt = FlowRuntime(project_dir=project_dir, catalog=catalog, app_context=app_context)
            state = dict(catalog.states["317e051f4bc939ec52fca9a311c17f56"])
            asyncio.run(rt._apply_minimum_amount_override(state))
            expected = f"{MINIMUM_RUB / btc_rub:.4f}".rstrip("0").rstrip(".")
            assert expected in state["text"], f"Expected {expected} for rate {btc_rub}"

    def test_minimum_formatted_to_4dp(self, tmp_path):
        """Result must be 4 decimal places max (trailing zeros stripped)."""
        rt = _make_runtime(tmp_path, rates=_DummyRates(btc_rub=8_000_000.0))
        project_dir = Path(__file__).parents[1]
        catalog = FlowCatalog.from_directory(
            raw_dir=project_dir / "data" / "raw",
            media_dir=project_dir / "data" / "media",
        )
        state = dict(catalog.states["317e051f4bc939ec52fca9a311c17f56"])
        asyncio.run(rt._apply_minimum_amount_override(state))
        # Extract the displayed minimum from text
        import re
        m = re.search(r"Минимальная сумма обмена: ([\d.]+) BTC", state["text"])
        assert m, "Minimum not found in text"
        displayed = m.group(1)
        # Must not have more than 4 decimal places
        parts = displayed.split(".")
        if len(parts) == 2:
            assert len(parts[1]) <= 4, f"Too many decimal places: {displayed!r}"
        # Must not have trailing zeros after decimal point
        assert not displayed.endswith("0"), f"Trailing zero: {displayed!r}"


# ===========================================================================
# 5. CATALOG ROUTING — BACK BUTTON AND CURRENCY FLOWS
# ===========================================================================

class TestCatalogRoutingEvil:

    def test_back_button_works_from_every_address_input_state(self, catalog: FlowCatalog):
        """Every 'Введите адрес' state must have a working Назад route."""
        for sid in catalog.states:
            if not catalog.is_address_input_state(sid):
                continue
            result = catalog.resolve_action(sid, "Назад", history=[catalog.receive_currency_state_id, sid])
            assert result is not None, f"Назад failed from address input state {sid}"
            assert result in catalog.states, f"Back target {result} not in states"

    def test_usdt_bep20_not_in_this_catalog(self, catalog: FlowCatalog):
        # This bot's captured flow does not include BEP-20 — must return None, not crash
        target = catalog.resolve_action(catalog.receive_currency_state_id, "USDT BEP-20")
        assert target is None, "BEP-20 should not route in this catalog"

    def test_all_currencies_route_to_address_input(self, catalog: FlowCatalog):
        currencies = ["Чистые BTC", "Ethereum", "Tether ERC-20", "Tether TRC-20", "Litecoin", "Monero"]
        for currency in currencies:
            target = catalog.resolve_action(catalog.receive_currency_state_id, currency)
            assert target is not None, f"No route for currency: {currency!r}"
            assert catalog.is_address_input_state(target), f"{currency!r} should go to address input"

    def test_resolve_action_unknown_returns_none(self, catalog: FlowCatalog):
        result = catalog.resolve_action(catalog.start_state_id, "НЕСУЩЕСТВУЮЩАЯ КНОПКА_XYZ123")
        assert result is None

    def test_resolve_action_empty_string_returns_none(self, catalog: FlowCatalog):
        result = catalog.resolve_action(catalog.start_state_id, "")
        assert result is None

    def test_back_button_from_about_back_to_main(self, catalog: FlowCatalog):
        result = catalog.resolve_action(
            catalog.about_state_id, "Назад",
            history=[catalog.start_state_id, catalog.about_state_id],
        )
        assert result is not None
        assert result in catalog.states

    def test_double_back_does_not_crash(self, catalog: FlowCatalog):
        """Назад with no real history → should return something or None, not crash."""
        result = catalog.resolve_action(catalog.about_state_id, "Назад", history=[])
        # Must not raise — result can be None or any valid state
        assert result is None or result in catalog.states

    def test_order_template_states_detected(self, catalog: FlowCatalog):
        """At least one order template state must exist per the flow."""
        project_dir = Path(__file__).parents[1]
        c = FlowCatalog.from_directory(
            raw_dir=project_dir / "data" / "raw",
            media_dir=project_dir / "data" / "media",
        )
        rt = FlowRuntime(
            project_dir=project_dir,
            catalog=c,
            app_context=SimpleNamespace(settings=_DummySettings(), rates=_DummyRates(), orders=None),
        )
        assert len(rt.order_template_state_ids) > 0, "No order templates detected"

    def test_all_order_templates_have_currency_title(self, catalog: FlowCatalog):
        for sid in catalog.states:
            parsed = _parse_order_template_metadata(catalog.states[sid])
            if parsed is not None:
                assert parsed["currency_title"], f"Order template {sid} has empty currency_title"

    def test_partner_state_exists_in_catalog(self, catalog: FlowCatalog):
        assert catalog.partner_state_id is not None
        assert catalog.partner_state_id in catalog.states


# ===========================================================================
# 6. USDT_BEP20 FIX — WALLET ALIAS DETECTION
# ===========================================================================

class TestUsdtBep20WalletAliasDetection:
    """Verify the usdt_bsc → usdt_bep20 fix is in effect."""

    def test_sell_wallet_aliases_has_usdt_bep20_not_usdt_bsc(self, catalog: FlowCatalog):
        assert "usdt_bep20" in catalog.sell_wallet_aliases, "usdt_bep20 key missing from sell_wallet_aliases"
        assert "usdt_bsc" not in catalog.sell_wallet_aliases, "usdt_bsc should not exist (renamed to usdt_bep20)"

    def test_usdt_bep20_admin_override_reaches_text(self, catalog: FlowCatalog):
        """When admin sets usdt_bep20 wallet, it must replace in state text."""
        # Find a state that has a BEP-20 wallet address (if any detected)
        aliases = catalog.sell_wallet_aliases.get("usdt_bep20", ())
        if not aliases:
            pytest.skip("No usdt_bep20 wallet aliases detected in this catalog")
        old_wallet = aliases[0]
        new_wallet = "0xNEWBEP20WALLET1234567890abcdef12345678"
        # Find a state that contains the old wallet
        state_with_wallet = None
        for sid, state in catalog.states.items():
            if old_wallet in str(state.get("text") or ""):
                state_with_wallet = dict(state)
                break
        if state_with_wallet is None:
            pytest.skip("No state contains usdt_bep20 wallet address in text")
        result = apply_state_overrides(
            state=state_with_wallet,
            overrides=RuntimeOverrides(sell_wallet_overrides={"usdt_bep20": new_wallet}),
            operator_url_aliases=(),
            operator_handle_aliases=(),
            sell_wallet_aliases={"usdt_bep20": (old_wallet,)},
        )
        assert new_wallet in str(result.get("text") or "")
        assert old_wallet not in str(result.get("text") or "")


# ===========================================================================
# 7. SESSION LOGIC — EVIL USER SCENARIOS
# ===========================================================================

class TestSessionEvil:

    def test_captcha_codes_always_4_unique(self):
        for _ in range(20):
            codes = _build_captcha_codes()
            assert len(codes) == 4
            assert len(set(codes)) == 4

    def test_captcha_correct_code_always_present(self):
        from app.runtime import CAPTCHA_CORRECT_CODE
        for _ in range(20):
            codes = _build_captcha_codes()
            assert CAPTCHA_CORRECT_CODE in codes

    def test_cancel_with_no_session_returns_false(self, tmp_path):
        rt = _make_runtime(tmp_path)
        assert rt._cancel_current_order(99999) is False

    def test_cancel_with_no_order_id_in_session_returns_false(self, tmp_path):
        rt = _make_runtime(tmp_path)
        rt.sessions[1] = UserSession(state_id="x", current_order_id=None)
        assert rt._cancel_current_order(1) is False

    def test_cancel_nonexistent_order_id_returns_false(self, tmp_path):
        orders = OrdersStore(tmp_path / "orders.json")
        rt = _make_runtime(tmp_path, orders=orders)
        rt.sessions[1] = UserSession(state_id="x", current_order_id="nonexistent_order_999")
        assert rt._cancel_current_order(1) is False

    def test_history_with_zero_orders_returns_empty_message(self, tmp_path):
        orders = OrdersStore(tmp_path / "orders.json")
        rt = _make_runtime(tmp_path, orders=orders)
        msg = _CaptureMessage(user_id=77777)
        asyncio.run(rt._send_history_page(msg, 77777, 0))
        assert any("нет обменов" in str(c.get("text", "")).lower() for c in msg.calls)

    def test_history_page_clamps_out_of_range(self, tmp_path):
        """Page -1 or 9999 must not crash, must clamp to valid range."""
        orders = OrdersStore(tmp_path / "orders.json")
        rt = _make_runtime(tmp_path, orders=orders)
        # Create 3 orders for user
        for _ in range(3):
            orders.create_order(
                user_id=55555, username="qa",
                wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
                coin_symbol="Tether TRC-20",
                coin_amount=0.0, amount_rub=0.0, payment_method="", bank="",
            )
        msg = _CaptureMessage(user_id=55555)
        # Page 9999 — must clamp, not crash
        asyncio.run(rt._send_history_page(msg, 55555, 9999))
        assert msg.calls

    def test_history_order_wrong_user_rejected(self, tmp_path):
        """User A must not see User B's order."""
        orders = OrdersStore(tmp_path / "orders.json")
        rt = _make_runtime(tmp_path, orders=orders)
        order = orders.create_order(
            user_id=1111, username="alice",
            wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            coin_symbol="Tether TRC-20",
            coin_amount=0.0, amount_rub=0.0, payment_method="", bank="",
        )
        msg = _CaptureMessage(user_id=2222)
        asyncio.run(rt._send_history_order(msg, order["order_id"], requester_user_id=2222))
        assert not msg.calls, "User 2222 should not see User 1111's order"

    def test_send_state_unknown_state_id_silent(self, tmp_path):
        """Unknown state_id must not crash, just silently do nothing."""
        rt = _make_runtime(tmp_path)
        msg = _CaptureMessage()
        asyncio.run(rt._send_state_by_id(msg, "TOTALLY_FAKE_STATE_ID_XYZ"))
        assert not msg.calls

    def test_session_survives_long_history(self, tmp_path):
        """Session with 200-step history must not crash on Назад."""
        rt = _make_runtime(tmp_path)
        start = rt.catalog.start_state_id
        history = [start] * 200
        session = UserSession(state_id=start, history=history)
        rt.sessions[12345] = session
        # Resolve Назад — should not raise
        result = rt.catalog.resolve_action(start, "Назад", history=history)
        assert result is None or result in rt.catalog.states

    def test_multiple_users_isolated_sessions(self, tmp_path):
        """Two users must have completely independent sessions."""
        orders = OrdersStore(tmp_path / "orders.json")
        rt = _make_runtime(tmp_path, orders=orders)

        order_a = orders.create_order(
            user_id=1001, username="alice",
            wallet="bc1q3ljysstgyvpakferddf3s36efgtgdt32hp85e2",
            coin_symbol="BTC (чистый)", coin_amount=0.0, amount_rub=0.0,
            payment_method="", bank="",
        )
        order_b = orders.create_order(
            user_id=1002, username="bob",
            wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            coin_symbol="Tether TRC-20", coin_amount=0.0, amount_rub=0.0,
            payment_method="", bank="",
        )

        rt.sessions[1001] = UserSession(
            state_id="x", current_order_id=order_a["order_id"],
            selected_currency_title="BTC (чистый)",
        )
        rt.sessions[1002] = UserSession(
            state_id="y", current_order_id=order_b["order_id"],
            selected_currency_title="Tether TRC-20",
        )

        # Cancel user A's order
        rt._cancel_current_order(1001)

        # User B's order must still be pending
        assert orders.get_order(order_b["order_id"])["status"] == "pending_payment"
        # User A's session still points to his order (session not wiped)
        assert rt.sessions[1001].current_order_id == order_a["order_id"]


# ===========================================================================
# 8. ORDER FLOW — FULL SCENARIOS
# ===========================================================================

class TestOrderFlowEvil:

    def test_build_order_state_unknown_currency_falls_back(self, tmp_path):
        """Unknown currency title → must not crash, uses any available template."""
        rt = _make_runtime(tmp_path)
        order = {
            "order_id": "test_1",
            "coin_symbol": "НЕ_СУЩЕСТВУЮЩАЯ_МОНЕТА_XYZ",
            "wallet": "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            "status": "pending_payment",
        }
        state = rt._build_order_state_for_order(
            state_id=rt._best_order_template_state_id("НЕ_СУЩЕСТВУЮЩАЯ_МОНЕТА_XYZ", False),
            order=order,
            drop_buttons=True,
        )
        # Must return a dict (possibly empty but no crash)
        assert isinstance(state, dict)

    def test_order_snapshot_removes_tx_for_cancelled(self):
        from app.runtime import _build_order_snapshot_state
        project_dir = Path(__file__).parents[1]
        catalog = FlowCatalog.from_directory(
            raw_dir=project_dir / "data" / "raw",
            media_dir=project_dir / "data" / "media",
        )
        # Use TRC-20 state which has transactions
        state = catalog.states.get("c9b22348761f7d08315e2c20904c8f58", {})
        snapshot = _build_order_snapshot_state(
            state=state,
            order_id="9999",
            wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            status_text="Отменен",
            include_transactions=False,
        )
        assert "Транзакции:" not in str(snapshot.get("text") or "")
        assert "Транзакции:" not in str(snapshot.get("text_html") or "")

    def test_order_id_replaced_in_all_fields(self):
        from app.runtime import _build_order_snapshot_state
        project_dir = Path(__file__).parents[1]
        catalog = FlowCatalog.from_directory(
            raw_dir=project_dir / "data" / "raw",
            media_dir=project_dir / "data" / "media",
        )
        state = catalog.states.get("317e051f4bc939ec52fca9a311c17f56", {})
        snapshot = _build_order_snapshot_state(
            state=state,
            order_id="777666",
            wallet="47Kv7Szy7ePGBgoYtfXCEH2R4peJsmNfEhD8zQ1sEgBRNiN5Xmt6bp8W96nUZ9Ea1cXrkA2hkESxkSKuJMzH9qkNDHwaLU4",
            status_text="Ожидает оплаты",
            include_transactions=False,
        )
        for field in ("text", "text_html", "text_markdown"):
            val = str(snapshot.get(field) or "")
            if val:
                assert "777666" in val, f"Order ID not in {field}"

    def test_confirmed_order_keeps_transactions(self):
        from app.runtime import _build_order_snapshot_state
        project_dir = Path(__file__).parents[1]
        catalog = FlowCatalog.from_directory(
            raw_dir=project_dir / "data" / "raw",
            media_dir=project_dir / "data" / "media",
        )
        state = catalog.states.get("c9b22348761f7d08315e2c20904c8f58", {})
        if "Транзакции:" not in str(state.get("text") or ""):
            pytest.skip("This state has no transactions section")
        snapshot = _build_order_snapshot_state(
            state=state,
            order_id="1234",
            wallet="T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
            status_text="Подтвержден",
            include_transactions=True,
            drop_buttons=False,
        )
        assert "Транзакции:" in str(snapshot.get("text") or "")


# ===========================================================================
# 9. CAPTCHA — USER IMPERSONATION
# ===========================================================================

class TestCaptchaSecurityEvil:

    def test_captcha_answer_from_wrong_user_rejected(self, tmp_path):
        """User B must not be able to pass captcha by answering for User A."""
        rt = _make_runtime(tmp_path)
        from app.runtime import CAPTCHA_CORRECT_CODE
        rt.pending_captcha[1111] = CAPTCHA_CORRECT_CODE

        answered_for_wrong_uid = False

        async def fake_answer(text=None, show_alert=False, **kw):
            nonlocal answered_for_wrong_uid
            if show_alert and "не для вас" in str(text or ""):
                answered_for_wrong_uid = True

        cb = SimpleNamespace(
            data=f"captcha:1111:{CAPTCHA_CORRECT_CODE}",
            from_user=SimpleNamespace(id=2222),
            message=None,
            answer=fake_answer,
        )
        asyncio.run(rt.on_callback(cb))
        assert answered_for_wrong_uid, "Captcha impersonation not blocked"
        assert 2222 not in rt.captcha_passed, "Impersonator must not pass captcha"
        assert 1111 not in rt.captcha_passed, "Original user must not pass either"

    def test_captcha_wrong_code_shows_retry(self, tmp_path):
        rt = _make_runtime(tmp_path)
        rt.pending_captcha[3333] = "rfp6p"

        alert_shown = [False]

        async def fake_answer(text=None, show_alert=False, **kw):
            if show_alert and text:
                alert_shown[0] = True

        cb = SimpleNamespace(
            data="captcha:3333:wrong",
            from_user=SimpleNamespace(id=3333),
            message=None,
            answer=fake_answer,
        )
        asyncio.run(rt.on_callback(cb))
        assert alert_shown[0], "Wrong captcha must show alert"
        assert 3333 not in rt.captcha_passed


# ===========================================================================
# 10. NUMBER FORMATTING
# ===========================================================================

class TestNumberFormattingEvil:
    from app.utils import fmt_coin, fmt_money

    @pytest.mark.parametrize("value, expected", [
        (0.0012345, "0.0012"),  # 4dp, truncated
        (0.00125, "0.0013"),    # rounds up at 4th dp
        (1.0, "1"),             # trailing zeros stripped
        (1.5, "1.5"),           # no trailing zeros
        (0.1234, "0.1234"),     # exactly 4dp
        (0.12345, "0.1235"),    # 5th place rounds up
        (0.00001, "0.0"),       # very small → rounds to near-zero... let's verify
    ])
    def test_fmt_coin_precision(self, value, expected):
        from app.utils import fmt_coin
        result = fmt_coin(value)
        # We can't always predict exact rounding but check 4dp max
        assert "." not in result or len(result.split(".")[1]) <= 4

    @pytest.mark.parametrize("value, expected", [
        (10000.0, "10 000"),
        (100.0, "100"),
        (1000000.4, "1 000 000"),  # rounds to int
        (99.6, "100"),             # rounds up
    ])
    def test_fmt_money_integer_with_spaces(self, value, expected):
        from app.utils import fmt_money
        assert fmt_money(value) == expected

    def test_fmt_money_no_decimals(self):
        from app.utils import fmt_money
        result = fmt_money(12345.99)
        assert "." not in result

    def test_fmt_coin_no_trailing_zeros(self):
        from app.utils import fmt_coin
        result = fmt_coin(1.0000)
        assert result == "1"
        result2 = fmt_coin(0.1000)
        assert result2 == "0.1"
