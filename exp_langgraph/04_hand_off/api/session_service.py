from __future__ import annotations

from typing import Callable, Optional

from domain.state_models import SessionModel


class SessionService:
    def __init__(
        self,
        initial_sessions: Optional[dict[str, SessionModel]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize session lifecycle service.

        Args:
            initial_sessions: Optional preloaded session snapshot for startup
                restore from persistence.
            on_change: Optional callback fired when session records mutate, so
                app-level persistence can flush updated state.
        """
        self._sessions: dict[str, SessionModel] = initial_sessions or {}
        self._on_change = on_change

    def create_session(self) -> SessionModel:
        session = SessionModel.create()
        self._sessions[session.sessionId] = session
        self._notify_changed()
        return session

    def get_session(self, session_id: str) -> SessionModel | None:
        return self._sessions.get(session_id)

    def set_last_run(self, session_id: str, run_id: str) -> SessionModel | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        updated = session.model_copy(update={"lastRunId": run_id})
        self._sessions[session_id] = updated
        self._notify_changed()
        return updated

    def dump_state(self) -> dict[str, dict]:
        """Return JSON-serializable snapshot of session records.

        Used by persistence layer to store durable session metadata across
        backend restarts.
        """
        return {sid: session.model_dump() for sid, session in self._sessions.items()}

    def _notify_changed(self) -> None:
        if self._on_change is not None:
            self._on_change()
