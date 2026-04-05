from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class LinkDefinition:
    key: str
    label: str
    default: str = ""
    env_key: str | None = None

    @property
    def resolved_env_key(self) -> str:
        return self.env_key or f"{self.key.upper()}_LINK"


@dataclass(frozen=True, slots=True)
class AdminKitConfig:
    env_path: Path
    data_dir: Path
    link_definitions: Sequence[LinkDefinition]
    default_commission: float = 5.0
    admin_ids: Sequence[int] = ()
    sell_wallet_labels: Mapping[str, str] = field(default_factory=dict)
    enable_users: bool = True
    enable_orders: bool = True
