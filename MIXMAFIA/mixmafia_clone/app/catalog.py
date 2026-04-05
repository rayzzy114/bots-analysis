from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .constants import LINK_LABELS, SELL_WALLET_LABELS
from .fingerprints import state_fingerprint

SPECIAL_INPUT_ACTIONS = ("<manual-input>", "<input>")
URL_IN_TEXT_RE = re.compile(r"https?://[^\s<>)\]\}\"']+")
HANDLE_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,})")
CARD_RE = re.compile(r"\b\d{4}(?:[ \-]?\d{4}){3}\b")
OPERATOR_HINTS = (
    "support",
    "поддерж",
    "оператор",
    "помощ",
    "тикет",
    "ticket",
)
LINK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "faq": ("faq",),
    "channel": ("канал", "channel"),
    "chat": ("чат", "chat"),
    "review_form": ("форма", "оставить отзыв", "review form"),
    "reviews": ("отзыв", "reviews", "review"),
    "manager": ("менеджер", "manager"),
    "terms": ("услов", "terms"),
    "exchange": ("обменник", "перейти"),
}
BTC_ADDRESS_RE = re.compile(r"\b(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{20,}\b")
ETH_ADDRESS_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
TRX_ADDRESS_RE = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{25,34}\b")
LTC_ADDRESS_RE = re.compile(r"\b[LM3][a-km-zA-HJ-NP-Z1-9]{26,40}\b")
XMR_ADDRESS_RE = re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{90,110}\b")
TON_ADDRESS_RE = re.compile(r"\b(?:EQ|UQ)[A-Za-z0-9_-]{40,60}\b")


@dataclass
class FlowCatalog:
    raw_dir: Path
    media_dir: Path
    states: dict[str, dict[str, Any]]
    edges: list[dict[str, str]]
    events: list[dict[str, Any]]
    links: list[str]
    fingerprints: dict[str, str]
    transition_index: dict[str, dict[str, list[str]]]
    observed_counts: dict[tuple[str, str, str], int]
    state_layout_signatures: dict[str, str]
    layout_transition_index: dict[str, dict[str, list[str]]]
    global_action_targets: dict[str, list[str]]
    state_first_lines: dict[str, str]
    exchange_state_id: str
    unblock_state_id: str
    partner_state_id: str
    receive_currency_state_id: str
    receive_address_state_by_currency: dict[str, str]
    receive_amount_target_by_source: dict[str, str]
    city_choice_target_by_source: dict[str, str]
    start_state_id: str
    exchange_info_state_id: str
    about_state_id: str
    reviews_state_id: str
    tariffs_state_id: str
    operator_url_aliases: tuple[str, ...]
    operator_handle_aliases: tuple[str, ...]
    detected_requisites: tuple[str, ...]
    link_url_aliases: dict[str, tuple[str, ...]]
    sell_wallet_aliases: dict[str, tuple[str, ...]]
    default_operator_url: str

    @classmethod
    def from_directory(cls, raw_dir: Path, media_dir: Path) -> "FlowCatalog":
        flow = _load_json(raw_dir / "flow.json")
        edges = _load_json(raw_dir / "edges.json")
        events = _load_json(raw_dir / "events.json")
        links = _load_json(raw_dir / "links.json")

        if not isinstance(flow, dict):
            raise RuntimeError("flow.json must be a dict")
        if not isinstance(edges, list):
            raise RuntimeError("edges.json must be a list")
        if not isinstance(events, list):
            raise RuntimeError("events.json must be a list")
        if not isinstance(links, list):
            raise RuntimeError("links.json must be a list")

        states: dict[str, dict[str, Any]] = {
            str(sid): dict(state) for sid, state in flow.items() if isinstance(state, dict)
        }
        normalized_edges = _normalize_edges(edges)
        transition_index = _build_transition_index(normalized_edges)
        observed_counts = _build_observed_counts(events)
        state_layout_signatures = {
            sid: _state_layout_signature(state) for sid, state in states.items()
        }
        layout_transition_index = _build_layout_transition_index(
            normalized_edges,
            state_layout_signatures=state_layout_signatures,
        )
        global_action_targets = _build_global_action_targets(normalized_edges)
        state_first_lines = {sid: _state_first_line(state) for sid, state in states.items()}
        exchange_state_id = _detect_exchange_state_id(state_first_lines)
        unblock_state_id = _detect_unblock_state_id(states)
        partner_state_id = _detect_partner_state_id(states)
        receive_currency_state_id = _detect_receive_currency_state_id(state_first_lines)
        receive_address_state_by_currency = _build_receive_address_state_by_currency(states)
        receive_amount_target_by_source = _build_receive_amount_target_by_source(
            normalized_edges,
            state_first_lines=state_first_lines,
        )
        city_choice_target_by_source = _build_city_choice_target_by_source(
            normalized_edges,
            state_first_lines=state_first_lines,
        )
        start_state_id = _resolve_start_state(events, states)
        fingerprints = {sid: state_fingerprint(state) for sid, state in states.items()}
        exchange_info_state_id = _detect_exchange_info_state_id(states)
        about_state_id = _detect_about_state_id(states)
        reviews_state_id = _detect_reviews_state_id(states)
        tariffs_state_id = _detect_tariffs_state_id(states)
        operator_url_aliases, operator_handle_aliases = _detect_operator_aliases(states)
        detected_requisites = _detect_requisites(states)
        link_url_aliases = _detect_link_aliases(states, operator_url_aliases)
        sell_wallet_aliases = _detect_sell_wallet_aliases(states)
        default_operator_url = operator_url_aliases[0] if operator_url_aliases else ""

        return cls(
            raw_dir=raw_dir,
            media_dir=media_dir,
            states=states,
            edges=normalized_edges,
            events=events,
            links=[str(x) for x in links],
            fingerprints=fingerprints,
            transition_index=transition_index,
            observed_counts=observed_counts,
            state_layout_signatures=state_layout_signatures,
            layout_transition_index=layout_transition_index,
            global_action_targets=global_action_targets,
            state_first_lines=state_first_lines,
            exchange_state_id=exchange_state_id,
            unblock_state_id=unblock_state_id,
            partner_state_id=partner_state_id,
            receive_currency_state_id=receive_currency_state_id,
            receive_address_state_by_currency=receive_address_state_by_currency,
            receive_amount_target_by_source=receive_amount_target_by_source,
            city_choice_target_by_source=city_choice_target_by_source,
            start_state_id=start_state_id,
            exchange_info_state_id=exchange_info_state_id,
            about_state_id=about_state_id,
            reviews_state_id=reviews_state_id,
            tariffs_state_id=tariffs_state_id,
            operator_url_aliases=operator_url_aliases,
            operator_handle_aliases=operator_handle_aliases,
            detected_requisites=detected_requisites,
            link_url_aliases=link_url_aliases,
            sell_wallet_aliases=sell_wallet_aliases,
            default_operator_url=default_operator_url,
        )

    def resolve_action(
        self,
        state_id: str,
        action_text: str,
        *,
        is_text_input: bool = False,
        history: list[str] | None = None,
    ) -> str | None:
        action = (action_text or "").strip()
        if action == "💵 Партнерам" and self.partner_state_id:
            # Captured edge may pass through welcome + next-message; route directly to partner screen.
            return self.partner_state_id
        if state_id == self.receive_currency_state_id:
            explicit_target = self.receive_address_state_by_currency.get(action)
            if explicit_target:
                return explicit_target

        action_map = self.transition_index.get(state_id) or {}

        candidates: list[str] = []
        if action:
            candidates.append(action)
        if is_text_input:
            candidates.extend(SPECIAL_INPUT_ACTIONS)

        for candidate in candidates:
            targets = action_map.get(candidate)
            if targets:
                return self._pick_target(state_id, candidate, targets)

        inferred = self._resolve_inferred_action(state_id, action, history=history)
        if inferred:
            return inferred

        return None

    def resolve_system_next(self, state_id: str) -> str | None:
        action_map = self.transition_index.get(state_id) or {}
        targets = action_map.get("<next-message>")
        if not targets:
            return None
        return self._pick_target(state_id, "<next-message>", targets)

    def state_accepts_input(self, state_id: str) -> bool:
        action_map = self.transition_index.get(state_id) or {}
        return any(key in action_map for key in SPECIAL_INPUT_ACTIONS)

    def is_address_input_state(self, state_id: str) -> bool:
        """True if this state asks the user to enter a crypto address."""
        state = self.states.get(state_id)
        if not state:
            return False
        text = str(state.get("text") or "")
        has_buttons = bool(state.get("buttons") or state.get("button_rows"))
        return "Введите адрес" in text and not has_buttons

    def get_address_input_next(self, state_id: str) -> str | None:
        """For address-input states, returns the first outgoing transition target."""
        action_map = self.transition_index.get(state_id) or {}
        for _action, targets in action_map.items():
            if targets:
                return targets[0]
        return None

    def state_has_buttons(self, state_id: str) -> bool:
        state = self.states.get(state_id) or {}
        rows = state.get("button_rows")
        if isinstance(rows, list) and rows:
            return True
        buttons = state.get("buttons")
        return isinstance(buttons, list) and bool(buttons)

    def _pick_target(self, state_id: str, action: str, targets: list[str]) -> str:
        if len(targets) == 1:
            return targets[0]
        ranked = sorted(
            targets,
            key=lambda dst: (
                self.observed_counts.get((state_id, action, dst), 0),
                -targets.index(dst),
            ),
            reverse=True,
        )
        return ranked[0]

    def _resolve_inferred_action(
        self,
        state_id: str,
        action: str,
        *,
        history: list[str] | None,
    ) -> str | None:
        if not action:
            return None

        normalized = action.strip()
        if not normalized:
            return None

        if normalized in {"🏠 Главная", "В начало"}:
            return self.start_state_id

        if normalized == "🧹 Чистка BTC" and self.receive_currency_state_id:
            return self.receive_currency_state_id

        if state_id == self.receive_currency_state_id:
            explicit_target = self.receive_address_state_by_currency.get(normalized)
            if explicit_target:
                return explicit_target

        if normalized == "💵 Партнерам" and self.partner_state_id:
            return self.partner_state_id

        if normalized == "💼 Обмен" and self.exchange_info_state_id:
            return self.exchange_info_state_id

        if normalized == "🎩 О нас" and self.about_state_id:
            return self.about_state_id

        if normalized == "Отзывы" and state_id == self.about_state_id and self.reviews_state_id:
            return self.reviews_state_id

        if normalized == "Тарифы" and state_id == self.about_state_id and self.tariffs_state_id:
            return self.tariffs_state_id

        if normalized == "Назад":
            if state_id in {self.reviews_state_id, self.tariffs_state_id} and self.about_state_id:
                return self.about_state_id
            if history and len(history) >= 2:
                # History-aware fallback is safer than a global "Назад" guess.
                return history[-2]

        if (
            normalized == "🔐 Bitmafia Unblock - Разблокировка бирж!"
            and self.unblock_state_id
        ):
            return self.unblock_state_id

        first_line = (self.state_first_lines.get(state_id) or "").lower()

        if normalized == "Обменять" and "хотите обменять средства" in first_line:
            if self.exchange_state_id:
                return self.exchange_state_id

        if (
            "выберите валюту которую вы получаете" in first_line
            and normalized != "Назад"
        ):
            target = self.receive_amount_target_by_source.get(state_id)
            if target:
                return target

        if "введите желаемый город" in first_line and normalized != "Назад":
            target = self.city_choice_target_by_source.get(state_id)
            if target:
                return target

        if "выберите валюту которую вы отда" in first_line:
            action_map = self.transition_index.get(state_id) or {}
            if normalized == "TRX TRON":
                targets = action_map.get("Tether TRC-20") or []
                if targets:
                    return targets[0]
            if normalized == "Litecoin":
                targets = action_map.get("Bitcoin") or []
                if targets:
                    return targets[0]

        layout_signature = self.state_layout_signatures.get(state_id, "")
        if layout_signature:
            by_layout = self.layout_transition_index.get(layout_signature) or {}
            layout_targets = by_layout.get(normalized) or []
            if len(layout_targets) == 1:
                return layout_targets[0]
            if len(layout_targets) > 1:
                # Ambiguous inferred route: better not move than move to a wrong branch.
                return None

        global_targets = self.global_action_targets.get(normalized) or []
        if len(global_targets) == 1:
            return global_targets[0]

        return None


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_edges(edges: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in edges:
        if not isinstance(row, dict):
            continue
        src = str(row.get("from") or "")
        action = str(row.get("action") or "")
        dst = str(row.get("to") or "")
        if not src or not dst:
            continue
        out.append({"from": src, "action": action, "to": dst})
    return out


def _build_transition_index(edges: list[dict[str, str]]) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in edges:
        src = row["from"]
        action = row["action"]
        dst = row["to"]
        lst = index[src][action]
        if dst not in lst:
            lst.append(dst)
    return {src: dict(actions) for src, actions in index.items()}


def _build_layout_transition_index(
    edges: list[dict[str, str]],
    *,
    state_layout_signatures: dict[str, str],
) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in edges:
        src = row["from"]
        action = row["action"]
        dst = row["to"]
        if action.startswith("<"):
            continue
        layout_signature = state_layout_signatures.get(src, "")
        if not layout_signature:
            continue
        lst = index[layout_signature][action]
        if dst not in lst:
            lst.append(dst)
    return {layout: dict(actions) for layout, actions in index.items()}


def _build_global_action_targets(edges: list[dict[str, str]]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = defaultdict(list)
    for row in edges:
        action = row["action"]
        dst = row["to"]
        if action.startswith("<"):
            continue
        lst = index[action]
        if dst not in lst:
            lst.append(dst)
    return dict(index)


def _build_observed_counts(events: list[dict[str, Any]]) -> dict[tuple[str, str, str], int]:
    counts: Counter[tuple[str, str, str]] = Counter()
    prev_state: str | None = None

    for event in events:
        if not isinstance(event, dict):
            continue
        curr_state = str(event.get("state_id") or "")
        action = str(event.get("from_action") or "")
        if prev_state and curr_state and action:
            counts[(prev_state, action, curr_state)] += 1
        prev_state = curr_state or prev_state

    return dict(counts)


def _resolve_start_state(events: list[dict[str, Any]], states: dict[str, dict[str, Any]]) -> str:
    start_hits: Counter[str] = Counter()
    for event in events:
        if not isinstance(event, dict):
            continue
        if str(event.get("from_action") or "") != "/start":
            continue
        state_id = str(event.get("state_id") or "")
        if state_id:
            start_hits[state_id] += 1

    if start_hits:
        return start_hits.most_common(1)[0][0]

    if states:
        return next(iter(states.keys()))
    raise RuntimeError("No states found in captured flow")


def _iter_button_rows(state: dict[str, Any]) -> list[list[dict[str, Any]]]:
    rows = state.get("button_rows")
    parsed: list[list[dict[str, Any]]] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, list):
                continue
            parsed_row = [btn for btn in row if isinstance(btn, dict)]
            if parsed_row:
                parsed.append(parsed_row)
    if parsed:
        return parsed

    fallback = state.get("buttons")
    if isinstance(fallback, list) and fallback:
        return [[btn for btn in fallback if isinstance(btn, dict)]]
    return []


def _state_text_blob(state: dict[str, Any]) -> str:
    parts = [
        str(state.get("text") or ""),
        str(state.get("text_html") or ""),
        str(state.get("text_markdown") or ""),
    ]
    return "\n".join(parts)


def _state_layout_signature(state: dict[str, Any]) -> str:
    rows = _iter_button_rows(state)
    if not rows:
        return ""
    serialized_rows: list[str] = []
    for row in rows:
        serialized_buttons = []
        for btn in row:
            btn_type = str(btn.get("type") or "")
            text = str(btn.get("text") or "").strip()
            serialized_buttons.append(f"{btn_type}:{text}")
        serialized_rows.append("|".join(serialized_buttons))
    return "||".join(serialized_rows)


def _state_first_line(state: dict[str, Any]) -> str:
    return str(state.get("text") or "").splitlines()[0].strip()


def _detect_exchange_state_id(state_first_lines: dict[str, str]) -> str:
    for sid, first_line in state_first_lines.items():
        if first_line == "Выберите валюту которую вы отдаёте:":
            return sid
    return ""


def _detect_receive_currency_state_id(state_first_lines: dict[str, str]) -> str:
    for sid, first_line in state_first_lines.items():
        if first_line == "Выберите валюту, которую хотите получить":
            return sid
    return ""


def _detect_unblock_state_id(states: dict[str, dict[str, Any]]) -> str:
    exact = "💼 Bitmafia Unblock — эксперты по разблокировке крипты"
    for sid, state in states.items():
        if _state_first_line(state) == exact:
            return sid
    for sid, state in states.items():
        text = _state_text_blob(state).lower()
        if "bitmafia unlock" in text and "разблокировке крипты" in text:
            return sid
    return ""


def _detect_partner_state_id(states: dict[str, dict[str, Any]]) -> str:
    exact_prefix = "Вы можете приглашать участников по собственной персональной ссылке"
    for sid, state in states.items():
        first_line = _state_first_line(state)
        if first_line.startswith(exact_prefix):
            return sid
    for sid, state in states.items():
        text = _state_text_blob(state).lower()
        if "партнерская ссылка" in text and "минимальная сумма вывода" in text:
            return sid
    return ""


def _detect_exchange_info_state_id(states: dict[str, dict[str, Any]]) -> str:
    exact_prefix = "Если вы желаете купить или продать криптовалюту"
    for sid, state in states.items():
        if _state_first_line(state).startswith(exact_prefix):
            return sid
    return ""


def _detect_about_state_id(states: dict[str, dict[str, Any]]) -> str:
    exact_prefix = "MixMafia — Ваш надежный финансовый партнер."
    for sid, state in states.items():
        if _state_first_line(state).startswith(exact_prefix):
            return sid
    return ""


def _detect_reviews_state_id(states: dict[str, dict[str, Any]]) -> str:
    exact_prefix = "Посмотреть или оставить отзывы о нашей работе"
    for sid, state in states.items():
        if _state_first_line(state).startswith(exact_prefix):
            return sid
    return ""


def _detect_tariffs_state_id(states: dict[str, dict[str, Any]]) -> str:
    for sid, state in states.items():
        if _state_first_line(state) == "BTC - Любая доступная монета":
            return sid
    return ""


def _build_receive_amount_target_by_source(
    edges: list[dict[str, str]],
    *,
    state_first_lines: dict[str, str],
) -> dict[str, str]:
    by_source: dict[str, set[str]] = defaultdict(set)
    for row in edges:
        src = row["from"]
        dst = row["to"]
        src_first = (state_first_lines.get(src) or "").lower()
        dst_first = (state_first_lines.get(dst) or "").lower()
        if "выберите валюту которую вы получаете" not in src_first:
            continue
        if "в какой валюте вы хотите указать сумму?" not in dst_first:
            continue
        by_source[src].add(dst)

    result: dict[str, str] = {}
    for src, targets in by_source.items():
        if len(targets) == 1:
            result[src] = next(iter(targets))
    return result


def _build_receive_address_state_by_currency(
    states: dict[str, dict[str, Any]],
) -> dict[str, str]:
    result: dict[str, str] = {}
    pattern = re.compile(r"Вы выбрали получить:\s*(.+)")
    for sid, state in states.items():
        text = str(state.get("text") or "")
        if "Введите адрес для получения чистых средств" not in text:
            continue
        match = pattern.search(text)
        if not match:
            continue
        currency = match.group(1).strip()
        if currency and currency not in result:
            result[currency] = sid
    return result


def _build_city_choice_target_by_source(
    edges: list[dict[str, str]],
    *,
    state_first_lines: dict[str, str],
) -> dict[str, str]:
    by_source: dict[str, set[str]] = defaultdict(set)
    for row in edges:
        src = row["from"]
        action = row["action"]
        dst = row["to"]
        src_first = (state_first_lines.get(src) or "").lower()
        if "введите желаемый город" not in src_first:
            continue
        if action.startswith("<") or action == "Назад":
            continue
        by_source[src].add(dst)

    result: dict[str, str] = {}
    for src, targets in by_source.items():
        if len(targets) == 1:
            result[src] = next(iter(targets))
    return result


def _normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""
    if value.endswith("/"):
        value = value[:-1]
    return value


def _is_operator_context(button_text: str) -> bool:
    button_lower = (button_text or "").lower()
    return any(hint in button_lower for hint in OPERATOR_HINTS)


def _extract_tg_handle(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().strip()
    if host.startswith("www."):
        host = host[4:]
    if host not in {"t.me", "telegram.me"}:
        return ""
    path = (parsed.path or "").strip("/")
    if not path:
        return ""
    return path.split("/")[0]


def _detect_operator_aliases(states: dict[str, dict[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    url_aliases: set[str] = set()
    handle_aliases: set[str] = set()

    for state in states.values():
        for row in _iter_button_rows(state):
            for btn in row:
                url = _normalize_url(str(btn.get("url") or ""))
                if not url:
                    continue
                button_text = str(btn.get("text") or "")
                if _extract_tg_handle(url) and _is_operator_context(button_text):
                    url_aliases.add(url)

    if not url_aliases:
        for state in states.values():
            for row in _iter_button_rows(state):
                for btn in row:
                    url = _normalize_url(str(btn.get("url") or ""))
                    button_text = str(btn.get("text") or "")
                    if url and "тикет" in button_text.lower():
                        url_aliases.add(url)

    for url in url_aliases:
        handle = _extract_tg_handle(url)
        if not handle:
            continue
        lower = handle.lower()
        handle_aliases.add(lower)
        no_underscores = lower.replace("_", "")
        if no_underscores:
            handle_aliases.add(no_underscores)

    if handle_aliases:
        normalized_known = {h.replace("_", "") for h in handle_aliases}
        for state in states.values():
            text = _state_text_blob(state)
            for handle in HANDLE_RE.findall(text):
                candidate = handle.lower()
                if candidate.replace("_", "") in normalized_known:
                    handle_aliases.add(candidate)

    return tuple(sorted(url_aliases)), tuple(sorted(handle_aliases))


def _detect_requisites(states: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    requisites: set[str] = set()
    for state in states.values():
        text = _state_text_blob(state)
        for match in CARD_RE.findall(text):
            requisites.add(match)
    return tuple(sorted(requisites))


def _detect_link_aliases(
    states: dict[str, dict[str, Any]],
    operator_url_aliases: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    aliases: dict[str, set[str]] = {key: set() for key in LINK_LABELS}

    for operator_url in operator_url_aliases:
        if operator_url and "operator" in aliases:
            aliases["operator"].add(operator_url)

    for state in states.values():
        for row in _iter_button_rows(state):
            for btn in row:
                url = _normalize_url(str(btn.get("url") or ""))
                if not url:
                    continue
                text = str(btn.get("text") or "")
                key = _match_link_key(text)
                if key and key in aliases:
                    aliases[key].add(url)

    return {key: tuple(sorted(values)) for key, values in aliases.items()}


def _match_link_key(button_text: str) -> str | None:
    text = (button_text or "").strip().lower()
    if not text:
        return None

    if _is_operator_context(text):
        return "operator"

    for key, label in sorted(LINK_LABELS.items(), key=lambda kv: len(kv[1]), reverse=True):
        if label.lower() in text:
            return key
        if key.replace("_", " ") in text:
            return key

    for keyword in LINK_KEYWORDS["review_form"]:
        if keyword in text:
            return "review_form"

    for key in ("faq", "channel", "chat", "reviews", "manager", "terms", "exchange"):
        for keyword in LINK_KEYWORDS.get(key, ()):
            if keyword in text:
                return key
    return None


def _detect_sell_wallet_aliases(states: dict[str, dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    # Initialise with all SELL_WALLET_LABELS keys, plus any extra keys that the
    # detection logic may write to (e.g. "btc", "ton", "usdt_bep20", "trx").
    # Using setdefault-style access via a defaultdict avoids KeyError when a
    # particular coin key is absent from this bot's SELL_WALLET_LABELS.
    aliases: dict[str, set[str]] = {key: set() for key in SELL_WALLET_LABELS}

    def _add(key: str, address: str) -> None:
        # Remap generic "btc" to "btc_clean" if that's how this bot labels it.
        if key == "btc" and "btc_clean" in aliases:
            key = "btc_clean"
        if key in aliases:
            aliases[key].add(address)

    for state in states.values():
        text = _state_text_blob(state)
        for address in BTC_ADDRESS_RE.findall(text):
            _add("btc", address)
        for address in LTC_ADDRESS_RE.findall(text):
            _add("ltc", address)
        for address in XMR_ADDRESS_RE.findall(text):
            _add("xmr", address)
        for address in TON_ADDRESS_RE.findall(text):
            _add("ton", address)
        for address in ETH_ADDRESS_RE.findall(text):
            target_key = "usdt_bep20" if _is_usdt_bsc_context(text) else "eth"
            _add(target_key, address)
        for address in TRX_ADDRESS_RE.findall(text):
            target_key = "usdt_trc20" if _is_usdt_trc_context(text) else "trx"
            _add(target_key, address)

    return {key: tuple(sorted(values)) for key, values in aliases.items()}


def _is_usdt_trc_context(text: str) -> bool:
    lowered = (text or "").lower()
    return "usdt" in lowered and ("trc20" in lowered or "trx" in lowered)


def _is_usdt_bsc_context(text: str) -> bool:
    lowered = (text or "").lower()
    return "usdt" in lowered and ("bsc" in lowered or "bep20" in lowered)
