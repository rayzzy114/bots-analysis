from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(str(value).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None


@dataclass
class CompiledState:
    state_id: str
    text: str
    text_html: str
    text_markdown: str
    entities: list[dict[str, Any]]
    entity_types: list[str]
    button_rows: list[list[dict[str, Any]]]
    interactive_actions: list[str]
    media_ref: str | None
    media_file: str | None
    media_exists: bool
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TransitionTarget:
    to_state: str
    count: int
    weight: float
    confidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "to_state": self.to_state,
            "count": self.count,
            "weight": self.weight,
            "confidence": self.confidence,
        }


@dataclass
class QuoteRecord:
    state_id: str
    operation: str
    coin: str
    coin_amount: float
    rub_amount: float
    net_amount: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromoRecord:
    state_id: str
    coin: str
    coin_amount: float
    pay_before: float
    pay_after: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OrderTemplateRecord:
    state_id: str
    coin: str
    sold_amount_raw: str
    payout_rub: float
    requisites_label: str
    requisites_value: str
    source_text: str
    buttons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UserSession:
    user_id: int
    current_state_id: str
    history: list[str] = field(default_factory=list)
    pending_operation: str | None = None
    pending_coin: str | None = None
    pending_amount_raw: str | None = None
    pending_payment_method: str | None = None
    pending_wallet: str | None = None
    promo_applied: bool | None = None
    last_quote_state_id: str | None = None
    last_quote_coin_amount: float | None = None
    last_quote_rub_amount: float | None = None
    last_quote_net_amount: float | None = None
    last_order_id: str | None = None
    updated_at: str = field(default_factory=utc_now_iso)

    def push_state(self, state_id: str, limit: int) -> None:
        self.history.append(state_id)
        if len(self.history) > limit:
            self.history = self.history[-limit:]
        self.current_state_id = state_id
        self.updated_at = utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UserSession":
        return cls(
            user_id=_as_int(payload.get("user_id")),
            current_state_id=str(payload.get("current_state_id") or ""),
            history=[str(x) for x in payload.get("history", [])],
            pending_operation=payload.get("pending_operation"),
            pending_coin=payload.get("pending_coin"),
            pending_amount_raw=payload.get("pending_amount_raw"),
            pending_payment_method=payload.get("pending_payment_method"),
            pending_wallet=payload.get("pending_wallet"),
            promo_applied=(bool(payload.get("promo_applied")) if payload.get("promo_applied") is not None else None),
            last_quote_state_id=payload.get("last_quote_state_id"),
            last_quote_coin_amount=_as_float(payload.get("last_quote_coin_amount")),
            last_quote_rub_amount=_as_float(payload.get("last_quote_rub_amount")),
            last_quote_net_amount=_as_float(payload.get("last_quote_net_amount")),
            last_order_id=payload.get("last_order_id"),
            updated_at=str(payload.get("updated_at") or utc_now_iso()),
        )


@dataclass
class Order:
    order_id: str
    user_id: int
    operation: str
    coin: str
    input_amount: float
    output_amount: float
    pay_amount: float
    net_amount: float | None
    payment_method: str
    wallet_or_requisites: str
    status: str
    created_at: str
    expires_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Order":
        return cls(
            order_id=str(payload["order_id"]),
            user_id=int(payload["user_id"]),
            operation=str(payload["operation"]),
            coin=str(payload["coin"]),
            input_amount=float(payload["input_amount"]),
            output_amount=float(payload["output_amount"]),
            pay_amount=float(payload["pay_amount"]),
            net_amount=float(payload["net_amount"]) if payload.get("net_amount") is not None else None,
            payment_method=str(payload.get("payment_method") or ""),
            wallet_or_requisites=str(payload.get("wallet_or_requisites") or ""),
            status=str(payload["status"]),
            created_at=str(payload["created_at"]),
            expires_at=str(payload["expires_at"]),
            updated_at=str(payload["updated_at"]),
        )
