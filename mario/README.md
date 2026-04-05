# ruMarioBTCbot Clone v2

Полноценный data-driven клон на основе собранного дампа:

- `data/raw/flow.json`
- `data/raw/edges.json`
- `data/raw/events.json`
- `assets/media/*`

## Запуск

```bash
cd ruMarioBTCbot_clone_v2
cp .env.example .env
# заполнить BOT_TOKEN и ADMIN_IDS
uv run main.py
```

При старте бот компилирует raw-flow в `data/compiled/` и запускает state-machine рантайм.

## Hot Reload

- Встроен hot-reload процесса по изменениям `*.py` и `.env`.
- Включение: `HOT_RELOAD=true`
- Интервал проверки: `HOT_RELOAD_INTERVAL_SECONDS=1.0`
- Изменения `.env` через админку автоматически применяются к процессу после перезапуска hot-reload.

## Админка

- Команда: `/admin`
- Доступ по `ADMIN_IDS` из `.env` (через запятую).
- Встроен Infinity AdminKit: комиссия, реквизиты, ссылки, обновление курсов.

## Курсы и калькулятор

- Расчеты quote идут через CoinGecko (`BTC/LTC/XMR/USDT/TRX/ETH/SOL`).
- Кнопка `Калькулятор` в amount-состояниях показывает актуальный курс и принимает сумму для пересчета.

## Запуск polling

- По умолчанию старт моментальный и webhook не удаляется: `DELETE_WEBHOOK_ON_START=false`.
- Если нужен сброс webhook перед polling, включи `DELETE_WEBHOOK_ON_START=true`.
- Выдача реквизитов после состояния поиска настраивается: `SEARCH_DELAY_SECONDS=15`.
- Если `ADMIN_IDS` не задан, `/admin` открыт для первичной настройки (режим single-user).
