"""Workflow scenario: UI handles HITL clarification and resume to completion.

UI narrative:
1. User submits a prompt from chat panel.
2. Run stream emits `clarification_required`; UI displays question and waits.
3. User answers clarification in chat panel; UI calls resume endpoint.
4. Resumed stream emits `layer_updated` + `done`.
5. UI reloads session layers and map can show the generated layer.
"""

from __future__ import annotations

import asyncio

import api.run_service as run_service_module
from api.layer_service import LayerService
from api.run_service import RunService
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle
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
    def __init__(self):
        self.values = {
            "actions": [
                {
                    "action": "show_layer",
                    "artifact": "cat_001",
                }
            ]
        }
        self.interrupts = []


class _FakeGraphHitl:
    def __init__(self):
        self._calls = 0

    async def astream(self, inputs, config=None):
        self._calls += 1
        if False:
            yield None

    async def aget_state(self, config=None):
        if self._calls == 1:
            return _FakeStateInterrupt()
        return _FakeStateDoneWithOutput()


def _fake_builder_factory():
    async def _build():
        return _FakeGraphHitl()

    return _build


def test_workflow_hitl_resume_end_to_end() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _fake_builder_factory()
        try:
            rs = _SSEEventCollector()
            ls = LayerService()
            ap = LocalArtifactProvider()

            class _MockLayerShowService:
                def __init__(self) -> None:
                    self.calls: list[tuple[str, str | None]] = []

                def show_layer(self, session_id: str, *, artifact=None, catalog_item_id=None, layer_id=None):
                    self.calls.append((session_id, artifact))
                    return LayerDescriptor(
                        id="lyr_stub_hitl_1",
                        name="Stub HITL Layer",
                        kind="geojson",
                        source=LayerSource(type="geojson", url="/api/artifacts/stub/content"),
                        style=LayerStyle(preset="line-default"),
                        visible=True,
                        origin="input",
                        createdAt="2026-01-01T00:00:00Z",
                    )
            action_service = _MockLayerShowService()

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
                    layer_show_service=action_service,
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
                layer_show_service=action_service,
            )

            # Reconnect stream after resume and observe terminal catch-up.
            second_events = await _collect_until(run.runId, {"done", "error"})

            status2 = rs.get_run(run.runId)
            assert status2 is not None and status2.status == "completed"
            assert action_service.calls == [(session_id, "cat_001")]
            assert "done" in second_events
            assert "layer_updated" in rs.emitted_types
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())
