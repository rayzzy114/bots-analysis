# rapid_clone_bot

Клон `RAPID_EX_BOT`, собранный на основе зафиксированного `captured_flow.json` и медиа из `assets/`.

## Запуск

1. Установить зависимости:
```bash
pip install -r requirements.txt
```

2. Создать `.env` из `.env.example` и заполнить:
- `BOT_TOKEN`
- `ADMIN_IDS` (через запятую)

3. Обычный запуск:
```bash
python main.py
```

4. Hot-reload запуск:
```bash
python dev.py
```

## Запуск через uv (рекомендуется)

```bash
uv run dev.py
```

Если видите предупреждение про `VIRTUAL_ENV ... does not match the project environment path '.venv'`,
значит в shell уже активировано окружение другого проекта и вы запустили с `--active`.
Для запуска именно этого проекта:

```bash
deactivate  # если окружение активно
uv run dev.py
```

## Что внутри

- Пользовательский флоу берётся из `captured_flow.json`.
- Все кнопки главного меню и inline-кнопки собраны по захваченному флоу.
- Админ-панель подключена через `app/handlers/admin.py`.
- Медиа из донора лежат в `assets/`.
