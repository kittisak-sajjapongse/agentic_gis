from __future__ import annotations

from domain.state_models import SessionModel


class SessionService:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionModel] = {}

    def create_session(self) -> SessionModel:
        session = SessionModel.create()
        self._sessions[session.sessionId] = session
        return session

    def get_session(self, session_id: str) -> SessionModel | None:
        return self._sessions.get(session_id)

