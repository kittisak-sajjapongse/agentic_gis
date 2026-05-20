"""Workflow scenario: chat request is declined and UI must show decline reason.

UI narrative:
1. User types a non-actionable/non-GIS prompt in the chat panel and clicks Send.
2. UI starts run stream (`/api/runs/{runId}/stream`).
3. Agent decides to decline, run completes quickly.
4. Even if UI subscribes late (or misses live `decline` SSE event), backend
   terminal catch-up must still carry `declineMessage` so the chat panel can
   render: "Declined: <reason>".
"""

from __future__ import annotations

import asyncio

import api.run_service as run_service_module
from api.run_service import RunService


class _FakeStateDeclineDone:
    def __init__(self) -> None:
        self.values = {
            "decline_message": "The prompt is not a GIS-related question.",
            "outputs": [],
        }
        self.interrupts = []


class _FakeGraphDeclineDone:
    async def astream(self, inputs, config=None):
        if False:
            yield None

    async def aget_state(self, config=None):
        return _FakeStateDeclineDone()


async def _fake_build_main_graph():
    return _FakeGraphDeclineDone()


def test_workflow_chat_decline_message_terminal_catchup() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _fake_build_main_graph
        try:
            rs = RunService()
            run = rs.create_run("sess_decline")

            # Execute run first (simulates UI attaching stream late).
            await rs.execute_run("sess_decline", run.runId, "hello")

            events: list[dict] = []
            async for event in rs.subscribe(run.runId):
                events.append(event)

            assert len(events) >= 2
            assert events[0]["type"] == "message"
            assert events[1]["type"] == "done"
            assert events[1]["payload"]["status"] == "completed"
            assert (
                events[1]["payload"].get("declineMessage")
                == "The prompt is not a GIS-related question."
            )
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())

