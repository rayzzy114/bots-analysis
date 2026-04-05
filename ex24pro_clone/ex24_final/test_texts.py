from __future__ import annotations

from texts import get_text


def test_welcome_source_question_is_question() -> None:
    assert get_text("welcome_source_question", "ru") == "💛 Подскажите, пожалуйста, как вы узнали о боте?"


def test_welcome_followup_is_source_acknowledgement() -> None:
    assert get_text("welcome_followup", "ru") == (
        "💛 Ответ принят! Спасибо за обратную связь!"
    )


def test_welcome_manager_connected_block_matches_request() -> None:
    expected = (
        "🧑‍💻Менеджер подключился к чату!\n"
        "\n"
        "Больше информации о нашем сервисе:\n"
        "\n"
        "⚡️EX24.PRO: Работаем в Таиланде, Китае, Бали, Турции и ОАЭ с 2015 года!\n"
        "\n"
        "🏠Новостной канал: <a href=\"https://t.me/exchange24thalland\">Ознакомиться</a>\n"
        "🫂Отзывы о работе: <a href=\"https://t.me/ex24pro_comments\">Ознакомиться</a>"
    )

    assert get_text("welcome_manager_connected", "ru") == expected


def test_welcome_help_prompt_matches_request() -> None:
    assert get_text("welcome_help_prompt", "ru") == "💛 Здравствуйте, чем могу Вам помочь?"
