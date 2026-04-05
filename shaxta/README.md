# Shaxta Bot

Телеграм-бот для покупки, продажи и обмена криптовалюты (aiogram + SQLite).

## Требования

- Python 3.10+
- `pip`

## Установка

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Настройка `.env`

Создайте/заполните `.env` в корне проекта. Минимально нужны:

- `BOT_TOKEN`
- `BOT_NAME`
- `OPERATOR`

Дополнительно можно задать:

- `OTZIVY`, `NEWS`
- `payment_details`, `PAYMENT_BANK`
- `DEFAULT_COMMISSION`, `RATE_UPDATE_INTERVAL`
- `ADMIN_IDS` (через запятую)

## Запуск бота

```bash
python main.py
```

## Проверки (опционально)

```bash
ruff check .
ruff format .
uvx ty check .
python -m unittest discover -s tests -p "test_*.py"
```
