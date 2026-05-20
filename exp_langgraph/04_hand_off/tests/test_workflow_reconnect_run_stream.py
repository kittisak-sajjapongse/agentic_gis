"""Workflow scenario: UI reconnects to run stream and still gets terminal state.

UI narrative:
1. User starts a run and UI opens SSE stream.
2. Network blip or page refresh happens; UI loses stream.
3. UI reconnects using same `runId`.
4. Backend must provide coherent state catch-up so UI can still show completion.
"""

from __future__ import annotations

import asyncio

import api.run_service as run_service_module
from api.run_service import RunService


class _FakeStateDone:
    def __init__(self):
        self.values = {"outputs": []}
        self.interrupts = []


class _FakeGraphDone:
    async def astream(self, inputs, config=None):
        await asyncio.sleep(0.01)
        if False:
            yield None

    async def aget_state(self, config=None):
        return _FakeStateDone()


async def _fake_build_main_graph():
    return _FakeGraphDone()


def test_workflow_reconnect_run_stream() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _fake_build_main_graph
        try:
            rs = RunService()
            run = rs.create_run("sess_reconnect")

            await rs.execute_run("sess_reconnect", run.runId, "do task")

            # Reconnect after completion: subscriber should still receive done.
            events: list[str] = []
            async for event in rs.subscribe(run.runId):
                events.append(event["type"])
                if event["type"] in {"done", "error"}:
                    break

            assert events[0] == "message"
            assert "done" in events
            assert rs.get_run(run.runId).status == "completed"  # type: ignore[union-attr]
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())

