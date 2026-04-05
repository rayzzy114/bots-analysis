from __future__ import annotations

import pytest

from app.transition_engine import TransitionEngine

pytestmark = pytest.mark.unit


def test_transition_engine_exact_and_fallback() -> None:
    transitions = {
        "by_state": {
            "s1": {
                "button:Купить": "s2",
                "input:any": "s3",
                "system:auto": "s4",
            }
        },
        "default_next": {"s1": "s5"},
        "transitions": {
            "s1": {
                "button:Купить": [
                    {
                        "to_state": "s2",
                        "count": 4,
                        "weight": 8.0,
                        "confidence": "high",
                        "confidence_score": 0.9,
                    }
                ],
                "input:any": [
                    {
                        "to_state": "s3",
                        "count": 5,
                        "weight": 9.0,
                        "confidence": "medium",
                        "confidence_score": 0.7,
                    }
                ],
            }
        },
    }
    states_payload = {"states": {"s1": {}, "s2": {}, "s3": {}, "s4": {}, "s5": {}}}

    engine = TransitionEngine(transitions, states_payload)

    next_state, reason = engine.resolve_next("s1", action_text="Купить", is_text_input=False, session_history=[])
    assert next_state == "s2"
    assert reason.startswith("action:")

    next_state, reason = engine.resolve_next("s1", action_text="12345", is_text_input=True, session_history=[])
    assert next_state == "s3"

    next_state, reason = engine.resolve_next("unknown", action_text="abc", is_text_input=False, session_history=[])
    assert next_state is None
    assert reason == "fallback:unresolved"
