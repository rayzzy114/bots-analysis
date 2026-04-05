from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .flow_loader import load_raw_bundle
from .models import CompiledState, OrderTemplateRecord, PromoRecord, QuoteRecord

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")
NUMBER_RE = re.compile(r"[-+]?\d[\d\s.,]*")

PROMPT_RE = re.compile(
    r"сколько ты хочешь\s+(купить|продать).*?в\s+([A-Za-zА-Яа-я()0-9]+)",
    re.IGNORECASE | re.DOTALL,
)
QUOTE_RE = re.compile(
    r"Сумма к получению:\s*(?P<receive>[^\n]+?)\s+Сумма к оплате:\s*(?P<pay>[^\n]+)(?:\nСумма к зачислению:\s*(?P<net>[^\n]+))?",
    re.IGNORECASE,
)
PROMO_RE = re.compile(
    r"Ты покупаешь\s*(?P<coin>[^:]+):\s*(?P<coin_amount>[\d.,]+).*?Тебе нужно будет оплатить:\s*(?P<pay_before>[\d\s.,]+)\s+(?P<pay_after>[\d\s.,]+)",
    re.IGNORECASE | re.DOTALL,
)
ORDER_RE = re.compile(
    r"Заявка №\s*(?P<order_id>\d+).*?Продаете:\s*(?P<sold>[^\n]+).*?📲СБП реквизиты:\s*(?P<sbp>\d+).*?Получаете:\s*(?P<payout>[\d\s.,]+)\s*₽.*?Реквизиты для перевода\s*(?P<label>[^:]+):\s*(?P<requisites>[A-Za-z0-9]+)",
    re.IGNORECASE | re.DOTALL,
)

COIN_CANON = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "litecoin": "LTC",
    "ltc": "LTC",
    "usdt": "USDT",
    "usdttrc20": "USDT",
    "usdt(trc20)": "USDT",
    "trx": "TRX",
    "tron": "TRX",
    "trontrx": "TRX",
    "tron(trx)": "TRX",
    "xmr": "XMR",
    "monero": "XMR",
    "moneroxmr": "XMR",
    "monero(xmr)": "XMR",
    "eth": "ETH",
    "ethereum": "ETH",
    "sol": "SOL",
}

ACTION_COINS = {"btc", "bitcoin", "ltc", "litecoin", "usdt", "trx", "tron", "xmr", "monero", "eth", "sol"}
INPUT_HINTS = (
    "введите",
    "укажите",
    "напиши",
    "напишите",
    "кошелек",
    "кошел",
    "адрес",
    "реквизит",
    "карт",
    "номер",
    "send",
    "input",
    "enter",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text or "")}


def _norm_text(text: str) -> str:
    return " ".join(_tokens(text))


def _norm_coin(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9()]+", "", (value or "").strip().lower())
    if key in COIN_CANON:
        return COIN_CANON[key]
    # try removing parentheses
    key2 = re.sub(r"[\(\)]", "", key)
    return COIN_CANON.get(key2, (value or "").strip().upper())


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None
    match = NUMBER_RE.search(value)
    if not match:
        return None
    raw = match.group(0).replace(" ", "")
    if raw.count(",") and raw.count("."):
        raw = raw.replace(",", "")
    elif raw.count(","):
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_amount_asset(fragment: str) -> tuple[float | None, str]:
    text = (fragment or "").strip()
    amount = _parse_number(text)
    lowered = text.lower()
    if "₽" in text or "rub" in lowered or "руб" in lowered:
        return amount, "RUB"
    tokens = TOKEN_RE.findall(text)
    if not tokens:
        return amount, ""
    asset = _norm_coin(tokens[-1])
    return amount, asset


def _rows_for_state(state: dict[str, Any]) -> list[list[dict[str, Any]]]:
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

    fallback_buttons = state.get("buttons") or []
    flat_row = [btn for btn in fallback_buttons if isinstance(btn, dict)]
    if flat_row:
        return [flat_row]
    return []


def _interactive_actions(rows: list[list[dict[str, Any]]]) -> list[str]:
    seen: set[str] = set()
    actions: list[str] = []
    for row in rows:
        for btn in row:
            text = str(btn.get("text") or "").strip()
            if not text:
                continue
            if str(btn.get("type") or "") == "KeyboardButtonUrl":
                continue
            if text in seen:
                continue
            seen.add(text)
            actions.append(text)
    return actions


def _state_kind(text: str, rows: list[list[dict[str, Any]]], actions: list[str]) -> str:
    t = (text or "").lower()
    if "если бот завис" in t and actions:
        return "main_menu"
    if "сколько ты хочешь купить" in t:
        return "buy_amount_prompt"
    if "сколько ты хочешь продать" in t:
        return "sell_amount_prompt"
    if "какую крипту хочешь купить" in t:
        return "buy_coin_select"
    if "какую крипту хочешь продать" in t:
        return "sell_coin_select"
    if "сумма к получению" in t and "сумма к оплате" in t:
        return "quote"
    if "ты покупаешь" in t and "промокод" in t:
        return "promo_confirm"
    if "твоя заявка" in t and "выбери способ оплаты" in t:
        return "payment_method_select"
    if "введите" in t and "адрес кошелька" in t:
        return "wallet_prompt"
    if "поиск реквизита" in t or "поиск реквизитов" in t:
        return "order_searching"
    if "реквизиты найдены" in t:
        return "order_found"
    if "заявка была отменена" in t:
        return "order_cancelled"
    if "заявка №" in t:
        return "order_card"
    if "введите /start" in t and "ошибка" in t:
        return "error"
    if not rows and "mariobtcbot 24/7" in t:
        return "intro_banner"
    if "история сделок" in t and actions:
        return "history"
    return "info"


def _resolve_missing_media(
    state_id: str,
    states: dict[str, CompiledState],
    by_state: dict[str, dict[str, str]],
    default_next: dict[str, str],
) -> str | None:
    current = states[state_id]
    if current.media_exists:
        return current.media_file

    # Prefer immediate transition target with valid media.
    candidates: list[str] = []
    for action_targets in by_state.get(state_id, {}).values():
        target_state = states.get(action_targets)
        if target_state and target_state.media_exists and target_state.media_file:
            candidates.append(target_state.media_file)
    fallback_state = states.get(default_next.get(state_id, ""))
    if fallback_state and fallback_state.media_exists and fallback_state.media_file:
        candidates.append(fallback_state.media_file)
    if candidates:
        return Counter(candidates).most_common(1)[0][0]

    # Fallback to most frequent existing media in known menu/intro-like states.
    global_candidates: list[str] = []
    for state in states.values():
        if not state.media_exists or not state.media_file:
            continue
        if state.kind in {"intro_banner", "main_menu"}:
            global_candidates.append(state.media_file)
    if global_candidates:
        return Counter(global_candidates).most_common(1)[0][0]
    return None


@dataclass
class CandidateScore:
    action: str
    score: float
    reasons: list[str]


def _keyword_score(button_text: str, target_text: str) -> tuple[float, list[str]]:
    b = button_text.lower()
    t = target_text.lower()
    score = 0.0
    reasons: list[str] = []

    def hit(button_keywords: tuple[str, ...], target_keywords: tuple[str, ...], points: float, reason: str) -> None:
        nonlocal score
        if any(k in b for k in button_keywords) and any(k in t for k in target_keywords):
            score += points
            reasons.append(reason)

    hit(("куп",), ("куп", "покуп"), 2.0, "buy-intent")
    hit(("прод",), ("прод",), 2.0, "sell-intent")
    hit(("истор",), ("истор", "заявк", "время на оплату"), 2.0, "history-intent")
    hit(("бонус",), ("бонус",), 2.0, "bonus-intent")
    hit(("рефера", "приглас"), ("рефера", "приглас"), 2.0, "referral-intent")
    hit(("оператор", "контакт"), ("оператор", "контакт"), 2.0, "operator-intent")
    hit(("назад",), ("/start", "главн", "какую крипту", "какую операцию"), 1.5, "back-intent")
    hit(("оплатил",), ("поиск реквиз", "реквизиты", "ожидание"), 2.0, "payment-intent")

    b_tokens = _tokens(button_text)
    t_tokens = _tokens(target_text)
    coins = ACTION_COINS & b_tokens & t_tokens
    if coins:
        score += 2.0
        reasons.append(f"coin-overlap:{','.join(sorted(coins))}")
    return score, reasons


def _score_action(button_text: str, target_text: str) -> CandidateScore:
    score = 0.0
    reasons: list[str] = []
    b_norm = _norm_text(button_text)
    t_norm = _norm_text(target_text)

    if b_norm and b_norm in t_norm:
        score += 4.0
        reasons.append("button-text-in-target")

    overlap = _tokens(button_text) & _tokens(target_text)
    if overlap:
        score += min(3.0, 0.9 * len(overlap))
        reasons.append(f"token-overlap:{','.join(sorted(overlap))}")

    kw_score, kw_reasons = _keyword_score(button_text, target_text)
    score += kw_score
    reasons.extend(kw_reasons)

    return CandidateScore(action=button_text, score=score, reasons=reasons)


def _confidence(top: CandidateScore, second: CandidateScore | None, candidate_count: int) -> tuple[str, float]:
    if candidate_count <= 1:
        return "high", 0.95
    margin = top.score - (second.score if second else 0.0)
    if top.score >= 5.0 and margin >= 1.5:
        return "high", 0.85
    if top.score >= 2.5 and margin >= 0.7:
        return "medium", 0.65
    if top.score >= 1.0:
        return "low", 0.4
    return "low", 0.2


def _transition_weight(conf: str) -> float:
    if conf == "high":
        return 3.0
    if conf == "medium":
        return 2.0
    return 1.0


def _is_input_prompt(text: str, kind: str) -> bool:
    if kind in {"buy_amount_prompt", "sell_amount_prompt", "wallet_prompt"}:
        return True
    if kind in {
        "quote",
        "promo_confirm",
        "payment_method_select",
        "order_card",
        "order_searching",
        "order_found",
        "order_cancelled",
        "main_menu",
        "intro_banner",
        "history",
    }:
        return False
    t = (text or "").lower()
    if "сумма к получению" in t and "сумма к оплате" in t:
        return False
    if re.search(r"\b(введите|укажите|напиши|напишите|впишите|заполните)\b", t):
        return True
    return any(hint in t for hint in INPUT_HINTS)


def _action_key(action: str) -> str:
    if action == "__user_input__":
        return "input:any"
    if action == "__system__":
        return "system:auto"
    return f"button:{action}"


def infer_transitions(states: dict[str, CompiledState], edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inferred: list[dict[str, Any]] = []
    bucket: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, "weight": 0.0, "max_conf_score": 0.0, "conf_low": 0.0, "conf_medium": 0.0, "conf_high": 0.0}
    )
    default_next_count: Counter[tuple[str, str]] = Counter()

    for idx, edge in enumerate(edges):
        src_id = str(edge.get("from") or "")
        dst_id = str(edge.get("to") or "")
        src = states.get(src_id)
        dst = states.get(dst_id)
        if not src or not dst:
            continue

        src_text = src.text
        dst_text = dst.text
        actions = src.interactive_actions
        reasons: list[str] = []
        ranked: list[CandidateScore] = []

        inferred_action = "__system__"
        conf = "low"
        conf_score = 0.25

        if not actions:
            if _is_input_prompt(src_text, src.kind):
                inferred_action = "__user_input__"
                conf = "medium"
                conf_score = 0.6
                reasons.append("source-looks-like-input-prompt")
            elif src.kind in {"quote", "order_searching", "error", "order_found", "order_cancelled", "intro_banner"}:
                inferred_action = "__system__"
                conf = "medium"
                conf_score = 0.6
                reasons.append("non-interactive-system-transition")
            else:
                inferred_action = "__system__"
                conf = "low"
                conf_score = 0.3
                reasons.append("no-interactive-buttons-in-source")
        else:
            ranked = sorted(
                (_score_action(action, dst_text) for action in actions),
                key=lambda row: (row.score, row.action),
                reverse=True,
            )
            top = ranked[0]
            second = ranked[1] if len(ranked) > 1 else None
            is_input_state = _is_input_prompt(src_text, src.kind)
            explicitly_reflected = "button-text-in-target" in top.reasons or top.score >= 4.5

            if is_input_state and not explicitly_reflected:
                inferred_action = "__user_input__"
                conf = "medium"
                conf_score = 0.65
                reasons.append("input-prompt-overrides-weak-button-match")
                reasons.extend(top.reasons)
                if second:
                    reasons.append(f"margin={top.score - second.score:.2f}")
            else:
                inferred_action = top.action
                conf, conf_score = _confidence(top, second, len(actions))
                reasons.extend(top.reasons)
                if second:
                    reasons.append(f"margin={top.score - second.score:.2f}")

        action_key = _action_key(inferred_action)
        entry = bucket[(src_id, action_key, dst_id)]
        entry["count"] += 1.0
        entry["weight"] += _transition_weight(conf)
        entry["max_conf_score"] = max(entry["max_conf_score"], conf_score)
        entry[f"conf_{conf}"] += 1.0
        default_next_count[(src_id, dst_id)] += 1

        inferred.append(
            {
                "index": idx,
                "from": src_id,
                "to": dst_id,
                "original_action": str(edge.get("action") or ""),
                "inferred_action": inferred_action,
                "action_key": action_key,
                "confidence": conf,
                "confidence_score": conf_score,
                "reasons": reasons,
                "source_kind": src.kind,
                "target_kind": dst.kind,
                "source_text_preview": src_text.replace("\n", " ")[:160],
                "target_text_preview": dst_text.replace("\n", " ")[:160],
                "candidates": [
                    {
                        "action": c.action,
                        "score": round(c.score, 3),
                        "reasons": c.reasons,
                    }
                    for c in ranked[:8]
                ],
            }
        )

    transitions: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    by_state: dict[str, dict[str, str]] = defaultdict(dict)

    for (src_id, action_key, dst_id), stats in bucket.items():
        conf_votes = {"high": stats["conf_high"], "medium": stats["conf_medium"], "low": stats["conf_low"]}
        dominant_conf = max(conf_votes.items(), key=lambda item: item[1])[0]
        transitions[src_id][action_key].append(
            {
                "to_state": dst_id,
                "count": int(stats["count"]),
                "weight": round(stats["weight"], 3),
                "confidence": dominant_conf,
                "confidence_score": round(stats["max_conf_score"], 3),
            }
        )

    for src_id, action_map in transitions.items():
        for action_key, targets in action_map.items():
            targets.sort(
                key=lambda row: (row["weight"], row["count"], row["confidence_score"], row["to_state"]),
                reverse=True,
            )
            by_state[src_id][action_key] = targets[0]["to_state"]

    default_next: dict[str, str] = {}
    grouped_default: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for (src_id, dst_id), count in default_next_count.items():
        grouped_default[src_id].append((dst_id, count))
    for src_id, pairs in grouped_default.items():
        pairs.sort(key=lambda item: (item[1], item[0]), reverse=True)
        default_next[src_id] = pairs[0][0]

    confidence_counts = Counter(row["confidence"] for row in inferred)

    compiled = {
        "meta": {
            "generated_at": _utc_now(),
            "states_count": len(states),
            "edges_count": len(inferred),
            "confidence_counts": dict(confidence_counts),
        },
        "by_state": by_state,
        "default_next": default_next,
        "transitions": transitions,
    }
    return inferred, compiled


def _extract_prompt_states(states: dict[str, CompiledState]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {"buy": {}, "sell": {}}
    for sid, state in states.items():
        match = PROMPT_RE.search(state.text)
        if not match:
            continue
        op_raw, coin_raw = match.groups()
        operation = "buy" if "куп" in op_raw.lower() else "sell"
        coin = _norm_coin(coin_raw)
        result[operation][coin] = sid
    return result


def _extract_quotes(states: dict[str, CompiledState]) -> list[QuoteRecord]:
    out: list[QuoteRecord] = []
    for sid, state in states.items():
        match = QUOTE_RE.search(state.text)
        if not match:
            continue
        receive_text = match.group("receive")
        pay_text = match.group("pay")
        net_text = match.group("net")
        receive_amount, receive_asset = _parse_amount_asset(receive_text)
        pay_amount, pay_asset = _parse_amount_asset(pay_text)
        net_amount = _parse_number(net_text)

        operation = ""
        coin = ""
        coin_amount = None
        rub_amount = None

        if receive_asset == "RUB" and pay_asset and pay_asset != "RUB":
            operation = "sell"
            coin = pay_asset
            coin_amount = pay_amount
            rub_amount = receive_amount
        elif pay_asset == "RUB" and receive_asset and receive_asset != "RUB":
            operation = "buy"
            coin = receive_asset
            coin_amount = receive_amount
            rub_amount = pay_amount
        elif state.kind == "quote":
            # best effort fallback
            if "₽" in receive_text:
                operation = "sell"
                coin = _norm_coin(pay_asset or "UNKNOWN")
                coin_amount = pay_amount
                rub_amount = receive_amount
            else:
                operation = "buy"
                coin = _norm_coin(receive_asset or "UNKNOWN")
                coin_amount = receive_amount
                rub_amount = pay_amount

        if not operation or not coin:
            continue
        if coin_amount is None or rub_amount is None:
            continue
        out.append(
            QuoteRecord(
                state_id=sid,
                operation=operation,
                coin=_norm_coin(coin),
                coin_amount=float(coin_amount),
                rub_amount=float(rub_amount),
                net_amount=float(net_amount) if net_amount is not None else None,
            )
        )
    return out


def _extract_promos(states: dict[str, CompiledState]) -> list[PromoRecord]:
    out: list[PromoRecord] = []
    for sid, state in states.items():
        match = PROMO_RE.search(state.text)
        if not match:
            continue
        coin_raw = match.group("coin")
        coin_amount = _parse_number(match.group("coin_amount"))
        pay_before = _parse_number(match.group("pay_before"))
        pay_after = _parse_number(match.group("pay_after"))
        if coin_amount is None or pay_before is None or pay_after is None:
            continue
        out.append(
            PromoRecord(
                state_id=sid,
                coin=_norm_coin(coin_raw),
                coin_amount=float(coin_amount),
                pay_before=float(pay_before),
                pay_after=float(pay_after),
            )
        )
    return out


def _extract_order_templates(states: dict[str, CompiledState]) -> list[OrderTemplateRecord]:
    out: list[OrderTemplateRecord] = []
    for sid, state in states.items():
        match = ORDER_RE.search(state.text)
        if not match:
            continue
        sold_raw = match.group("sold").strip()
        sold_amount = _parse_number(sold_raw)
        sold_tokens = TOKEN_RE.findall(sold_raw)
        sold_coin = _norm_coin(sold_tokens[-1] if sold_tokens else "")
        payout_rub = _parse_number(match.group("payout")) or 0.0
        buttons = state.interactive_actions.copy()
        out.append(
            OrderTemplateRecord(
                state_id=sid,
                coin=sold_coin,
                sold_amount_raw=sold_raw,
                payout_rub=float(payout_rub),
                requisites_label=match.group("label").strip(),
                requisites_value=match.group("requisites").strip(),
                source_text=state.text,
                buttons=buttons,
            )
        )
        _ = sold_amount  # reserved for future matching logic
    return out


def build_compiled(raw_dir: Path, media_dir: Path, compiled_dir: Path) -> dict[str, Any]:
    bundle = load_raw_bundle(raw_dir)

    states: dict[str, CompiledState] = {}
    for sid, state in bundle.flow.items():
        rows = _rows_for_state(state)
        actions = _interactive_actions(rows)
        text = str(state.get("text") or "")
        text_html = str(state.get("text_html") or text)
        text_markdown = str(state.get("text_markdown") or text)
        entities = [entity for entity in state.get("entities", []) if isinstance(entity, dict)]
        entity_types = [str(value) for value in state.get("entity_types", []) if isinstance(value, str)]
        media_ref = state.get("media") if isinstance(state.get("media"), str) else None
        media_file = Path(media_ref.replace("\\", "/")).name if media_ref else None
        media_exists = bool(media_file and (media_dir / media_file).exists())
        kind = _state_kind(text, rows, actions)
        states[sid] = CompiledState(
            state_id=sid,
            text=text,
            text_html=text_html,
            text_markdown=text_markdown,
            entities=entities,
            entity_types=entity_types,
            button_rows=rows,
            interactive_actions=actions,
            media_ref=media_ref,
            media_file=media_file,
            media_exists=media_exists,
            kind=kind,
        )

    inferred_edges, transitions = infer_transitions(states, bundle.edges)

    # Resolve media gaps after transitions are known.
    for sid, state in states.items():
        if state.media_ref and not state.media_exists:
            fallback_media = _resolve_missing_media(
                sid,
                states,
                transitions.get("by_state", {}),
                transitions.get("default_next", {}),
            )
            if fallback_media:
                state.media_file = fallback_media
                state.media_exists = True

    prompt_states = _extract_prompt_states(states)
    quotes = _extract_quotes(states)
    promos = _extract_promos(states)
    order_templates = _extract_order_templates(states)

    compiled_states_payload = {
        "meta": {
            "generated_at": _utc_now(),
            "states_count": len(states),
            "links_count": len(bundle.links),
            "missing_media_count": sum(1 for state in states.values() if state.media_ref and not state.media_exists),
        },
        "states": {sid: state.to_dict() for sid, state in states.items()},
        "links": bundle.links,
    }
    compiled_replay_payload = {
        "meta": {
            "generated_at": _utc_now(),
            "quotes_count": len(quotes),
            "promos_count": len(promos),
            "order_templates_count": len(order_templates),
        },
        "prompt_states": prompt_states,
        "quotes": [record.to_dict() for record in quotes],
        "promos": [record.to_dict() for record in promos],
        "order_templates": [record.to_dict() for record in order_templates],
    }

    compiled_dir.mkdir(parents=True, exist_ok=True)
    (compiled_dir / "compiled_states.json").write_text(
        json.dumps(compiled_states_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (compiled_dir / "compiled_transitions.json").write_text(
        json.dumps(transitions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (compiled_dir / "compiled_replay_tables.json").write_text(
        json.dumps(compiled_replay_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (compiled_dir / "compiled_inferred_edges.json").write_text(
        json.dumps(inferred_edges, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "states": compiled_states_payload,
        "transitions": transitions,
        "replay": compiled_replay_payload,
        "inferred_edges": inferred_edges,
    }


def ensure_compiled(raw_dir: Path, media_dir: Path, compiled_dir: Path) -> None:
    required = [
        compiled_dir / "compiled_states.json",
        compiled_dir / "compiled_transitions.json",
        compiled_dir / "compiled_replay_tables.json",
    ]
    if all(path.exists() for path in required):
        raw_mtime = max(
            (raw_dir / "flow.json").stat().st_mtime,
            (raw_dir / "edges.json").stat().st_mtime,
            (raw_dir / "events.json").stat().st_mtime,
        )
        compiled_mtime = min(path.stat().st_mtime for path in required)
        if compiled_mtime >= raw_mtime:
            return
    build_compiled(raw_dir=raw_dir, media_dir=media_dir, compiled_dir=compiled_dir)
