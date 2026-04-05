"""Tests for MM5 mixer site FastAPI server."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Patch paths before importing server so it uses a temp directory
import server as srv


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Each test gets its own data directory so tests don't interfere."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    config_path = data_dir / "site-config.json"
    monkeypatch.setattr(srv, "DATA_DIR", data_dir)
    monkeypatch.setattr(srv, "CONFIG_PATH", config_path)
    # Reset sessions between tests
    srv.SESSIONS.clear()
    # Write default config
    config_path.write_text(json.dumps(srv.DEFAULT_CONFIG, indent=2))
    yield


@pytest.fixture
def client():
    app = srv.create_app()
    return TestClient(app)


@pytest.fixture
def auth_client(client: TestClient):
    """Client that is already logged in."""
    resp = client.post("/api/admin/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    return client


# ── Health ──────────────────────────────────────────────

def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── Auth ────────────────────────────────────────────────

def test_login_success(client: TestClient):
    resp = client.post("/api/admin/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    assert srv.SESSION_COOKIE_NAME in resp.cookies


def test_login_wrong_password(client: TestClient):
    resp = client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_login_wrong_username(client: TestClient):
    resp = client.post("/api/admin/login", json={"username": "hacker", "password": "admin"})
    assert resp.status_code == 401


def test_admin_me_not_logged_in(client: TestClient):
    resp = client.get("/api/admin/me")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False


def test_admin_me_logged_in(auth_client: TestClient):
    resp = auth_client.get("/api/admin/me")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True


def test_logout(auth_client: TestClient):
    resp = auth_client.post("/api/admin/logout")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False
    # After logout, /me should be false
    resp2 = auth_client.get("/api/admin/me")
    assert resp2.json()["authenticated"] is False


# ── Config GET ──────────────────────────────────────────

def test_get_config_returns_defaults(client: TestClient):
    resp = client.get("/api/site-config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["feePercent"] == 4.5
    assert data["feeFixedBtc"] == 0.0007
    assert data["depositAddress"] == "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7"
    assert data["telegramBotUrl"] == "https://tele.click/mm5btc_bot"
    assert data["telegramChannelUrl"] == "https://t.me/kitchen_crypto"
    assert data["onionDomain"] == "mixermo4pgkgep3k3qr4fz7dhijavxnh6lwgu7gf5qeltpy4unjed2yd.onion"


def test_get_config_no_auth_needed(client: TestClient):
    """Public endpoint — no login required."""
    resp = client.get("/api/site-config")
    assert resp.status_code == 200


# ── Config POST (update) ───────────────────────────────

def test_update_config_requires_auth(client: TestClient):
    resp = client.post("/api/site-config", json={"feePercent": 10})
    assert resp.status_code == 401


def test_update_deposit_address(auth_client: TestClient):
    resp = auth_client.post("/api/site-config", json={"depositAddress": "bc1qNEWADDRESS"})
    assert resp.status_code == 200
    assert resp.json()["depositAddress"] == "bc1qNEWADDRESS"
    # Verify persistence
    resp2 = auth_client.get("/api/site-config")
    assert resp2.json()["depositAddress"] == "bc1qNEWADDRESS"


def test_update_telegram_bot_url(auth_client: TestClient):
    resp = auth_client.post("/api/site-config", json={"telegramBotUrl": "https://t.me/new_bot"})
    assert resp.status_code == 200
    assert resp.json()["telegramBotUrl"] == "https://t.me/new_bot"


def test_update_telegram_channel_url(auth_client: TestClient):
    resp = auth_client.post("/api/site-config", json={"telegramChannelUrl": "https://t.me/new_chan"})
    assert resp.status_code == 200
    assert resp.json()["telegramChannelUrl"] == "https://t.me/new_chan"


def test_update_onion_domain(auth_client: TestClient):
    new_onion = "abc123def456.onion"
    resp = auth_client.post("/api/site-config", json={"onionDomain": new_onion})
    assert resp.status_code == 200
    assert resp.json()["onionDomain"] == new_onion


def test_update_fee(auth_client: TestClient):
    resp = auth_client.post("/api/site-config", json={"feePercent": 7.5, "feeFixedBtc": 0.001})
    assert resp.status_code == 200
    assert resp.json()["feePercent"] == 7.5
    assert resp.json()["feeFixedBtc"] == 0.001


def test_update_multiple_fields(auth_client: TestClient):
    payload = {
        "feePercent": 3,
        "depositAddress": "bc1qMulti",
        "telegramBotUrl": "https://t.me/multi_bot",
        "onionDomain": "multi.onion",
    }
    resp = auth_client.post("/api/site-config", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["feePercent"] == 3
    assert data["depositAddress"] == "bc1qMulti"
    assert data["telegramBotUrl"] == "https://t.me/multi_bot"
    assert data["onionDomain"] == "multi.onion"
    # Fields not sent should keep old values
    assert data["telegramChannelUrl"] == "https://t.me/kitchen_crypto"


def test_update_ignores_empty_strings(auth_client: TestClient):
    """Empty string values should not overwrite existing config."""
    resp = auth_client.post("/api/site-config", json={"depositAddress": "  "})
    assert resp.status_code == 200
    # Should keep the default, not blank
    assert resp.json()["depositAddress"] == "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7"


def test_negative_fee_clamped_to_zero(auth_client: TestClient):
    resp = auth_client.post("/api/site-config", json={"feePercent": -5})
    assert resp.status_code == 200
    assert resp.json()["feePercent"] == 0


# ── Config Reset ────────────────────────────────────────

def test_reset_requires_auth(client: TestClient):
    resp = client.post("/api/site-config/reset", json={})
    assert resp.status_code == 401


def test_reset_restores_defaults(auth_client: TestClient):
    # First change something
    auth_client.post("/api/site-config", json={
        "depositAddress": "bc1qCHANGED",
        "telegramBotUrl": "https://t.me/changed",
        "onionDomain": "changed.onion",
    })
    # Now reset
    resp = auth_client.post("/api/site-config/reset", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["depositAddress"] == srv.DEFAULT_CONFIG["depositAddress"]
    assert data["telegramBotUrl"] == srv.DEFAULT_CONFIG["telegramBotUrl"]
    assert data["onionDomain"] == srv.DEFAULT_CONFIG["onionDomain"]
    assert data["feePercent"] == srv.DEFAULT_CONFIG["feePercent"]


# ── Static pages served ─────────────────────────────────

def test_index_html_served(client: TestClient):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Bitcoin mixer" in resp.text


def test_admin_html_served(client: TestClient):
    resp = client.get("/admin.html")
    assert resp.status_code == 200
    assert "Mixer Admin" in resp.text


# ── Language routes ────────────────────────────────────

def test_en_index_served(client: TestClient):
    resp = client.get("/en/")
    assert resp.status_code == 200
    assert "Bitcoin mixer" in resp.text.lower() or "Mix My Coins" in resp.text


def test_ru_index_served(client: TestClient):
    resp = client.get("/ru/")
    assert resp.status_code == 200
    assert "Биткоин" in resp.text or "миксер" in resp.text.lower()


def test_unknown_lang_returns_404(client: TestClient):
    resp = client.get("/xx/")
    assert resp.status_code == 404


# ── Language switch links are relative (no .onion) ─────

def test_en_index_lang_links_are_relative(client: TestClient):
    """Language switch links must NOT contain .onion domains."""
    resp = client.get("/en/")
    assert resp.status_code == 200
    # Should NOT have absolute onion URLs in navigation
    assert 'href="http://' not in resp.text or 'blog.mixer.money' in resp.text
    # Language list should use relative paths
    assert 'href="/ru/"' in resp.text
    assert 'href="/en/"' in resp.text


def test_ru_index_lang_links_are_relative(client: TestClient):
    resp = client.get("/ru/")
    assert resp.status_code == 200
    assert 'href="/ru/"' in resp.text
    assert 'href="/en/"' in resp.text


# ── Mixer result pages ─────────────────────────────────

def test_en_mixer_result_served(client: TestClient):
    resp = client.get("/en/mixer-result/")
    assert resp.status_code == 200
    assert "mixing" in resp.text.lower() or "submitted" in resp.text.lower()


def test_ru_mixer_result_served(client: TestClient):
    resp = client.get("/ru/mixer-result/")
    assert resp.status_code == 200
    assert "миксинг" in resp.text.lower() or "заявка" in resp.text.lower()


def test_en_mixer_result_with_address(client: TestClient):
    """Form submission sends forward_first_address as query param."""
    addr = "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"
    resp = client.get(f"/en/mixer-result/?forward_first_address={addr}")
    assert resp.status_code == 200
    # The JS reads from query params, but the HTML template has a default address
    # Just ensure the page loads with CSS reference
    assert "/assets/main.min.css" in resp.text


def test_ru_mixer_result_with_address(client: TestClient):
    addr = "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"
    resp = client.get(f"/ru/mixer-result/?forward_first_address={addr}")
    assert resp.status_code == 200
    assert "/assets/main.min.css" in resp.text


# ── Legacy slug routes (tochnyj-platezh, result-fa) ───

def test_en_tochnyj_platezh_serves_result(client: TestClient):
    resp = client.get("/en/tochnyj-platezh/")
    assert resp.status_code == 200


def test_en_result_fa_serves_result(client: TestClient):
    resp = client.get("/en/result-fa/")
    assert resp.status_code == 200


def test_ru_tochnyj_platezh_serves_result(client: TestClient):
    resp = client.get("/ru/tochnyj-platezh/")
    assert resp.status_code == 200


def test_ru_result_fa_serves_result(client: TestClient):
    resp = client.get("/ru/result-fa/")
    assert resp.status_code == 200


# ── Asset paths are root-absolute ──────────────────────

def test_en_index_css_path_is_absolute(client: TestClient):
    resp = client.get("/en/")
    assert resp.status_code == 200
    assert 'href="/assets/main.min.css"' in resp.text


def test_ru_index_css_path_is_absolute(client: TestClient):
    resp = client.get("/ru/")
    assert resp.status_code == 200
    assert 'href="/assets/main.min.css"' in resp.text


def test_en_result_css_path_is_absolute(client: TestClient):
    resp = client.get("/en/mixer-result/")
    assert resp.status_code == 200
    assert 'href="/assets/main.min.css"' in resp.text


def test_ru_result_css_path_is_absolute(client: TestClient):
    resp = client.get("/ru/mixer-result/")
    assert resp.status_code == 200
    assert 'href="/assets/main.min.css"' in resp.text


def test_site_config_js_path_is_absolute(client: TestClient):
    resp = client.get("/en/")
    assert resp.status_code == 200
    assert 'src="/site-config.js"' in resp.text


def test_ru_site_config_js_path_is_absolute(client: TestClient):
    resp = client.get("/ru/")
    assert resp.status_code == 200
    assert 'src="/site-config.js"' in resp.text


# ── Static assets accessible from root ─────────────────

def test_main_css_accessible(client: TestClient):
    resp = client.get("/assets/main.min.css")
    assert resp.status_code == 200


def test_site_config_js_accessible(client: TestClient):
    resp = client.get("/site-config.js")
    assert resp.status_code == 200
    assert "MixerSiteConfig" in resp.text


def test_logo_accessible(client: TestClient):
    resp = client.get("/assets/logo.png")
    assert resp.status_code == 200


# ── Forms use GET method ───────────────────────────────

def test_en_forms_use_get(client: TestClient):
    resp = client.get("/en/")
    assert resp.status_code == 200
    # All 3 forms should use GET
    assert 'action="/en/mixer-result/" class="refund-form" method="get"' in resp.text
    # No POST forms for mixing
    assert 'class="refund-form" method="post"' not in resp.text


def test_ru_forms_use_get(client: TestClient):
    resp = client.get("/ru/")
    assert resp.status_code == 200
    assert 'action="/ru/mixer-result/" class="refund-form" method="get"' in resp.text
    assert 'class="refund-form" method="post"' not in resp.text


# ── No .onion in href attributes ───────────────────────

def test_no_onion_in_en_hrefs(client: TestClient):
    """No internal links should point to .onion addresses."""
    resp = client.get("/en/")
    text = resp.text
    # Filter out display text — only check href attributes
    import re
    hrefs = re.findall(r'href="([^"]*)"', text)
    for href in hrefs:
        assert ".onion" not in href, f"Found .onion in href: {href}"


def test_no_onion_in_ru_hrefs(client: TestClient):
    resp = client.get("/ru/")
    import re
    hrefs = re.findall(r'href="([^"]*)"', text := resp.text)
    for href in hrefs:
        assert ".onion" not in href, f"Found .onion in href: {href}"


def test_no_onion_in_en_result_hrefs(client: TestClient):
    resp = client.get("/en/mixer-result/")
    import re
    hrefs = re.findall(r'href="([^"]*)"', resp.text)
    for href in hrefs:
        assert ".onion" not in href, f"Found .onion in href: {href}"


def test_no_onion_in_ru_result_hrefs(client: TestClient):
    resp = client.get("/ru/mixer-result/")
    import re
    hrefs = re.findall(r'href="([^"]*)"', resp.text)
    for href in hrefs:
        assert ".onion" not in href, f"Found .onion in href: {href}"


# ── Admin panel fixes ──────────────────────────────────

def test_onion_domain_trailing_slash_stripped(auth_client: TestClient):
    """onionDomain with trailing slash must be cleaned."""
    resp = auth_client.post("/api/site-config", json={"onionDomain": "abc123.onion/"})
    assert resp.status_code == 200
    assert resp.json()["onionDomain"] == "abc123.onion"


def test_onion_domain_http_prefix_stripped(auth_client: TestClient):
    """onionDomain with http:// prefix must be cleaned."""
    resp = auth_client.post("/api/site-config", json={"onionDomain": "http://abc123.onion/"})
    assert resp.status_code == 200
    assert resp.json()["onionDomain"] == "abc123.onion"


def test_admin_html_uses_absolute_paths(client: TestClient):
    resp = client.get("/admin.html")
    assert resp.status_code == 200
    assert 'src="/site-config.js"' in resp.text
    assert 'src="/assets/payment_qr.png"' in resp.text or 'src="/assets/uploads/' in resp.text
    assert 'href="/en/"' in resp.text


def test_admin_telegram_inputs_not_url_type(client: TestClient):
    """Telegram inputs should be type=text, not type=url (avoids validation crash)."""
    resp = client.get("/admin.html")
    assert resp.status_code == 200
    assert 'id="telegram-bot-url" type="text"' in resp.text
    assert 'id="telegram-channel-url" type="text"' in resp.text


def test_upload_qr_requires_auth(client: TestClient):
    resp = client.post("/api/upload-qr")
    assert resp.status_code == 401


def test_upload_qr_rejects_non_image(auth_client: TestClient):
    resp = auth_client.post(
        "/api/upload-qr",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PNG" in resp.json()["detail"] or "allowed" in resp.json()["detail"]


def test_upload_qr_accepts_png(auth_client: TestClient, tmp_path: Path):
    # Minimal 1x1 PNG
    import base64
    png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    png_data = base64.b64decode(png_b64)

    resp = auth_client.post(
        "/api/upload-qr",
        files={"file": ("qr.png", png_data, "image/png")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "qrImageSrc" in data
    assert data["qrImageSrc"].startswith("/assets/uploads/")
    # Config should also be updated
    assert data["config"]["qrImageSrc"] == data["qrImageSrc"]
