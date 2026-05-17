from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import uuid4

from langchain_core.messages import HumanMessage

from domain.state_models import RunModel
from graphs.main_graph import build_main_graph


class RunService:
    def __init__(self) -> None:
        self._runs: dict[str, RunModel] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

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

    def _emit_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        event = {
            "type": event_type,
            "runId": run_id,
            "sessionId": run.sessionId,
            "timestamp": self._now_iso(),
            "payload": payload,
        }
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)

    def _terminal_event_for_run(self, run: RunModel) -> dict[str, Any] | None:
        if run.status == "completed":
            return {
                "type": "done",
                "runId": run.runId,
                "sessionId": run.sessionId,
                "timestamp": self._now_iso(),
                "payload": {"status": "completed"},
            }
        if run.status in {"failed", "interrupted"}:
            return {
                "type": "error",
                "runId": run.runId,
                "sessionId": run.sessionId,
                "timestamp": self._now_iso(),
                "payload": {
                    "status": run.status,
                    "message": run.error or "Run interrupted",
                },
            }
        return None

    def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        if self.get_run(run_id) is None:
            raise KeyError(f"Run not found: {run_id}")

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)

        async def _iter() -> AsyncIterator[dict[str, Any]]:
            try:
                # Send current run status immediately so clients can sync on connect.
                run = self.get_run(run_id)
                if run is not None:
                    yield {
                        "type": "message",
                        "runId": run.runId,
                        "sessionId": run.sessionId,
                        "timestamp": self._now_iso(),
                        "payload": {"status": run.status},
                    }
                    terminal = self._terminal_event_for_run(run)
                    if terminal is not None:
                        yield terminal
                        return

                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # Catch terminal state even if subscriber connected after
                        # events were emitted and no queue messages remain.
                        run = self.get_run(run_id)
                        if run is not None:
                            terminal = self._terminal_event_for_run(run)
                            if terminal is not None:
                                yield terminal
                                break
                        continue
                    yield event
                    if event["type"] in {"done", "error"}:
                        break
            finally:
                subscribers = self._subscribers.get(run_id, [])
                if queue in subscribers:
                    subscribers.remove(queue)
                if not subscribers and run_id in self._subscribers:
                    self._subscribers.pop(run_id, None)

        return _iter()

    async def execute_run(self, session_id: str, run_id: str, message: str) -> None:
        self._update_run(run_id, status="running")
        self._emit_event(run_id, "message", {"text": "Run started", "status": "running"})
        self._emit_event(run_id, "tool_start", {"tool": "main_graph", "status": "started"})
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
                self._emit_event(
                    run_id,
                    "tool_end",
                    {"tool": "main_graph", "status": "interrupted"},
                )
                self._emit_event(
                    run_id,
                    "error",
                    {"message": "Run interrupted and requires clarification"},
                )
                return

            self._update_run(
                run_id,
                status="completed",
                finishedAt=self._now_iso(),
            )
            self._emit_event(
                run_id,
                "tool_end",
                {"tool": "main_graph", "status": "completed"},
            )
            self._emit_event(
                run_id,
                "done",
                {"status": "completed"},
            )
        except Exception as exc:
            self._update_run(
                run_id,
                status="failed",
                error=str(exc),
                finishedAt=self._now_iso(),
            )
            self._emit_event(
                run_id,
                "tool_end",
                {"tool": "main_graph", "status": "failed"},
            )
            self._emit_event(
                run_id,
                "error",
                {"message": str(exc)},
            )
