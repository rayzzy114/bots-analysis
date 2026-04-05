#!/bin/bash

echo "[*] Установка зависимостей Debian..."
apt update && apt install -y python3-venv python3-pip

echo "[*] Создание виртуального окружения..."
python3 -m venv venv

echo "[*] Установка Python библиотек..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install aiogram>=3.24.0 aiosqlite>=0.22.1 sqlalchemy>=2.0.46 python-dotenv>=1.2.1 apscheduler>=3.11.2 fastapi>=0.128.0 sqladmin>=0.22.0 uvicorn>=0.40.0 watchfiles>=1.1.1 jinja2>=3.1.6

if [ ! -f .env ]; then
    echo "[*] Создание .env из шаблона..."
    echo "BOT_TOKEN=your_token" > .env
    echo "ADMIN_ID=your_id" >> .env
    echo "WEB_ADMIN_USERNAME=admin" >> .env
    echo "WEB_ADMIN_PASSWORD=admin" >> .env
    echo "SECRET_KEY=some_secret" >> .env
    echo "[!] НЕ ЗАБУДЬТЕ ОТРЕДАКТИРОВАТЬ .env!"
fi

echo "[+] Настройка завершена."
echo "[>] Запуск бота: ./venv/bin/python3 dev.py"
