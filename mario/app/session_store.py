from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import UserSession


class SessionStore:
    def __init__(self, path: Path, history_limit: int):
        self.path = path
        self.history_limit = history_limit
        self._sessions: dict[int, UserSession] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self._sessions = {}
            self.save()
            return
        if not isinstance(payload, dict):
            self._sessions = {}
            self.save()
            return
        sessions = payload.get("sessions")
        if not isinstance(sessions, list):
            self._sessions = {}
            self.save()
            return
        for item in sessions:
            if not isinstance(item, dict):
                continue
            try:
                session = UserSession.from_dict(item)
            except Exception:
                continue
            self._sessions[session.user_id] = session

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sessions": [session.to_dict() for session in self._sessions.values()]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_or_create(self, user_id: int, default_state_id: str) -> UserSession:
        session = self._sessions.get(user_id)
        if session:
            return session
        created = UserSession(user_id=user_id, current_state_id=default_state_id, history=[default_state_id])
        self._sessions[user_id] = created
        return created

    def set_state(self, user_id: int, state_id: str, default_state_id: str) -> UserSession:
        session = self.get_or_create(user_id, default_state_id)
        session.push_state(state_id, self.history_limit)
        return session

    def clear(self, user_id: int, default_state_id: str) -> UserSession:
        session = UserSession(user_id=user_id, current_state_id=default_state_id, history=[default_state_id])
        self._sessions[user_id] = session
        return session

    def update_fields(self, user_id: int, default_state_id: str, **kwargs: Any) -> UserSession:
        session = self.get_or_create(user_id, default_state_id)
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        return session
