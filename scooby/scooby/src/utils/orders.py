import json
import os
from typing import Dict, Optional

ORDERS_FILE = "orders.json"


def load_orders() -> Dict[str, dict]:
    """Загружает заявки из файла"""
    if os.path.exists(ORDERS_FILE):
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_orders(orders: Dict[str, dict]) -> None:
    """Сохраняет заявки в файл"""
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)


def create_order(order_id: str, user_chat_id: int, data: dict) -> None:
    """Создает новую заявку"""
    orders = load_orders()
    orders[order_id] = {
        "user_chat_id": user_chat_id,
        "status": "pending",
        **data
    }
    save_orders(orders)


def get_order(order_id: str) -> Optional[dict]:
    """Получает заявку по ID"""
    orders = load_orders()
    return orders.get(order_id)


def update_order_status(order_id: str, status: str) -> None:
    """Обновляет статус заявки"""
    orders = load_orders()
    if order_id in orders:
        orders[order_id]["status"] = status
        save_orders(orders)


def get_user_chat_id(order_id: str) -> Optional[int]:
    """Получает chat_id пользователя по order_id"""
    order = get_order(order_id)
    if order:
        return order.get("user_chat_id")
    return None

