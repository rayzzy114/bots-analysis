import json
import os
from typing import List, Dict

PAYMENT_METHODS_FILE = "payment_methods.json"


def load_payment_methods() -> List[Dict[str, str]]:
    """Загружает методы оплаты из файла"""
    if os.path.exists(PAYMENT_METHODS_FILE):
        try:
            with open(PAYMENT_METHODS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return get_default_methods()
    return get_default_methods()


def save_payment_methods(methods: List[Dict[str, str]]) -> None:
    """Сохраняет методы оплаты в файл"""
    with open(PAYMENT_METHODS_FILE, "w", encoding="utf-8") as f:
        json.dump(methods, f, ensure_ascii=False, indent=2)


def get_default_methods() -> List[Dict[str, str]]:
    """Возвращает методы оплаты по умолчанию"""
    return [
        {"id": "sbp", "name": "🇷🇺 СБП РФ", "callback": "payment_sbp"},
        {"id": "tbank", "name": "⬇️ Перевод за границу из Т-Банка", "callback": "payment_tbank"}
    ]


def add_payment_method(name: str, callback: str) -> Dict[str, str]:
    """Добавляет новый метод оплаты"""
    methods = load_payment_methods()
    method_id = callback.replace("payment_", "")
    new_method = {
        "id": method_id,
        "name": name,
        "callback": callback
    }
    methods.append(new_method)
    save_payment_methods(methods)
    return new_method


def remove_payment_method(method_id: str) -> bool:
    """Удаляет метод оплаты"""
    methods = load_payment_methods()
    methods = [m for m in methods if m["id"] != method_id]
    save_payment_methods(methods)
    return True


def get_payment_methods() -> List[Dict[str, str]]:
    """Получает список всех методов оплаты"""
    return load_payment_methods()

