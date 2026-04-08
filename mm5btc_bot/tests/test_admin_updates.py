from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile, CallbackQuery, Chat, Message, Update, User

from app.context import AppContext
from app.handlers.admin import build_admin_router
from app.handlers.user import build_user_router
from app.storage import RuntimeStore, SettingsStore, build_wallet_qr_png_bytes
from app.texts import (
    address_accepted,
    clean_prompt,
    confirm_prompt,
    order_text,
    qr_caption,
    qr_failed_text,
)


def _make_user(user_id: int) -> User:
    return User(id=user_id, is_bot=False, first_name="Admin")


def _make_chat(chat_id: int = 100) -> Chat:
    return Chat(id=chat_id, type="private")


def _make_message(text: str, user_id: int, message_id: int) -> Message:
    return Message(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=_make_chat(),
        from_user=_make_user(user_id),
        text=text,
    )


def _make_callback(data: str, message: Message, user_id: int, callback_id: str) -> CallbackQuery:
    return CallbackQuery(
        id=callback_id,
        from_user=_make_user(user_id),
        chat_instance="chat-instance",
        message=message,
        data=data,
    )


async def _run_user_order_flow(
    tmp_path: Path,
    language: str = "Русский",
    *,
    fail_qr_photo: bool = False,
    fail_qr_document: bool = False,
) -> tuple[list[str], list[dict[str, object]], list[dict[str, object]]]:
    settings = SettingsStore(tmp_path / "settings.json")
    current_wallet = "bc1qupdateddepositwallet000000000000000000000000000000"
    settings.set_deposit_address(current_wallet)
    ctx = AppContext(
        root_dir=tmp_path,
        settings=settings,
        runtime=RuntimeStore(tmp_path / "runtime.json"),
        admin_ids={42},
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_user_router(ctx))
    bot = Bot("12345:ABCDE")

    answer = AsyncMock()
    photo_call_index = 0

    async def answer_photo_side_effect(*args: object, **kwargs: object) -> None:
        nonlocal photo_call_index
        photo_call_index += 1
        if fail_qr_photo and photo_call_index == 2:
            raise RuntimeError("photo failed")

    async def answer_document_side_effect(*args: object, **kwargs: object) -> None:
        if fail_qr_document:
            raise RuntimeError("document failed")

    answer_photo = AsyncMock(side_effect=answer_photo_side_effect)
    answer_document = AsyncMock(side_effect=answer_document_side_effect)

    with (
        patch.object(Message, "answer", answer),
        patch.object(Message, "answer_photo", answer_photo),
        patch.object(Message, "answer_document", answer_document),
    ):
        await dp.feed_update(bot, Update(update_id=1, message=_make_message("/start", 7, 1)))
        await dp.feed_update(bot, Update(update_id=2, message=_make_message(language, 7, 2)))
        clean_button = {
            "English": "💸 Clean coins",
            "Русский": "💸 Очистить монеты",
            "中文": "💸 清洗币",
        }[language]
        start_button = {
            "English": "✅ Start cleaning",
            "Русский": "✅ Начать очистку",
            "中文": "✅ 开始清洗",
        }[language]
        await dp.feed_update(bot, Update(update_id=3, message=_make_message(clean_button, 7, 3)))
        await dp.feed_update(
            bot,
            Update(update_id=4, message=_make_message("1BoatSLRHtKNngkdXEeobR76b53LETtpyT", 7, 4)),
        )
        await dp.feed_update(bot, Update(update_id=5, message=_make_message(start_button, 7, 5)))

    rendered = [str(call.args[0]) for call in answer.await_args_list]
    return rendered, [call.kwargs for call in answer_photo.await_args_list], [call.kwargs for call in answer_document.await_args_list]


def test_admin_flow_updates_website_and_tor_urls(tmp_path: Path) -> None:
    async def run_flow() -> tuple[list[str], dict[str, object]]:
        settings = SettingsStore(tmp_path / "settings.json")
        ctx = AppContext(
            root_dir=tmp_path,
            settings=settings,
            runtime=RuntimeStore(tmp_path / "runtime.json"),
            admin_ids={42},
        )

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(build_admin_router(ctx))
        bot = Bot("12345:ABCDE")

        message_answer = AsyncMock()
        callback_answer = AsyncMock()

        with (
            patch.object(Message, "answer", message_answer),
            patch.object(CallbackQuery, "answer", callback_answer),
        ):
            await dp.feed_update(bot, Update(update_id=1, message=_make_message("/admin", 42, 1)))
            await dp.feed_update(
                bot,
                Update(
                    update_id=2,
                    callback_query=_make_callback("admin:set_website", _make_message("/admin", 42, 1), 42, "cb-1"),
                ),
            )
            await dp.feed_update(bot, Update(update_id=3, message=_make_message('https://bad"site".example', 42, 2)))
            assert settings.get()["site_url"] == "https://mixermoney.it.com"
            await dp.feed_update(bot, Update(update_id=4, message=_make_message("https://new.example", 42, 3)))
            await dp.feed_update(
                bot,
                Update(
                    update_id=5,
                    callback_query=_make_callback("admin:set_tor", _make_message("/admin", 42, 1), 42, "cb-2"),
                ),
            )
            await dp.feed_update(bot, Update(update_id=6, message=_make_message("http://newtor.onion/", 42, 4)))
            assert settings.get()["tor_url"] == "http://mixereztksljzma2owmv6hmsrci322lsje6m3svicoddk3xbgvhd2fid.onion/"
            await dp.feed_update(
                bot,
                Update(
                    update_id=7,
                    message=_make_message("http://" + "a" * 56 + ".onion/", 42, 5),
                ),
            )

        rendered = [str(call.args[0]) for call in message_answer.await_args_list]
        return rendered, settings.get()

    rendered_texts, stored = asyncio.run(run_flow())

    assert stored["site_url"] == "https://new.example"
    assert stored["tor_url"] == "http://" + "a" * 56 + ".onion/"
    assert any("Invalid website URL" in text for text in rendered_texts)
    assert any("Invalid Tor URL" in text for text in rendered_texts)
    assert any("https://new.example" in text and ("http://" + "a" * 56 + ".onion/") in text for text in rendered_texts)


def test_admin_flow_updates_deposit_address_without_qr_upload(tmp_path: Path) -> None:
    async def run_flow() -> tuple[list[str], dict[str, object]]:
        settings = SettingsStore(tmp_path / "settings.json")
        ctx = AppContext(
            root_dir=tmp_path,
            settings=settings,
            runtime=RuntimeStore(tmp_path / "runtime.json"),
            admin_ids={42},
        )

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(build_admin_router(ctx))
        bot = Bot("12345:ABCDE")

        message_answer = AsyncMock()
        callback_answer = AsyncMock()

        with (
            patch.object(Message, "answer", message_answer),
            patch.object(CallbackQuery, "answer", callback_answer),
        ):
            await dp.feed_update(bot, Update(update_id=1, message=_make_message("/admin", 42, 1)))
            await dp.feed_update(
                bot,
                Update(
                    update_id=2,
                    callback_query=_make_callback("admin:set_address", _make_message("/admin", 42, 1), 42, "cb-1"),
                ),
            )
            await dp.feed_update(bot, Update(update_id=3, message=_make_message("1BoatSLRHtKNngkdXEeobR76b53LETtpyT", 42, 2)))

        rendered = [str(call.args[0]) for call in message_answer.await_args_list]
        return rendered, settings.get()

    rendered_texts, stored = asyncio.run(run_flow())

    assert stored["deposit_btc_address"] == "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
    assert any("Deposit address updated." in text for text in rendered_texts)
    assert any("1BoatSLRHtKNngkdXEeobR76b53LETtpyT" in text for text in rendered_texts)
    assert not any("upload QR" in text or "QR path" in text for text in rendered_texts)


def test_admin_flow_rejects_structurally_invalid_deposit_address(tmp_path: Path) -> None:
    async def run_flow() -> tuple[list[str], dict[str, object]]:
        settings = SettingsStore(tmp_path / "settings.json")
        ctx = AppContext(
            root_dir=tmp_path,
            settings=settings,
            runtime=RuntimeStore(tmp_path / "runtime.json"),
            admin_ids={42},
        )

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(build_admin_router(ctx))
        bot = Bot("12345:ABCDE")

        message_answer = AsyncMock()
        callback_answer = AsyncMock()

        invalid_wallet = "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt8"
        with (
            patch.object(Message, "answer", message_answer),
            patch.object(CallbackQuery, "answer", callback_answer),
        ):
            await dp.feed_update(bot, Update(update_id=1, message=_make_message("/admin", 42, 1)))
            await dp.feed_update(
                bot,
                Update(
                    update_id=2,
                    callback_query=_make_callback("admin:set_address", _make_message("/admin", 42, 1), 42, "cb-1"),
                ),
            )
            await dp.feed_update(bot, Update(update_id=3, message=_make_message(invalid_wallet, 42, 2)))

        rendered = [str(call.args[0]) for call in message_answer.await_args_list]
        return rendered, settings.get()

    rendered_texts, stored = asyncio.run(run_flow())

    assert stored["deposit_btc_address"] == "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7"
    assert any("Invalid BTC address" in text for text in rendered_texts)


def test_order_flow_uses_current_deposit_wallet_for_text_and_qr_bytes(tmp_path: Path) -> None:
    rendered_texts, photo_calls, document_calls = asyncio.run(_run_user_order_flow(tmp_path))

    current_wallet = "bc1qupdateddepositwallet000000000000000000000000000000"
    receiver_wallet = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"
    assert clean_prompt("ru") in rendered_texts
    assert address_accepted("ru", receiver_wallet) in rendered_texts
    assert confirm_prompt("ru") in rendered_texts
    assert order_text("ru", 24, receiver_wallet, current_wallet, 0.003, 50.0) in rendered_texts

    qr_call = next(call for call in photo_calls if current_wallet in str(call.get("caption", "")))
    qr_payload = qr_call["photo"]
    assert isinstance(qr_payload, BufferedInputFile)
    assert qr_payload.filename == "payment_qr.png"
    assert qr_payload.data == build_wallet_qr_png_bytes(current_wallet)
    assert not document_calls


def test_user_flow_rejects_structurally_invalid_receiver_wallet(tmp_path: Path) -> None:
    async def run_flow() -> tuple[list[str], dict[str, object]]:
        settings = SettingsStore(tmp_path / "settings.json")
        ctx = AppContext(
            root_dir=tmp_path,
            settings=settings,
            runtime=RuntimeStore(tmp_path / "runtime.json"),
            admin_ids={42},
        )

        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(build_user_router(ctx))
        bot = Bot("12345:ABCDE")

        answer = AsyncMock()
        answer_photo = AsyncMock()
        answer_document = AsyncMock()

        invalid_wallet = "bc1qreceiverwallet0000000000000000000000000000000001"
        with (
            patch.object(Message, "answer", answer),
            patch.object(Message, "answer_photo", answer_photo),
            patch.object(Message, "answer_document", answer_document),
        ):
            await dp.feed_update(bot, Update(update_id=1, message=_make_message("/start", 7, 1)))
            await dp.feed_update(bot, Update(update_id=2, message=_make_message("Русский", 7, 2)))
            await dp.feed_update(bot, Update(update_id=3, message=_make_message("💸 Очистить монеты", 7, 3)))
            await dp.feed_update(bot, Update(update_id=4, message=_make_message(invalid_wallet, 7, 4)))

        rendered = [str(call.args[0]) for call in answer.await_args_list]
        return rendered, settings.get()

    rendered_texts, stored = asyncio.run(run_flow())

    assert stored["deposit_btc_address"] == "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7"
    assert any("Нужен корректный BTC-адрес" in text for text in rendered_texts)
    assert any("Введите адрес получения очищенных BTC" in text for text in rendered_texts)
    assert not any("Адрес принят" in text for text in rendered_texts)


def test_order_flow_falls_back_to_document_when_photo_send_fails(tmp_path: Path) -> None:
    rendered_texts, photo_calls, document_calls = asyncio.run(
        _run_user_order_flow(tmp_path, fail_qr_photo=True)
    )

    current_wallet = "bc1qupdateddepositwallet000000000000000000000000000000"
    assert len(photo_calls) >= 2
    assert len(document_calls) == 1
    qr_photo_call = next(call for call in photo_calls if current_wallet in str(call.get("caption", "")))
    assert isinstance(qr_photo_call["photo"], BufferedInputFile)
    assert qr_caption("ru", current_wallet) == document_calls[0]["caption"]
    assert isinstance(document_calls[0]["document"], BufferedInputFile)
    assert document_calls[0]["document"].data == build_wallet_qr_png_bytes(current_wallet)
    assert qr_failed_text("ru") not in rendered_texts


def test_order_flow_shows_text_fallback_when_qr_media_sends_fail(tmp_path: Path) -> None:
    rendered_texts, photo_calls, document_calls = asyncio.run(
        _run_user_order_flow(
            tmp_path,
            fail_qr_photo=True,
            fail_qr_document=True,
        )
    )

    current_wallet = "bc1qupdateddepositwallet000000000000000000000000000000"
    assert len(photo_calls) >= 2
    assert len(document_calls) == 1
    qr_photo_call = next(call for call in photo_calls if current_wallet in str(call.get("caption", "")))
    assert isinstance(qr_photo_call["photo"], BufferedInputFile)
    assert qr_failed_text("ru") in rendered_texts


def test_chinese_user_flow_localized_buttons_and_copy_match_captured_flow(tmp_path: Path) -> None:
    rendered_texts, photo_calls, document_calls = asyncio.run(
        _run_user_order_flow(tmp_path, language="中文")
    )

    current_wallet = "bc1qupdateddepositwallet000000000000000000000000000000"
    receiver_wallet = "1BoatSLRHtKNngkdXEeobR76b53LETtpyT"

    assert clean_prompt("zh") in rendered_texts
    assert address_accepted("zh", receiver_wallet) in rendered_texts
    assert confirm_prompt("zh") in rendered_texts
    assert order_text("zh", 24, receiver_wallet, current_wallet, 0.003, 50.0) in rendered_texts

    qr_call = next(call for call in photo_calls if current_wallet in str(call.get("caption", "")))
    assert qr_call["caption"] == qr_caption("zh", current_wallet)
    assert not document_calls
