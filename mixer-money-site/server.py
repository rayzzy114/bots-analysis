from __future__ import annotations

import argparse
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Body, Cookie, Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_QR_SIZE = 2 * 1024 * 1024  # 2 MB

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
CONFIG_PATH = DATA_DIR / "site-config.json"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"
SESSION_COOKIE_NAME = "mm5_admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60

DEFAULT_CONFIG = {
    "feePercent": 4.5,
    "feeFixedBtc": 0.0007,
    "depositAddress": "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7",
    "qrImageSrc": "./assets/payment_qr.png",
    "telegramBotUrl": "https://tele.click/mm5btc_bot",
    "telegramChannelUrl": "https://t.me/kitchen_crypto",
    "onionDomain": "mixermo4pgkgep3k3qr4fz7dhijavxnh6lwgu7gf5qeltpy4unjed2yd.onion",
}

WRITE_LOCK = threading.Lock()
SESSION_LOCK = threading.Lock()
SESSIONS: dict[str, float] = {}


def sanitize_number(value: object, fallback: float) -> float:
    if not isinstance(value, (int, float, str)):
        return fallback
    try:
        number = float(value)
    except ValueError:
        return fallback
    return max(0.0, number)


def sanitize_config(raw: object) -> dict[str, object]:
    source: dict[str, Any] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(key, str):
                source[key] = value

    config = dict(DEFAULT_CONFIG)
    config["feePercent"] = sanitize_number(source.get("feePercent"), float(config["feePercent"]))
    config["feeFixedBtc"] = sanitize_number(source.get("feeFixedBtc"), float(config["feeFixedBtc"]))

    deposit_address = source.get("depositAddress")
    if isinstance(deposit_address, str) and deposit_address.strip():
        config["depositAddress"] = deposit_address.strip()

    qr_image_src = source.get("qrImageSrc")
    if isinstance(qr_image_src, str) and qr_image_src.strip():
        config["qrImageSrc"] = qr_image_src.strip()

    for key in ("telegramBotUrl", "telegramChannelUrl", "onionDomain"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            cleaned = value.strip()
            if key == "onionDomain":
                cleaned = cleaned.rstrip("/").removeprefix("http://").removeprefix("https://")
            config[key] = cleaned

    return config


def read_config() -> dict[str, object]:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    return sanitize_config(payload)


def write_config(config: dict[str, object]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe = sanitize_config(config)
    temp_path = CONFIG_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(CONFIG_PATH)


def ensure_config_exists() -> None:
    with WRITE_LOCK:
        if not CONFIG_PATH.exists():
            write_config(dict(DEFAULT_CONFIG))


def cleanup_sessions(now_ts: float | None = None) -> None:
    now = now_ts if now_ts is not None else time.time()
    expired = [token for token, exp in SESSIONS.items() if exp <= now]
    for token in expired:
        SESSIONS.pop(token, None)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with SESSION_LOCK:
        cleanup_sessions(time.time())
        SESSIONS[token] = time.time() + SESSION_TTL_SECONDS
    return token


def remove_session(token: str) -> None:
    with SESSION_LOCK:
        SESSIONS.pop(token, None)


def session_is_valid(token: str) -> bool:
    if not token:
        return False
    now = time.time()
    with SESSION_LOCK:
        cleanup_sessions(now)
        expires_at = SESSIONS.get(token)
        if expires_at is None:
            return False
        if expires_at <= now:
            SESSIONS.pop(token, None)
            return False
    return True


def require_admin(admin_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> None:
    token = (admin_session or "").strip()
    if not session_is_valid(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")


def create_app() -> FastAPI:
    if not SRC_DIR.exists():
        raise RuntimeError(f"Missing static source directory: {SRC_DIR}")

    ensure_config_exists()

    application = FastAPI(
        title="MM5 Mixer Site",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/admin/me")
    def admin_me(admin_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> dict[str, bool]:
        return {"authenticated": session_is_valid((admin_session or "").strip())}

    @application.post("/api/admin/login")
    def admin_login(payload: dict[str, Any] = Body(...)) -> JSONResponse:
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", ""))
        if username != ADMIN_USERNAME or password != ADMIN_PASSWORD:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login or password.")

        token = create_session()
        response = JSONResponse({"authenticated": True})
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=SESSION_TTL_SECONDS,
            path="/",
        )
        return response

    @application.post("/api/admin/logout")
    def admin_logout(admin_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME)) -> JSONResponse:
        token = (admin_session or "").strip()
        if token:
            remove_session(token)
        response = JSONResponse({"authenticated": False})
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return response

    @application.get("/api/site-config")
    def get_site_config() -> JSONResponse:
        return JSONResponse(read_config())

    @application.post("/api/site-config")
    def update_site_config(
        payload: dict[str, Any] = Body(...),
        _auth: None = Depends(require_admin),
    ) -> JSONResponse:
        with WRITE_LOCK:
            current = read_config()
            merged = {**current, **payload}
            write_config(merged)
            updated = read_config()
        return JSONResponse(updated)

    @application.post("/api/site-config/reset")
    def reset_site_config(_auth: None = Depends(require_admin)) -> JSONResponse:
        with WRITE_LOCK:
            write_config(dict(DEFAULT_CONFIG))
            updated = read_config()
        return JSONResponse(updated)

    @application.post("/api/upload-qr")
    async def upload_qr(
        file: UploadFile = File(...),
        _auth: None = Depends(require_admin),
    ) -> JSONResponse:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, detail="Only PNG, JPEG, and WebP images are allowed.")
        data = await file.read()
        if len(data) > MAX_QR_SIZE:
            raise HTTPException(400, detail="Image too large (max 2 MB).")
        uploads_dir = SRC_DIR / "assets" / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(
            file.content_type, ".png"
        )
        filename = f"payment_qr{ext}"
        dest = uploads_dir / filename
        dest.write_bytes(data)
        url_path = f"/assets/uploads/{filename}"
        with WRITE_LOCK:
            current = read_config()
            current["qrImageSrc"] = url_path
            write_config(current)
            updated = read_config()
        return JSONResponse({"qrImageSrc": url_path, "config": updated})

    # ── Language-prefixed routes (/ru/, /en/, etc.) ──────────────────────
    # The original site used WordPress with WPML, generating /ru/... and
    # /en/... URLs.  We only have English static HTML, so every language
    # prefix transparently serves the same files.

    LANG_CODES = {"ru", "en", "de", "fr", "es", "pt", "zh", "ja", "ko"}

    # Map known WordPress-era slugs → local HTML files
    PAGE_MAP: dict[str, str] = {
        "": "index.html",
        "tochnyj-platezh": "mixer-result.html",
        "result-fa": "mixer-result.html",
        "result-mixer": "mixer-result.html",
        "mixer-result": "mixer-result.html",
    }

    def _serve_lang_page(lang: str, page_slug: str):
        slug = page_slug.strip("/")

        if "." in slug.split("/")[-1]:
            return RedirectResponse(url=f"/{slug}", status_code=301)

        html_file = PAGE_MAP.get(slug, "index.html")

        lang_path = SRC_DIR / lang / html_file
        root_path = SRC_DIR / html_file

        file_path = lang_path if lang_path.exists() else root_path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Not Found")

        return FileResponse(file_path, media_type="text/html")

    for _lang_code in LANG_CODES:
        @application.api_route(
            f"/{_lang_code}/{{page_slug:path}}",
            methods=["GET", "POST"],
            response_model=None,
            name=f"lang_{_lang_code}",
        )
        def lang_page(page_slug: str, _lc: str = _lang_code):
            return _serve_lang_page(_lc, page_slug)

    application.mount("/", StaticFiles(directory=str(SRC_DIR), html=True), name="site")
    return application


app = create_app()


def main() -> None:
    parser = argparse.ArgumentParser(description="MM5 mixer site (FastAPI static + config API)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    uvicorn.run("server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
