from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.messages import HumanMessage

from domain.state_models import RunModel
from graphs.main_graph import build_main_graph


class RunService:
    def __init__(self) -> None:
        self._runs: dict[str, RunModel] = {}

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_run(self, session_id: str) -> RunModel:
        run = RunModel(
            runId=f"run_{uuid4().hex[:12]}",
            sessionId=session_id,
            status="queued",
            startedAt=self._now_iso(),
        )
        self._runs[run.runId] = run
        return run

    def get_run(self, run_id: str) -> RunModel | None:
        return self._runs.get(run_id)

    def _update_run(self, run_id: str, **updates: str | None) -> RunModel | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        updated = run.model_copy(update=updates)
        self._runs[run_id] = updated
        return updated

    async def execute_run(self, session_id: str, run_id: str, message: str) -> None:
        self._update_run(run_id, status="running")
        try:
            # TODO: Move to session-scoped graph caching (lazy init + TTL cleanup)
            # to avoid rebuilding the graph/tool stack on every chat run.
            graph = await build_main_graph()
            config = {"configurable": {"thread_id": session_id}}
            inputs = {"_messages": [HumanMessage(content=message)]}

            async for _ in graph.astream(inputs, config=config):
                pass

            state = await graph.aget_state(config)
            if state.interrupts:
                self._update_run(
                    run_id,
                    status="interrupted",
                    finishedAt=self._now_iso(),
                )
                return

            self._update_run(
                run_id,
                status="completed",
                finishedAt=self._now_iso(),
            )
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error=str(exc),
                finishedAt=self._now_iso(),
            )
