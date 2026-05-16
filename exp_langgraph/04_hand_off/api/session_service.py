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

    def set_last_run(self, session_id: str, run_id: str) -> SessionModel | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        updated = session.model_copy(update={"lastRunId": run_id})
        self._sessions[session_id] = updated
        return updated
