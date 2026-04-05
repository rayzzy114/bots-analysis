from __future__ import annotations

import re
from typing import Any

ACTION_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9_]+")


def _norm_action(text: str) -> str:
    return " ".join(token.lower() for token in ACTION_TOKEN_RE.findall(text or ""))


class TransitionEngine:
    def __init__(self, transitions_payload: dict[str, Any], states_payload: dict[str, Any]):
        self.by_state: dict[str, dict[str, str]] = {
            str(sid): {str(action): str(dst) for action, dst in action_map.items()}
            for sid, action_map in (transitions_payload.get("by_state") or {}).items()
            if isinstance(action_map, dict)
        }
        self.default_next: dict[str, str] = {
            str(sid): str(dst) for sid, dst in (transitions_payload.get("default_next") or {}).items()
        }
        self.transitions: dict[str, dict[str, list[dict[str, Any]]]] = {
            str(sid): {str(action): list(targets) for action, targets in action_map.items()}
            for sid, action_map in (transitions_payload.get("transitions") or {}).items()
            if isinstance(action_map, dict)
        }
        self.states = (states_payload.get("states") or {}) if isinstance(states_payload, dict) else {}

    def _candidate_keys(self, action_text: str, is_text_input: bool) -> list[str]:
        keys: list[str] = []
        if is_text_input:
            keys.append("input:any")
        if action_text:
            keys.append(f"button:{action_text}")
            action_norm = _norm_action(action_text)
            if action_norm:
                keys.append(f"button_norm:{action_norm}")
        if not action_text and not is_text_input:
            keys.append("system:auto")
        return keys

    def _resolve_action_key(self, state_id: str, action_text: str, is_text_input: bool) -> str | None:
        action_map = self.by_state.get(state_id, {})
        if not action_map:
            return None
        candidate_keys = self._candidate_keys(action_text, is_text_input)

        # Exact action key.
        for key in candidate_keys:
            if key.startswith("button_norm:"):
                continue
            if key in action_map:
                return key

        # Normalized button lookup.
        action_norm = _norm_action(action_text) if action_text else ""
        if action_norm:
            for key in action_map.keys():
                if not key.startswith("button:"):
                    continue
                button_text = key[len("button:") :]
                if _norm_action(button_text) == action_norm:
                    return key
        return None

    def _rank_targets(
        self,
        state_id: str,
        action_key: str,
        session_history: list[str] | None,
    ) -> list[dict[str, Any]]:
        targets = list((self.transitions.get(state_id, {}) or {}).get(action_key, []))
        if not targets:
            default_target = self.by_state.get(state_id, {}).get(action_key)
            if default_target:
                return [
                    {
                        "to_state": default_target,
                        "count": 1,
                        "weight": 1.0,
                        "confidence_score": 0.5,
                    }
                ]
            return []

        recent = set((session_history or [])[-3:])
        ranked: list[dict[str, Any]] = []
        for row in targets:
            to_state = str(row.get("to_state") or "")
            score = float(row.get("weight") or 0.0) + float(row.get("count") or 0.0) * 0.05
            score += float(row.get("confidence_score") or 0.0) * 0.5
            if to_state in recent:
                score -= 0.35
            ranked.append({**row, "score": round(score, 6)})

        ranked.sort(
            key=lambda item: (
                float(item.get("score") or 0.0),
                float(item.get("weight") or 0.0),
                int(item.get("count") or 0),
                str(item.get("to_state") or ""),
            ),
            reverse=True,
        )
        return ranked

    def resolve_next(
        self,
        state_id: str,
        *,
        action_text: str = "",
        is_text_input: bool = False,
        session_history: list[str] | None = None,
    ) -> tuple[str | None, str]:
        action_key = self._resolve_action_key(state_id, action_text, is_text_input)
        if action_key:
            ranked = self._rank_targets(state_id, action_key, session_history)
            if ranked:
                return str(ranked[0].get("to_state") or ""), f"action:{action_key}"

        # Fallback route by default_next from compiled transitions.
        # Keep main menu strict: unknown menu buttons should not jump to arbitrary defaults.
        if not action_text and not is_text_input:
            fallback = self.default_next.get(state_id)
            if fallback:
                return fallback, "fallback:default_next"
        elif action_text and not is_text_input:
            state = self.states.get(state_id, {})
            kind = str(state.get("kind") or "")
            if kind != "main_menu":
                fallback = self.default_next.get(state_id)
                if fallback:
                    return fallback, "fallback:default_next"

        return None, "fallback:unresolved"
