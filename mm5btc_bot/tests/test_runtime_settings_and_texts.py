from __future__ import annotations

from pathlib import Path

from app.storage import SettingsStore
from app.keyboards import kb_confirm, kb_main, kb_return_to_main
from app.texts import address_accepted, clean_prompt, main_caption, order_text, qr_caption
from app.validation import is_valid_btc_address


def test_settings_defaults_expose_website_and_tor_urls_and_caption_uses_updated_values(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")

    settings = store.get()
    assert settings["site_url"] == "https://mixermoney.it.com"
    assert settings["tor_url"] == "http://mixereztksljzma2owmv6hmsrci322lsje6m3svicoddk3xbgvhd2fid.onion/"
    assert "qr_image_path" not in settings

    store.set_site_url("https://example.com")
    store.set_tor_url("http://exampleonion.onion/")

    updated = store.get()
    caption = main_caption(
        "en",
        float(updated["fee_percent"]),
        float(updated["fee_fixed_btc"]),
        updated["site_url"],
        updated["tor_url"],
    )

    assert "https://example.com" in caption
    assert "http://exampleonion.onion/" in caption


def test_main_caption_escapes_quotes_in_html_attributes() -> None:
    caption = main_caption(
        "en",
        4.5,
        0.0007,
        'https://example.com/?q="x"',
        "http://" + "a" * 56 + ".onion/",
    )

    assert '&quot;' in caption
    assert 'href="https://example.com/?q=&quot;x&quot;"' in caption


def test_btc_address_validation_rejects_prefixed_garbage() -> None:
    valid = "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt7"
    invalid = "bc1qga6mx70jx0uvfuk39eqpyyfwh9fsxzme75ckt8"

    assert is_valid_btc_address(valid)
    assert not is_valid_btc_address(invalid)


def test_russian_texts_match_captured_flow_copy() -> None:
    assert clean_prompt("ru") == "Введите адрес получения очищенных BTC (обязательно):"
    assert (
        order_text(
            "ru",
            67,
            "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH",
            "bc1qhwjxt3gpjnfs4cshfs55jg2mr3e9dafe6sl0jz",
            0.003,
            50.0,
        )
        == "✨ Ваша заявка №67 успешно создана!\n\n"
        "Вам необходимо отправить BTC на этот адрес, после чего, за вычетом комиссии, "
        "вы получите очищенные монеты на <strong>1FfmbHfnpaZjKFvyi1okTjJJusN455paPH</strong>.\n\n"
        "Mixer Money сгенерировал адрес: <strong>bc1qhwjxt3gpjnfs4cshfs55jg2mr3e9dafe6sl0jz</strong>\n\n"
        "⏰ Максимальное время очистки: 6 часов.\n"
        "⏳ Адрес действителен 168 часов.\n"
        "💰 Сумма: 0.003 - 50 BTC\n\n"
        "PGP fingerprint: D3B2 8095 6F0E 7CAF / 051F D18E 8237 6A2A.\n"
        "-----BEGIN PGP SIGNATURE-----\n\n"
        "iQEcBAEBAgAGBQJf4tE/AAoJENOygJVvDnyvA9oH/j3VLz2i6k1JOM6ESKAp/zyD\n"
        "pRZfp2YJlihJPetPq2incm6/EhL9EsFjlmgiZSunXeQEe1yqGSIDT3n/lbgpRs9I\n"
        "U6cDWL+GkwJil9BS1FDCU3IZ09Q/Q7m1epu+ovI94ORSUO3BfDT498BpKemVeHA7\n"
        "3Kmgg6FPiTTPoNFfuth1uf5Ms//B60qIAQnSAba2BOrEaoD9JtDfhlwvYnpMn7WP\n"
        "MYsIEHtnYimmzr83yDo5VUq7to1NRAUjyxy1PecUqZpagT/h2ANvq7nMoLM9gY5t\n"
        "1mqpz8DZVlhZfgLKbt2Kl69TLa6MVZ5DSKsijoRxY/tCDfjAKHOuSLdyqDHp0QU=\n"
        "=8FWO\n"
        "-----END PGP SIGNATURE-----\n\n"
        "⌛ Ожидаем ваш перевод..."
    )
    assert (
        qr_caption("ru", "bc1qhwjxt3gpjnfs4cshfs55jg2mr3e9dafe6sl0jz")
        == "📌 Mixer Money сгенерировал адрес: <strong>bc1qhwjxt3gpjnfs4cshfs55jg2mr3e9dafe6sl0jz</strong>"
    )


def test_russian_keyboards_match_captured_flow_buttons() -> None:
    confirm_keyboard = kb_confirm("ru", False)
    assert confirm_keyboard.keyboard[0][0].text == "✅ Начать очистку"
    assert confirm_keyboard.keyboard[0][1].text == "❌ Отменить очистку"

    main_keyboard = kb_return_to_main("ru")
    assert main_keyboard.keyboard[0][0].text == "🏠 Вернуться в главное меню"


def test_english_texts_match_captured_flow_copy() -> None:
    assert clean_prompt("en") == "Enter the BTC address for receiving cleaned coins (required):"
    assert address_accepted("en", "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH") == (
        "Address accepted: 1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"
    )
    assert (
        order_text(
            "en",
            68,
            "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH",
            "bc1qtf8wt2g0ck4ampyyef347rw6hzx7857grxy8cl",
            0.003,
            50.0,
        )
        == "✨ Your order #68 has been created successfully!\n\n"
        "You must send BTC to this address, then after the fee deduction, you will receive clean coins at "
        "<strong>1FfmbHfnpaZjKFvyi1okTjJJusN455paPH</strong>.\n\n"
        "Mixer Money generated address: <strong>bc1qtf8wt2g0ck4ampyyef347rw6hzx7857grxy8cl</strong>\n\n"
        "⏰ Maximum cleaning time: 6 hours.\n"
        "⏳ This address is valid for 168 hours.\n"
        "💰 Amount: 0.003 - 50 BTC\n\n"
        "PGP fingerprint: D3B2 8095 6F0E 7CAF / 051F D18E 8237 6A2A.\n"
        "-----BEGIN PGP SIGNATURE-----\n\n"
        "iQEcBAEBAgAGBQJf4tE/AAoJENOygJVvDnyvA9oH/j3VLz2i6k1JOM6ESKAp/zyD\n"
        "pRZfp2YJlihJPetPq2incm6/EhL9EsFjlmgiZSunXeQEe1yqGSIDT3n/lbgpRs9I\n"
        "U6cDWL+GkwJil9BS1FDCU3IZ09Q/Q7m1epu+ovI94ORSUO3BfDT498BpKemVeHA7\n"
        "3Kmgg6FPiTTPoNFfuth1uf5Ms//B60qIAQnSAba2BOrEaoD9JtDfhlwvYnpMn7WP\n"
        "MYsIEHtnYimmzr83yDo5VUq7to1NRAUjyxy1PecUqZpagT/h2ANvq7nMoLM9gY5t\n"
        "1mqpz8DZVlhZfgLKbt2Kl69TLa6MVZ5DSKsijoRxY/tCDfjAKHOuSLdyqDHp0QU=\n"
        "=8FWO\n"
        "-----END PGP SIGNATURE-----\n\n"
        "⌛ Waiting for your transfer..."
    )
    assert (
        qr_caption("en", "bc1qtf8wt2g0ck4ampyyef347rw6hzx7857grxy8cl")
        == "📌 Mixer Money generated address: <strong>bc1qtf8wt2g0ck4ampyyef347rw6hzx7857grxy8cl</strong>"
    )


def test_chinese_texts_match_captured_flow_copy() -> None:
    assert clean_prompt("zh") == "请输入接收清洗后BTC的地址（必填）："
    assert address_accepted("zh", "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH") == (
        "地址已接受： 1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"
    )
    assert (
        main_caption(
            "zh",
            4.5,
            0.0007,
            "https://mixermoney.it.com",
            "http://mixereztksljzma2owmv6hmsrci322lsje6m3svicoddk3xbgvhd2fid.onion/",
        )
        == "💎 <strong>比特币混币器 2.0</strong>\n"
        "🔒 <em>官方机器人 (中文)</em>\n\n"
        "保证您的完全匿名和币的纯净！\n"
        "防止链分析、交易量相关性、集群分析等。\n\n"
        "💰 <strong>手续费</strong>: 最多4.5% + 0.0007 BTC\n"
        "⏰ <strong>清洗时间</strong>: 最多6小时。\n\n"
        "🌐 <strong>网站</strong>: <a href=\"https://mixermoney.it.com\">https://mixermoney.it.com</a>\n"
        "🧅 <strong>Tor</strong>: <a href=\"http://mixereztksljzma2owmv6hmsrci322lsje6m3svicoddk3xbgvhd2fid.onion/\">http://mixereztksljzma2owmv6hmsrci322lsje6m3svicoddk3xbgvhd2fid.onion/</a>"
    )
    assert (
        order_text(
            "zh",
            69,
            "1FfmbHfnpaZjKFvyi1okTjJJusN455paPH",
            "bc1qrcp2zkcj5sjauf5psq3002ylve8szejunpqf2c",
            0.003,
            50.0,
        )
        == "✨ 您的订单编号69已成功创建！\n\n"
        "请向此地址发送BTC，扣除手续费后，您将收到清洗后的币到 <strong>1FfmbHfnpaZjKFvyi1okTjJJusN455paPH</strong>。\n\n"
        "Mixer Money 生成的地址： <strong>bc1qrcp2zkcj5sjauf5psq3002ylve8szejunpqf2c</strong>\n\n"
        "⏰ 最长清洗时间：6小时。\n"
        "⏳ 地址有效期168小时。\n"
        "💰 数量限制：0.003 - 50 BTC\n\n"
        "PGP fingerprint: D3B2 8095 6F0E 7CAF / 051F D18E 8237 6A2A.\n"
        "-----BEGIN PGP SIGNATURE-----\n\n"
        "iQEcBAEBAgAGBQJf4tE/AAoJENOygJVvDnyvA9oH/j3VLz2i6k1JOM6ESKAp/zyD\n"
        "pRZfp2YJlihJPetPq2incm6/EhL9EsFjlmgiZSunXeQEe1yqGSIDT3n/lbgpRs9I\n"
        "U6cDWL+GkwJil9BS1FDCU3IZ09Q/Q7m1epu+ovI94ORSUO3BfDT498BpKemVeHA7\n"
        "3Kmgg6FPiTTPoNFfuth1uf5Ms//B60qIAQnSAba2BOrEaoD9JtDfhlwvYnpMn7WP\n"
        "MYsIEHtnYimmzr83yDo5VUq7to1NRAUjyxy1PecUqZpagT/h2ANvq7nMoLM9gY5t\n"
        "1mqpz8DZVlhZfgLKbt2Kl69TLa6MVZ5DSKsijoRxY/tCDfjAKHOuSLdyqDHp0QU=\n"
        "=8FWO\n"
        "-----END PGP SIGNATURE-----\n\n"
        "⌛ 等待您的转账..."
    )
    assert (
        qr_caption("zh", "bc1qrcp2zkcj5sjauf5psq3002ylve8szejunpqf2c")
        == "📌 Mixer Money 生成的地址： <strong>bc1qrcp2zkcj5sjauf5psq3002ylve8szejunpqf2c</strong>"
    )


def test_chinese_keyboards_match_captured_flow_buttons() -> None:
    main_keyboard = kb_main("zh")
    assert main_keyboard.keyboard[0][0].text == "💸 清洗币"
    assert main_keyboard.keyboard[0][1].text == "❓ 常见问题"

    confirm_keyboard = kb_confirm("zh", False)
    assert confirm_keyboard.keyboard[0][0].text == "✅ 开始清洗"
    assert confirm_keyboard.keyboard[0][1].text == "❌ 取消清洗"

    return_keyboard = kb_return_to_main("zh")
    assert return_keyboard.keyboard[0][0].text == "🏠 返回主菜单"
