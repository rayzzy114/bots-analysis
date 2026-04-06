from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Literal, TypedDict, cast

from .config import LinkDefinition


class SplitMethodRequisitesData(TypedDict):
    bank: str
    value: str


class RequisitesData(TypedDict):
    mode: Literal["single", "split"]
    single_bank: str
    single_value: str
    payment_methods: list[str]
    split_by_method: dict[str, SplitMethodRequisitesData]


class SettingsData(TypedDict):
    commission_percent: float
    links: dict[str, str]
    sell_wallets: dict[str, str]
    requisites: RequisitesData


class HistoryEntry(TypedDict):
    ts: int
    side: str
    coin: str
    amount_coin: float
    amount_rub: float


class UserProfile(TypedDict):
    trades_total: int
    turnover_rub: float
    invited: int
    bonus_balance: float
    history: list[HistoryEntry]
    addresses: list[dict[str, str]]


class OrderData(TypedDict):
    order_id: str
    user_id: int
    username: str
    wallet: str
    coin_symbol: str
    coin_amount: float
    amount_rub: float
    payment_method: str
    bank: str
    status: Literal["pending_payment", "paid", "confirmed", "cancelled"]
    created_at: int
    updated_at: int
    confirmed_by: int | None


def _backup_corrupt_file(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}.corrupt.{stamp}{path.suffix}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}.corrupt.{stamp}.{counter}{path.suffix}")
        counter += 1
    path.replace(candidate)
    return candidate


def _load_json_or_recover(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _backup_corrupt_file(path)
        return {}
    if isinstance(data, dict):
        return cast(dict[str, object], data)
    _backup_corrupt_file(path)
    return {}


class SettingsStore:
    def __init__(
        self,
        path: Path,
        default_commission: float,
        link_definitions: tuple[LinkDefinition, ...],
        sell_wallet_labels: dict[str, str],
    ):
        self.path = path
        self.link_definitions = link_definitions
        self.sell_wallet_labels = dict(sell_wallet_labels)
        self.known_link_keys = {item.key for item in link_definitions}
        self.data: SettingsData = {
            "commission_percent": float(default_commission),
            "links": {item.key: item.default for item in link_definitions},
            "sell_wallets": {key: "" for key in sell_wallet_labels},
            "requisites": {
                "mode": "single",
                "single_bank": "Сбербанк",
                "single_value": "2200 0000 0000 0000",
                "payment_methods": ["Перевод на карту", "СБП"],
                "split_by_method": {},
            },
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._normalize_split_map()
            self.save()
            return
        raw = _load_json_or_recover(self.path)

        commission_raw = raw.get("commission_percent")
        if isinstance(commission_raw, (int, float)):
            self.data["commission_percent"] = float(commission_raw)

        links_raw = raw.get("links")
        if isinstance(links_raw, dict):
            merged_links = dict(self.data["links"])
            for key, value in links_raw.items():
                if isinstance(key, str) and isinstance(value, str) and key in self.known_link_keys:
                    merged_links[key] = value
            self.data["links"] = merged_links

        sell_wallets_raw = raw.get("sell_wallets")
        if isinstance(sell_wallets_raw, dict):
            merged_wallets = dict(self.data["sell_wallets"])
            for key, value in sell_wallets_raw.items():
                if isinstance(key, str) and isinstance(value, str) and key in self.sell_wallet_labels:
                    merged_wallets[key] = value.strip()
            self.data["sell_wallets"] = merged_wallets

        req_raw = raw.get("requisites")
        if isinstance(req_raw, dict):
            req = cast(dict[str, object], req_raw)

            mode_raw = req.get("mode")
            if isinstance(mode_raw, str) and mode_raw in {"single", "split"}:
                self.data["requisites"]["mode"] = cast(Literal["single", "split"], mode_raw)

            single_bank_raw = req.get("single_bank")
            if isinstance(single_bank_raw, str) and single_bank_raw.strip():
                self.data["requisites"]["single_bank"] = single_bank_raw.strip()

            single_value_raw = req.get("single_value")
            if isinstance(single_value_raw, str) and single_value_raw.strip():
                self.data["requisites"]["single_value"] = single_value_raw.strip()

            methods_raw = req.get("payment_methods")
            if isinstance(methods_raw, list):
                methods = [item.strip() for item in methods_raw if isinstance(item, str) and item.strip()]
                if methods:
                    self.data["requisites"]["payment_methods"] = methods

            split_by_method_raw = req.get("split_by_method")
            if isinstance(split_by_method_raw, dict):
                parsed_split: dict[str, SplitMethodRequisitesData] = {}
                for method, value in split_by_method_raw.items():
                    if not isinstance(method, str) or not isinstance(value, dict):
                        continue
                    value_obj = cast(dict[str, object], value)
                    bank = value_obj.get("bank")
                    requisites = value_obj.get("value")
                    if not isinstance(bank, str) or not isinstance(requisites, str):
                        continue
                    method_name = method.strip()
                    bank_name = bank.strip()
                    req_value = requisites.strip()
                    if method_name and bank_name and req_value:
                        parsed_split[method_name] = {"bank": bank_name, "value": req_value}
                if parsed_split:
                    self.data["requisites"]["split_by_method"] = parsed_split

        self._normalize_split_map()
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _normalize_split_map(self) -> None:
        req = self.data["requisites"]
        split = req["split_by_method"]
        for method in req["payment_methods"]:
            row = split.get(method)
            if row is not None and row["bank"].strip() and row["value"].strip():
                continue
            split[method] = {
                "bank": req["single_bank"],
                "value": req["single_value"],
            }
        for key in list(split.keys()):
            if key not in req["payment_methods"]:
                split.pop(key, None)

    @property
    def commission_percent(self) -> float:
        return self.data["commission_percent"]

    def set_commission(self, value: float) -> None:
        self.data["commission_percent"] = float(str(value).replace(",", ".").replace(" ", ""))
        self.save()

    def link(self, key: str) -> str:
        return self.data["links"].get(key, "")

    def all_links(self) -> dict[str, str]:
        return dict(self.data["links"])

    def set_link(self, key: str, value: str) -> bool:
        if key not in self.known_link_keys:
            return False
        self.data["links"][key] = value.strip()
        self.save()
        return True

    def sell_wallet(self, key: str) -> str:
        return self.data["sell_wallets"].get(key, "")

    def all_sell_wallets(self) -> dict[str, str]:
        return dict(self.data["sell_wallets"])

    def set_sell_wallet(self, key: str, value: str) -> bool:
        wallet_key = key.strip().lower()
        if wallet_key not in self.sell_wallet_labels:
            return False
        wallet_value = value.strip()
        if len(wallet_value) > 256:
            return False
        self.data["sell_wallets"][wallet_key] = wallet_value
        self.save()
        return True

    @property
    def requisites_mode(self) -> Literal["single", "split"]:
        return self.data["requisites"]["mode"]

    def set_requisites_mode(self, mode: Literal["single", "split"]) -> None:
        self.data["requisites"]["mode"] = mode
        self._normalize_split_map()
        self.save()

    def toggle_requisites_mode(self) -> None:
        self.set_requisites_mode("split" if self.requisites_mode == "single" else "single")

    @property
    def requisites_bank(self) -> str:
        return self.data["requisites"]["single_bank"]

    @property
    def requisites_value(self) -> str:
        return self.data["requisites"]["single_value"]

    def set_requisites_bank(self, bank: str) -> None:
        bank = bank.strip()
        if not bank:
            return
        self.data["requisites"]["single_bank"] = bank
        if self.requisites_mode == "single":
            for method in self.data["requisites"]["payment_methods"]:
                self.data["requisites"]["split_by_method"][method]["bank"] = bank
        self.save()

    def set_requisites_value(self, value: str) -> None:
        value = value.strip()
        if not value:
            return
        self.data["requisites"]["single_value"] = value
        if self.requisites_mode == "single":
            for method in self.data["requisites"]["payment_methods"]:
                self.data["requisites"]["split_by_method"][method]["value"] = value
        self.save()

    def payment_methods(self) -> list[str]:
        return list(self.data["requisites"]["payment_methods"])

    def add_payment_method(self, value: str) -> bool:
        value = value.strip()
        if len(value) < 2:
            return False
        methods = self.data["requisites"]["payment_methods"]
        if value in methods:
            return False
        methods.append(value)
        self.data["requisites"]["split_by_method"][value] = {
            "bank": self.data["requisites"]["single_bank"],
            "value": self.data["requisites"]["single_value"],
        }
        self.save()
        return True

    def delete_payment_method(self, index: int) -> bool:
        methods = self.data["requisites"]["payment_methods"]
        if len(methods) <= 1:
            return False
        if index < 0 or index >= len(methods):
            return False
        deleted = methods.pop(index)
        self.data["requisites"]["split_by_method"].pop(deleted, None)
        self.save()
        return True

    def split_method_map(self) -> dict[str, SplitMethodRequisitesData]:
        self._normalize_split_map()
        return {
            key: {"bank": value["bank"], "value": value["value"]}
            for key, value in self.data["requisites"]["split_by_method"].items()
        }

    def method_requisites(self, method: str) -> tuple[str, str]:
        if self.requisites_mode == "single":
            return self.requisites_bank, self.requisites_value
        row = self.data["requisites"]["split_by_method"].get(method)
        if row is None:
            return self.requisites_bank, self.requisites_value
        return row["bank"], row["value"]

    def set_method_requisites(self, method: str, bank: str, value: str) -> bool:
        method = method.strip()
        bank = bank.strip()
        value = value.strip()
        if method not in self.data["requisites"]["payment_methods"]:
            return False
        if not bank or not value:
            return False
        self.data["requisites"]["split_by_method"][method] = {"bank": bank, "value": value}
        self.save()
        return True


class UsersStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, UserProfile] = {}
        self.load()

    @staticmethod
    def _default_profile() -> UserProfile:
        return {
            "trades_total": 0,
            "turnover_rub": 0.0,
            "invited": 0,
            "bonus_balance": 0.0,
            "history": [],
            "addresses": [],
        }

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        raw = _load_json_or_recover(self.path)
        parsed: dict[str, UserProfile] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            item = cast(dict[str, object], value)
            profile = self._default_profile()
            if isinstance(item.get("trades_total"), int):
                profile["trades_total"] = cast(int, item["trades_total"])
            if isinstance(item.get("invited"), int):
                profile["invited"] = cast(int, item["invited"])
            if isinstance(item.get("turnover_rub"), (int, float)):
                profile["turnover_rub"] = float(cast(int | float, item["turnover_rub"]))
            if isinstance(item.get("bonus_balance"), (int, float)):
                profile["bonus_balance"] = float(cast(int | float, item["bonus_balance"]))
            history_raw = item.get("history")
            if isinstance(history_raw, list):
                entries: list[HistoryEntry] = []
                for row in history_raw:
                    if not isinstance(row, dict):
                        continue
                    row_obj = cast(dict[str, object], row)
                    ts = row_obj.get("ts")
                    side = row_obj.get("side")
                    coin = row_obj.get("coin")
                    amount_coin = row_obj.get("amount_coin")
                    amount_rub = row_obj.get("amount_rub")
                    if not isinstance(ts, int):
                        continue
                    if not isinstance(side, str) or not isinstance(coin, str):
                        continue
                    if not isinstance(amount_coin, (int, float)) or not isinstance(amount_rub, (int, float)):
                        continue
                    entries.append(
                        {
                            "ts": ts,
                            "side": side,
                            "coin": coin,
                            "amount_coin": float(amount_coin),
                            "amount_rub": float(amount_rub),
                        }
                    )
                profile["history"] = entries[-20:]
            addresses_raw = item.get("addresses")
            if isinstance(addresses_raw, list):
                parsed_addresses: list[dict[str, str]] = []
                for row in addresses_raw:
                    if not isinstance(row, dict):
                        continue
                    row_obj = cast(dict[str, object], row)
                    coin = row_obj.get("coin")
                    address = row_obj.get("address")
                    name = row_obj.get("name")
                    if not isinstance(coin, str) or not isinstance(address, str) or not isinstance(name, str):
                        continue
                    coin_clean = coin.strip().upper()
                    address_clean = address.strip()
                    name_clean = name.strip()
                    if not coin_clean or not address_clean or not name_clean:
                        continue
                    parsed_addresses.append(
                        {
                            "coin": coin_clean,
                            "address": address_clean,
                            "name": name_clean,
                        }
                    )
                profile["addresses"] = parsed_addresses[:100]
            parsed[key] = profile
        self.data = parsed
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def user(self, user_id: int) -> UserProfile:
        key = str(user_id)
        if key not in self.data:
            self.data[key] = self._default_profile()
            self.save()
        return self.data[key]

    def record_trade(
        self,
        user_id: int,
        side: str,
        coin: str,
        amount_coin: float,
        amount_rub: float,
    ) -> None:
        profile = self.user(user_id)
        profile["trades_total"] += 1
        profile["turnover_rub"] = round(profile["turnover_rub"] + float(amount_rub), 2)
        profile["bonus_balance"] = round(profile["bonus_balance"] + float(amount_rub) * 0.01, 2)
        profile["history"].append(
            {
                "ts": int(time.time()),
                "side": side,
                "coin": coin,
                "amount_coin": round(amount_coin, 8),
                "amount_rub": round(amount_rub, 2),
            }
        )
        profile["history"] = profile["history"][-20:]
        self.save()

    def add_address(self, user_id: int, coin: str, address: str, name: str) -> None:
        profile = self.user(user_id)
        profile["addresses"].append(
            {
                "coin": coin.strip().upper(),
                "address": address.strip(),
                "name": name.strip(),
            }
        )
        profile["addresses"] = profile["addresses"][:100]
        self.save()

    def list_addresses(self, user_id: int) -> list[dict[str, str]]:
        profile = self.user(user_id)
        return [
            {"coin": item["coin"], "address": item["address"], "name": item["name"]}
            for item in profile["addresses"]
        ]

    def delete_address(self, user_id: int, index: int) -> bool:
        profile = self.user(user_id)
        if index < 0 or index >= len(profile["addresses"]):
            return False
        profile["addresses"].pop(index)
        self.save()
        return True


class OrdersStore:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, OrderData] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        raw = _load_json_or_recover(self.path)
        parsed: dict[str, OrderData] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, dict):
                continue
            item = cast(dict[str, object], value)
            order_id = str(item.get("order_id") or key)
            user_id = item.get("user_id")
            username = item.get("username")
            wallet = item.get("wallet")
            coin_symbol = item.get("coin_symbol")
            coin_amount = item.get("coin_amount")
            amount_rub = item.get("amount_rub")
            payment_method = item.get("payment_method")
            bank = item.get("bank")
            status = item.get("status")
            created_at = item.get("created_at")
            updated_at = item.get("updated_at")
            confirmed_by = item.get("confirmed_by")
            if not isinstance(user_id, int):
                continue
            if not isinstance(username, str) or not isinstance(wallet, str):
                continue
            if not isinstance(coin_symbol, str):
                continue
            if not isinstance(coin_amount, (int, float)):
                continue
            if not isinstance(amount_rub, (int, float)):
                continue
            if not isinstance(payment_method, str) or not isinstance(bank, str):
                continue
            if status not in {"pending_payment", "paid", "confirmed", "cancelled"}:
                continue
            if not isinstance(created_at, int) or not isinstance(updated_at, int):
                continue
            parsed[order_id] = {
                "order_id": order_id,
                "user_id": user_id,
                "username": username,
                "wallet": wallet,
                "coin_symbol": coin_symbol,
                "coin_amount": float(coin_amount),
                "amount_rub": float(amount_rub),
                "payment_method": payment_method,
                "bank": bank,
                "status": cast(Literal["pending_payment", "paid", "confirmed", "cancelled"], status),
                "created_at": created_at,
                "updated_at": updated_at,
                "confirmed_by": confirmed_by if isinstance(confirmed_by, int) else None,
            }
        self.data = parsed
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _new_order_id(self) -> str:
        for _ in range(100):
            candidate = str(random.randint(100000, 999999))
            if candidate not in self.data:
                return candidate
        return str(int(time.time()))

    def create_order(
        self,
        user_id: int,
        username: str,
        wallet: str,
        coin_symbol: str,
        coin_amount: float,
        amount_rub: float,
        payment_method: str,
        bank: str,
    ) -> OrderData:
        now_ts = int(time.time())
        order_id = self._new_order_id()
        order: OrderData = {
            "order_id": order_id,
            "user_id": user_id,
            "username": username,
            "wallet": wallet,
            "coin_symbol": coin_symbol,
            "coin_amount": float(coin_amount),
            "amount_rub": float(amount_rub),
            "payment_method": payment_method,
            "bank": bank,
            "status": "pending_payment",
            "created_at": now_ts,
            "updated_at": now_ts,
            "confirmed_by": None,
        }
        self.data[order_id] = order
        self.save()
        return order

    def get_order(self, order_id: str) -> OrderData | None:
        return self.data.get(order_id)

    def mark_paid(self, order_id: str) -> bool:
        order = self.data.get(order_id)
        if order is None or order["status"] != "pending_payment":
            return False
        order["status"] = "paid"
        order["updated_at"] = int(time.time())
        self.save()
        return True

    def mark_cancelled(self, order_id: str) -> bool:
        order = self.data.get(order_id)
        if order is None or order["status"] != "pending_payment":
            return False
        order["status"] = "cancelled"
        order["updated_at"] = int(time.time())
        self.save()
        return True

    def confirm_order(self, order_id: str, admin_id: int) -> tuple[bool, OrderData | None]:
        order = self.data.get(order_id)
        if order is None:
            return False, None
        if order["status"] != "paid":
            return False, order
        order["status"] = "confirmed"
        order["confirmed_by"] = admin_id
        order["updated_at"] = int(time.time())
        self.save()
        return True, order

    def all_orders(self) -> list[dict]:
        """Return all orders as a list."""
        return list(self.data.values())
