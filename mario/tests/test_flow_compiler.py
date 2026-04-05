from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.flow_compiler import build_compiled

pytestmark = pytest.mark.unit


def test_build_compiled_writes_outputs(tmp_path: Path) -> None:
    project_dir = Path(__file__).resolve().parents[1]
    raw_dir = project_dir / "data" / "raw"
    media_dir = project_dir / "assets" / "media"
    compiled_dir = tmp_path / "compiled"

    result = build_compiled(raw_dir=raw_dir, media_dir=media_dir, compiled_dir=compiled_dir)

    assert (compiled_dir / "compiled_states.json").exists()
    assert (compiled_dir / "compiled_transitions.json").exists()
    assert (compiled_dir / "compiled_replay_tables.json").exists()
    assert (compiled_dir / "compiled_inferred_edges.json").exists()

    states_payload = json.loads((compiled_dir / "compiled_states.json").read_text(encoding="utf-8"))
    transitions_payload = json.loads((compiled_dir / "compiled_transitions.json").read_text(encoding="utf-8"))
    replay_payload = json.loads((compiled_dir / "compiled_replay_tables.json").read_text(encoding="utf-8"))

    assert states_payload["meta"]["states_count"] >= 60
    assert len(states_payload["states"]) >= 60
    assert len(transitions_payload["by_state"]) >= 50
    assert len(replay_payload["quotes"]) >= 5
    assert "buy" in replay_payload["prompt_states"]
    assert "sell" in replay_payload["prompt_states"]
    assert result["states"]["meta"]["states_count"] == states_payload["meta"]["states_count"]
