import json
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import server as srv

@pytest.fixture
def env_setup(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "custom_admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "custom_pass123")
    monkeypatch.setenv("SECURE_COOKIES", "true")

@pytest.fixture
def client_env(env_setup, tmp_path, monkeypatch):
    # Isolate data dir
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(srv, "DATA_DIR", data_dir)
    monkeypatch.setattr(srv, "CONFIG_PATH", data_dir / "site-config.json")
    srv.SESSIONS.clear()
    
    # We must RE-IMPORT or re-initialize variables in server if they are module-level
    # Since they are module level, we monkeypatch them directly for the test
    monkeypatch.setattr(srv, "ADMIN_USERNAME", "custom_admin")
    monkeypatch.setattr(srv, "ADMIN_PASSWORD", "custom_pass123")
    monkeypatch.setattr(srv, "SECURE_COOKIES", True)
    
    app = srv.create_app()
    return TestClient(app)

def test_custom_admin_credentials(client_env):
    # Old admin:admin should fail
    resp = client_env.post("/api/admin/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 401
    
    # New custom credentials should work
    resp = client_env.post("/api/admin/login", json={"username": "custom_admin", "password": "custom_pass123"})
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True
    
    # Check secure cookie flag - in TestClient we can check the cookie jar
    # resp.cookies is a RequestsCookieJar or similar
    # We can check for the cookie and its attributes
    found = False
    for cookie in resp.cookies.jar:
        if cookie.name == srv.SESSION_COOKIE_NAME:
            assert cookie.secure is True
            found = True
    assert found, f"Cookie {srv.SESSION_COOKIE_NAME} not found"

def test_no_soft_404(client_env):
    # Accessing unknown page in /ru/ should return 404, not index.html
    resp = client_env.get("/ru/non-existent-page-123")
    assert resp.status_code == 404
    assert "Page Not Found" in resp.text

def test_asset_absolute_paths(client_env):
    # Default config should have absolute path for QR
    resp = client_env.get("/api/site-config")
    assert resp.status_code == 200
    assert resp.json()["qrImageSrc"] == "/assets/payment_qr.png"

def test_serve_lang_page_valid(client_env, tmp_path, monkeypatch):
    # Setup mock src directory
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "index.html").write_text("root index")
    ru_dir = src_dir / "ru"
    ru_dir.mkdir()
    (ru_dir / "index.html").write_text("ru index")
    
    monkeypatch.setattr(srv, "SRC_DIR", src_dir)
    
    # Test /ru/ (empty slug)
    resp = client_env.get("/ru/")
    assert resp.status_code == 200
    assert resp.text == "ru index"
    
    # Test root via lang (if ru/index doesn't exist, should fallback to root)
    (ru_dir / "index.html").unlink()
    resp = client_env.get("/ru/")
    assert resp.status_code == 200
    assert resp.text == "root index"
