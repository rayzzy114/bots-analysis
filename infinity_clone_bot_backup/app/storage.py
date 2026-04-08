import json
import time
from pathlib import Path
from typing import TypedDict, cast


class SettingsData(TypedDict):
    commission_percent: float
    links: dict[str, str]
    requisites: "RequisitesData"


class RequisitesData(TypedDict):
    mode: str
    value: str
    bank: str
    payment_methods: list[str]


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
    captcha_passed: bool


class SettingsStore:
    def __init__(self, path: Path, default_commission: float, env_links: dict[str, str]):
        self.path = path
        default_methods = ["На карту РФ 🇷🇺"]
        self.data: SettingsData = {
            "commission_percent": float(default_commission),
            "links": dict(env_links),
            "requisites": {
                "mode": "single",
                "value": "2204321092962971",
                "bank": "Озон Банк",
                "payment_methods": default_methods,
            },
        }
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            raw = cast(dict[str, object], json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            raw = {}
        commission_raw = raw.get("commission_percent")
        if isinstance(commission_raw, (int, float)):
            self.data["commission_percent"] = float(commission_raw)
        links_raw = raw.get("links")
        links = dict(self.data["links"])
        if isinstance(links_raw, dict):
            for k, v in links_raw.items():
                if isinstance(k, str) and isinstance(v, str):
                    links[k] = v
        self.data["links"] = links
        req_raw = raw.get("requisites")
        req = dict(self.data["requisites"])
        if isinstance(req_raw, dict):
            req_obj = cast(dict[str, object], req_raw)
            mode_raw = req_obj.get("mode")
            if isinstance(mode_raw, str) and mode_raw in {"single"}:
                req["mode"] = mode_raw
            value_raw = req_obj.get("value")
            if isinstance(value_raw, str) and value_raw.strip():
                req["value"] = value_raw.strip()
            bank_raw = req_obj.get("bank")
            if isinstance(bank_raw, str) and bank_raw.strip():
                req["bank"] = bank_raw.strip()
            methods_raw = req_obj.get("payment_methods")
            if isinstance(methods_raw, list):
                methods = [item.strip() for item in methods_raw if isinstance(item, str) and item.strip()]
                if methods:
                    req["payment_methods"] = methods
        self.data["requisites"] = cast(RequisitesData, req)
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def commission_percent(self) -> float:
        return self.data["commission_percent"]

    def set_commission(self, value: float) -> None:
        self.data["commission_percent"] = float(str(value).replace(",", ".").replace(" ", ""))
        self.save()

    def link(self, key: str) -> str:
        return self.data["links"].get(key, "")

    def set_link(self, key: str, value: str) -> None:
        self.data["links"][key] = value
        self.save()

    def all_links(self) -> dict[str, str]:
        return dict(self.data["links"])

    @property
    def requisites_mode(self) -> str:
        return self.data["requisites"]["mode"]

    @property
    def requisites_value(self) -> str:
        return self.data["requisites"]["value"]

    @property
    def requisites_bank(self) -> str:
        return self.data["requisites"]["bank"]

    def payment_methods(self) -> list[str]:
        return list(self.data["requisites"]["payment_methods"])

    def set_requisites_value(self, value: str) -> None:
        self.data["requisites"]["value"] = value
        self.save()

    def set_requisites_bank(self, value: str) -> None:
        self.data["requisites"]["bank"] = value
        self.save()

    def add_payment_method(self, value: str) -> None:
        self.data["requisites"]["payment_methods"].append(value)
        self.save()

    def delete_payment_method(self, index: int) -> bool:
        methods = self.data["requisites"]["payment_methods"]
        if len(methods) <= 1:
            return False
        if index < 0 or index >= len(methods):
            return False
        methods.pop(index)
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
            "captcha_passed": False,
        }

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            raw = cast(dict[str, object], json.loads(self.path.read_text(encoding="utf-8")))
        except Exception:
            self.data = {}
            self.save()
            return
        parsed: dict[str, UserProfile] = {}
        for k, v in raw.items():
            if not isinstance(k, str) or not isinstance(v, dict):
                continue
            item = cast(dict[str, object], v)
            profile = self._default_profile()
            if isinstance(item.get("trades_total"), int):
                profile["trades_total"] = cast(int, item["trades_total"])
            if isinstance(item.get("invited"), int):
                profile["invited"] = cast(int, item["invited"])
            if isinstance(item.get("turnover_rub"), (int, float)):
                profile["turnover_rub"] = float(cast(float | int, item["turnover_rub"]))
            if isinstance(item.get("bonus_balance"), (int, float)):
                profile["bonus_balance"] = float(cast(float | int, item["bonus_balance"]))
            if isinstance(item.get("captcha_passed"), bool):
                profile["captcha_passed"] = cast(bool, item["captcha_passed"])
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
            parsed[k] = profile
        self.data = parsed
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def user(self, user_id: int) -> UserProfile:
        key = str(user_id)
        if key not in self.data:
            self.data[key] = self._default_profile()
            self.save()
        return self.data[key]

    def record_trade(self, user_id: int, side: str, coin: str, amount_coin: float, amount_rub: float) -> None:
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

    def captcha_passed(self, user_id: int) -> bool:
        return bool(self.user(user_id).get("captcha_passed", False))

    def set_captcha_passed(self, user_id: int, passed: bool = True) -> None:
        profile = self.user(user_id)
        profile["captcha_passed"] = bool(passed)
        self.save()
