from __future__ import annotations

from html import escape

PGP_SIGNATURE_BLOCK = """PGP fingerprint: D3B2 8095 6F0E 7CAF / 051F D18E 8237 6A2A.
-----BEGIN PGP SIGNATURE-----

iQEcBAEBAgAGBQJf4tE/AAoJENOygJVvDnyvA9oH/j3VLz2i6k1JOM6ESKAp/zyD
pRZfp2YJlihJPetPq2incm6/EhL9EsFjlmgiZSunXeQEe1yqGSIDT3n/lbgpRs9I
U6cDWL+GkwJil9BS1FDCU3IZ09Q/Q7m1epu+ovI94ORSUO3BfDT498BpKemVeHA7
3Kmgg6FPiTTPoNFfuth1uf5Ms//B60qIAQnSAba2BOrEaoD9JtDfhlwvYnpMn7WP
MYsIEHtnYimmzr83yDo5VUq7to1NRAUjyxy1PecUqZpagT/h2ANvq7nMoLM9gY5t
1mqpz8DZVlhZfgLKbt2Kl69TLa6MVZ5DSKsijoRxY/tCDfjAKHOuSLdyqDHp0QU=
=8FWO
-----END PGP SIGNATURE-----"""


def language_prompt() -> str:
    return "Please choose a language:\nПожалуйста, выберите язык:\n请选择语言："


def clean_prompt(lang: str) -> str:
    if lang == "ru":
        return "Введите адрес получения очищенных BTC (обязательно):"
    if lang == "zh":
        return "请输入接收清洗后BTC的地址（必填）："
    return "Enter the BTC address for receiving cleaned coins (required):"


def invalid_btc_warning(lang: str) -> str:
    if lang == "zh":
        return "⚠️ 请输入有效的 BTC 地址。"
    if lang == "ru":
        return "⚠️ Нужен корректный BTC-адрес."
    return "⚠️ A valid BTC address is required."


def address_accepted(lang: str, wallet: str) -> str:
    if lang == "ru":
        return f"Адрес принят: {wallet}"
    if lang == "zh":
        return f"地址已接受： {wallet}"
    return f"Address accepted: {wallet}"


def confirm_prompt(lang: str) -> str:
    if lang == "ru":
        return "Подтвердите или отмените:"
    if lang == "zh":
        return "确认或取消："
    return "Confirm or cancel:"


def return_to_main_echo(lang: str) -> str:
    if lang == "ru":
        return "🏠 Вернуться в главное меню"
    if lang == "zh":
        return "🏠 返回主菜单"
    return "🏠 Return to main menu"


def qr_missing_text(lang: str) -> str:
    if lang == "ru":
        return "QR-изображение отсутствует. Свяжитесь с администратором."
    if lang == "zh":
        return "QR 图片缺失，请联系管理员。"
    return "QR image is missing. Contact admin."


def qr_failed_text(lang: str) -> str:
    if lang == "ru":
        return "Не удалось отправить QR. Свяжитесь с администратором."
    if lang == "zh":
        return "QR 发送失败，请联系管理员。"
    return "QR send failed. Contact admin."


def main_caption(lang: str, fee_percent: float, fee_fixed_btc: float, site_url: str, tor_url: str) -> str:
    fee = f"{fee_percent:.1f}%"
    fixed = f"{fee_fixed_btc:.4f}"
    site = escape(site_url, quote=True)
    tor = escape(tor_url, quote=True)

    if lang == "ru":
        return (
            "💎 <strong>Bitcoin миксер 2.0</strong>\n"
            "🔒 <em>Официальный бот (Русский)</em>\n\n"
            "Ваша полная анонимность и гарантия чистоты монет!\n"
            "Защита от анализа цепочек транзакций, схожих объёмов, кластерного анализа.\n\n"
            f"💰 <strong>Комиссия</strong>: до {fee} + {fixed} BTC\n"
            "⏰ <strong>Время очистки</strong>: до 6 часов.\n\n"
            f"🌐 <strong>Сайт</strong>: <a href=\"{site}\">{site}</a>\n"
            f"🧅 <strong>Tor</strong>: <a href=\"{tor}\">{tor}</a>"
        )

    if lang == "zh":
        return (
            "💎 <strong>比特币混币器 2.0</strong>\n"
            "🔒 <em>官方机器人 (中文)</em>\n\n"
            "保证您的完全匿名和币的纯净！\n"
            "防止链分析、交易量相关性、集群分析等。\n\n"
            f"💰 <strong>手续费</strong>: 最多{fee} + {fixed} BTC\n"
            "⏰ <strong>清洗时间</strong>: 最多6小时。\n\n"
            f"🌐 <strong>网站</strong>: <a href=\"{site}\">{site}</a>\n"
            f"🧅 <strong>Tor</strong>: <a href=\"{tor}\">{tor}</a>"
        )

    return (
        "💎 <strong>Bitcoin Mixer 2.0</strong>\n"
        "🔒 <em>Official bot (English)</em>\n\n"
        "Your complete anonymity and guarantee of coin purity!\n"
        "Protection against chain analysis, volume correlation, cluster analysis.\n\n"
        f"💰 <strong>Fee</strong>: up to {fee} + {fixed} BTC\n"
        "⏰ <strong>Cleaning time</strong>: up to 6 hours.\n\n"
        f"🌐 <strong>Website</strong>: <a href=\"{site}\">{site}</a>\n"
        f"🧅 <strong>Tor</strong>: <a href=\"{tor}\">{tor}</a>"
    )


def faq_text(lang: str, fee_percent: float, fee_fixed_btc: float) -> str:
    fee = f"{fee_percent:.1f}%"
    fixed = f"{fee_fixed_btc:.4f}"

    if lang == "ru":
        return (
            "❓ <strong>FAQ</strong>\n\n"
            f"• Случайная комиссия до {fee} + {fixed} BTC.\n"
            "• Мин. сумма: 0.003 BTC, макс: 50 BTC.\n"
            "• Адрес пополнения действует 168 часов.\n"
            "• Очищенные BTC вернутся случайными частями в течение 6 часов."
        )

    if lang == "zh":
        return (
            "❓ <strong>FAQ</strong>\n\n"
            f"• 随机手续费，最高 {fee} + {fixed} BTC。\n"
            "• 最低金额：0.003 BTC，最高：50 BTC。\n"
            "• 充值地址有效期为 168 小时。\n"
            "• 清洗后的 BTC 会在 6 小时内分批返回。"
        )

    return (
        "❓ <strong>FAQ</strong>\n\n"
        f"• We have a random fee, up to {fee} + {fixed} BTC.\n"
        "• Min amount: 0.003 BTC, Max: 50 BTC.\n"
        "• The deposit address is valid for 168 hours.\n"
        "• Clean BTC will be returned in random chunks within 6 hours."
    )


def order_text(
    lang: str,
    order_id: int,
    receiver_wallet: str,
    deposit_wallet: str,
    min_btc: float,
    max_btc: float,
) -> str:
    receiver = escape(receiver_wallet, quote=False)
    deposit = escape(deposit_wallet, quote=False)

    if lang == "ru":
        return (
            f"✨ Ваша заявка №{order_id} успешно создана!\n\n"
            "Вам необходимо отправить BTC на этот адрес, после чего, за вычетом комиссии, "
            f"вы получите очищенные монеты на <strong>{receiver}</strong>.\n\n"
            f"Mixer Money сгенерировал адрес: <strong>{deposit}</strong>\n\n"
            "⏰ Максимальное время очистки: 6 часов.\n"
            "⏳ Адрес действителен 168 часов.\n"
            f"💰 Сумма: {min_btc:.3f} - {max_btc:.0f} BTC\n\n"
            f"{PGP_SIGNATURE_BLOCK}\n\n"
            "⌛ Ожидаем ваш перевод..."
        )

    if lang == "zh":
        return (
            f"✨ 您的订单编号{order_id}已成功创建！\n\n"
            "请向此地址发送BTC，扣除手续费后，您将收到清洗后的币到 "
            f"<strong>{receiver}</strong>。\n\n"
            f"Mixer Money 生成的地址： <strong>{deposit}</strong>\n\n"
            "⏰ 最长清洗时间：6小时。\n"
            "⏳ 地址有效期168小时。\n"
            f"💰 数量限制：{min_btc:.3f} - {max_btc:.0f} BTC\n\n"
            f"{PGP_SIGNATURE_BLOCK}\n\n"
            "⌛ 等待您的转账..."
        )

    return (
        f"✨ Your order #{order_id} has been created successfully!\n\n"
        "You must send BTC to this address, then after the fee deduction, you "
        f"will receive clean coins at <strong>{receiver}</strong>.\n\n"
        f"Mixer Money generated address: <strong>{deposit}</strong>\n\n"
        "⏰ Maximum cleaning time: 6 hours.\n"
        "⏳ This address is valid for 168 hours.\n"
        f"💰 Amount: {min_btc:.3f} - {max_btc:.0f} BTC\n\n"
        f"{PGP_SIGNATURE_BLOCK}\n\n"
        "⌛ Waiting for your transfer..."
    )


def qr_caption(lang: str, deposit_wallet: str) -> str:
    address = escape(deposit_wallet, quote=False)
    if lang == "ru":
        return f"📌 Mixer Money сгенерировал адрес: <strong>{address}</strong>"
    if lang == "zh":
        return f"📌 Mixer Money 生成的地址： <strong>{address}</strong>"
    return f"📌 Mixer Money generated address: <strong>{address}</strong>"
