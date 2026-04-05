from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RawFlowBundle:
    flow: dict[str, dict[str, Any]]
    edges: list[dict[str, Any]]
    events: list[dict[str, Any]]
    links: list[str]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_raw_bundle(raw_dir: Path) -> RawFlowBundle:
    flow = _load_json(raw_dir / "flow.json")
    edges = _load_json(raw_dir / "edges.json")
    events = _load_json(raw_dir / "events.json")
    links = _load_json(raw_dir / "links.json")

    if not isinstance(flow, dict):
        raise ValueError(f"Expected flow.json to be dict, got: {type(flow)!r}")
    if not isinstance(edges, list):
        raise ValueError(f"Expected edges.json to be list, got: {type(edges)!r}")
    if not isinstance(events, list):
        raise ValueError(f"Expected events.json to be list, got: {type(events)!r}")
    if not isinstance(links, list):
        raise ValueError(f"Expected links.json to be list, got: {type(links)!r}")

    normalized_flow: dict[str, dict[str, Any]] = {}
    for sid, state in flow.items():
        if isinstance(state, dict):
            normalized_flow[str(sid)] = state

    normalized_edges = [edge for edge in edges if isinstance(edge, dict)]
    normalized_events = [event for event in events if isinstance(event, dict)]
    normalized_links = [str(link) for link in links if isinstance(link, str)]

    return RawFlowBundle(
        flow=normalized_flow,
        edges=normalized_edges,
        events=normalized_events,
        links=normalized_links,
    )

