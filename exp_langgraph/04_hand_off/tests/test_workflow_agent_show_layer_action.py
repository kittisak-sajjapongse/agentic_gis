"""Workflow scenario: agent emits structured `show_layer` actions during a run.

UI narrative:
1. User sends a chat prompt.
2. Agent returns structured action payload in run state:
   - valid: {"action":"show_layer", ...}
   - invalid: malformed show_layer selector payload
3. Backend run execution detects actions and invokes show-layer service.
4. UI observes layer update events and/or terminal error event accordingly.
"""

from __future__ import annotations

import asyncio

import api.run_service as run_service_module
from api.run_service import RunService
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle


class _FakeState:
    def __init__(self, values: dict):
        self.values = values
        self.interrupts = []


class _FakeGraph:
    def __init__(self, values: dict):
        self._values = values

    async def astream(self, inputs, config=None):
        if False:
            yield None

    async def aget_state(self, config=None):
        return _FakeState(self._values)


def _builder_factory(values: dict):
    async def _build():
        return _FakeGraph(values)

    return _build


class _MockedLayerShowService:
    def __init__(self):
        self.calls: list[tuple[str, str | None, str | None, str | None]] = []

    def show_layer(self, session_id: str, *, artifact=None, catalog_item_id=None, layer_id=None):
        self.calls.append((session_id, artifact, catalog_item_id, layer_id))
        return LayerDescriptor(
            id="lyr_stub_1",
            name="Stub shown layer",
            kind="geojson",
            source=LayerSource(type="geojson", url="/api/artifacts/stub/content"),
            style=LayerStyle(preset="line-default"),
            visible=True,
            origin="input",
            catalogItemId=catalog_item_id,
            createdAt="2026-01-01T00:00:00Z",
        )


def test_workflow_agent_show_layer_action_valid() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _builder_factory(
            {
                "actions": [
                    {
                        "action": "show_layer",
                        "artifact": "cat_001",
                    }
                ],
                "outputs": [],
            }
        )
        try:
            rs = RunService()
            run = rs.create_run("sess_action_ok")
            action_service = _MockedLayerShowService()

            events: list[str] = []
            async def _collect():
                async for event in rs.subscribe(run.runId):
                    events.append(event["type"])
                    if event["type"] in {"done", "error"}:
                        break

            collector = asyncio.create_task(_collect())
            await asyncio.sleep(0)
            await rs.execute_run(
                session_id="sess_action_ok",
                run_id=run.runId,
                message="show hotspot",
                layer_show_service=action_service,
            )
            await collector

            status = rs.get_run(run.runId)
            assert status is not None and status.status == "completed"
            assert action_service.calls == [("sess_action_ok", "cat_001", None, None)]
            assert "layer_updated" in events
            assert "done" in events
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())


def test_workflow_agent_show_layer_action_invalid_payload_fails_cleanly() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _builder_factory(
            {
                "actions": [
                    {
                        "action": "show_layer",
                        # Invalid: both missing.
                    }
                ],
                "outputs": [],
            }
        )
        try:
            rs = RunService()
            run = rs.create_run("sess_action_bad")
            action_service = _MockedLayerShowService()

            events: list[str] = []
            async def _collect():
                async for event in rs.subscribe(run.runId):
                    events.append(event["type"])
                    if event["type"] in {"error", "done"}:
                        break

            collector = asyncio.create_task(_collect())
            await asyncio.sleep(0)
            task = asyncio.create_task(
                rs.execute_run(
                    session_id="sess_action_bad",
                    run_id=run.runId,
                    message="show something",
                    layer_show_service=action_service,
                )
            )
            await task
            await collector

            status = rs.get_run(run.runId)
            assert status is not None and status.status == "failed"
            assert "show_layer action requires non-empty `artifact`" in (status.error or "")
            assert "error" in events
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())


def test_workflow_agent_show_layer_action_artifact_selector() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _builder_factory(
            {
                "actions": [
                    {
                        "action": "show_layer",
                        "artifact": "/data/hotspot_2024.parquet",
                    }
                ],
                "outputs": [],
            }
        )
        try:
            rs = RunService()
            run = rs.create_run("sess_action_path")
            action_service = _MockedLayerShowService()

            await rs.execute_run(
                session_id="sess_action_path",
                run_id=run.runId,
                message="show hotspot",
                layer_show_service=action_service,
            )
            status = rs.get_run(run.runId)
            assert status is not None and status.status == "completed"
            assert action_service.calls == [
                ("sess_action_path", "/data/hotspot_2024.parquet", None, None)
            ]
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())
