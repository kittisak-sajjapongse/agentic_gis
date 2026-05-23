"""Workflow scenario: UI handles HITL clarification and resume to completion.

UI narrative:
1. User submits a prompt from chat panel.
2. Run stream emits `clarification_required`; UI displays question and waits.
3. User answers clarification in chat panel; UI calls resume endpoint.
4. Resumed stream emits `layer_created` + `done`.
5. UI reloads session layers and map can show the generated layer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import api.run_service as run_service_module
from api.layer_service import LayerService
from api.run_service import RunService
from tools.artifact_provider import LocalArtifactProvider


class _SSEEventCollector(RunService):
    """RunService test double that records emitted SSE event types."""

    def __init__(self):
        super().__init__()
        self.emitted_types: list[str] = []

    def _emit_event(self, run_id: str, event_type: str, payload: dict) -> None:
        self.emitted_types.append(event_type)
        super()._emit_event(run_id, event_type, payload)


class _FakeInterrupt:
    def __init__(self, interrupt_id: str, value: dict):
        self.id = interrupt_id
        self.value = value


class _FakeStateInterrupt:
    def __init__(self):
        self.values = {}
        self.interrupts = [
            _FakeInterrupt(
                "intr_ui_1",
                {
                    "type": "ir_clarification",
                    "question": "Which month should be used?",
                },
            )
        ]


class _FakeStateDoneWithOutput:
    def __init__(self, output_path: str):
        self.values = {
            "outputs": [
                {
                    "output_type": "GEOJSON",
                    "description": "Layer after clarification",
                    "path": output_path,
                }
            ]
        }
        self.interrupts = []


class _FakeGraphHitl:
    def __init__(self, output_path: str):
        self._calls = 0
        self._output_path = output_path

    async def astream(self, inputs, config=None):
        self._calls += 1
        if False:
            yield None

    async def aget_state(self, config=None):
        if self._calls == 1:
            return _FakeStateInterrupt()
        return _FakeStateDoneWithOutput(self._output_path)


def _fake_builder_factory(output_path: str):
    async def _build():
        return _FakeGraphHitl(output_path)

    return _build


def test_workflow_hitl_resume_end_to_end() -> None:
    async def _run() -> None:
        output_file = Path("data/test_hitl_workflow_output.geojson")
        output_file.write_text(
            json.dumps({"type": "FeatureCollection", "features": []}),
            encoding="utf-8",
        )
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _fake_builder_factory(str(output_file))
        try:
            rs = _SSEEventCollector()
            ls = LayerService()
            ap = LocalArtifactProvider()

            session_id = "sess_workflow_hitl"
            ls.init_session(session_id)
            run = rs.create_run(session_id)

            async def _collect_until(run_id: str, terminal: set[str]) -> list[str]:
                collected: list[str] = []
                async for event in rs.subscribe(run_id):
                    collected.append(event["type"])
                    if event["type"] in terminal:
                        break
                return collected

            first_events_task = asyncio.create_task(
                _collect_until(run.runId, {"clarification_required", "error"})
            )
            await asyncio.sleep(0)

            # Start run after subscriber attached.
            execute_task = asyncio.create_task(
                rs.execute_run(
                    session_id=session_id,
                    run_id=run.runId,
                    message="Create random points layer",
                    layer_service=ls,
                    artifact_provider=ap,
                )
            )
            first_events = await first_events_task
            await execute_task

            status1 = rs.get_run(run.runId)
            assert status1 is not None and status1.status == "interrupted"
            assert status1.pendingInterruptId == "intr_ui_1"
            assert "clarification_required" in first_events

            # Resume after UI user answer.
            await rs.resume_run(
                run_id=run.runId,
                interrupt_id="intr_ui_1",
                answer="Use March",
                layer_service=ls,
                artifact_provider=ap,
            )

            # Reconnect stream after resume and observe terminal catch-up.
            second_events = await _collect_until(run.runId, {"done", "error"})

            status2 = rs.get_run(run.runId)
            layers = ls.list_layers(session_id)
            assert status2 is not None and status2.status == "completed"
            # Explicitly assert resume path emitted layer_created event from
            # RunService internals, independent of subscriber timing.
            assert "layer_created" in rs.emitted_types
            assert "done" in second_events
            assert len(layers) == 1
            assert layers[0].origin == "agent_output"
        finally:
            run_service_module.build_main_graph = original_builder
            if output_file.exists():
                output_file.unlink()

    asyncio.run(_run())
