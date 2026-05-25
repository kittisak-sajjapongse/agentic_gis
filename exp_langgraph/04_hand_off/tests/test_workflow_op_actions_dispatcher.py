"""Workflow scenario: OP actions dispatcher executes create/show/rename chain.

UI narrative:
1. User sends a chat request.
2. OP returns actions-only payload:
   - create_layer_from_artifact
   - show_created_layer
   - rename_layer
3. Backend executes actions in order with sourceActionIndex resolution.
4. SSE emits layer update events and then terminal done.
5. UI layer list/map state converges to visible renamed output layer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import api.run_service as run_service_module
from api.layer_service import LayerService
from api.run_service import RunService
from tools.artifact_provider import LocalArtifactProvider


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


def test_workflow_op_actions_create_show_rename_chain() -> None:
    async def _run() -> None:
        out = Path("data/test_actions_chain.geojson")
        out.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [],
                }
            ),
            encoding="utf-8",
        )
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _builder_factory({"actions": [], "outputs": []})
        try:
            rs = RunService()
            ls = LayerService()
            ap = LocalArtifactProvider()

            session_id = "sess_actions_chain"
            ls.init_session(session_id)
            run = rs.create_run(session_id)

            # First execute create+show only, then run rename in a second run
            # because rename needs concrete layerId from create result.
            run_service_module.build_main_graph = _builder_factory(
                {
                    "actions": [
                        {
                            "action": "create_layer_from_artifact",
                            "artifact": {
                                "path": str(out),
                                "format": "GEOJSON",
                                "description": "Generated temp layer",
                            },
                        },
                        {
                            "action": "show_created_layer",
                            "sourceActionIndex": 0,
                        },
                    ],
                    "outputs": [],
                }
            )

            events: list[str] = []

            async def _collect() -> None:
                async for event in rs.subscribe(run.runId):
                    events.append(event["type"])
                    if event["type"] in {"done", "error"}:
                        break

            collector = asyncio.create_task(_collect())
            await asyncio.sleep(0)
            await rs.execute_run(
                session_id=session_id,
                run_id=run.runId,
                message="create and show layer",
                layer_service=ls,
                artifact_provider=ap,
            )
            await collector

            status = rs.get_run(run.runId)
            assert status is not None and status.status == "completed"
            assert "layer_updated" in events

            layers = ls.list_layers(session_id)
            assert len(layers) == 1
            layer = layers[0]
            assert layer.visible is True
            assert layer.origin == "agent_output"
            assert layer.createdByRunId == run.runId
            assert layer.source.url.startswith("/api/artifacts/")

            # Rename action as a follow-up action-only run against known layer id.
            run2 = rs.create_run(session_id)
            run_service_module.build_main_graph = _builder_factory(
                {
                    "actions": [
                        {
                            "action": "rename_layer",
                            "layerId": layer.id,
                            "name": "Renamed Layer",
                        }
                    ],
                    "outputs": [],
                }
            )
            await rs.execute_run(
                session_id=session_id,
                run_id=run2.runId,
                message="rename created layer",
                layer_service=ls,
                artifact_provider=ap,
            )
            status2 = rs.get_run(run2.runId)
            assert status2 is not None and status2.status == "completed"
            renamed = ls.get_layer(layer.id)
            assert renamed is not None and renamed.name == "Renamed Layer"
        finally:
            run_service_module.build_main_graph = original_builder
            if out.exists():
                out.unlink()

    asyncio.run(_run())


def test_workflow_op_actions_invalid_source_action_index_fails() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _builder_factory(
            {
                "actions": [
                    {
                        "action": "show_created_layer",
                        "sourceActionIndex": 2,
                    }
                ],
                "outputs": [],
            }
        )
        try:
            rs = RunService()
            ls = LayerService()
            ap = LocalArtifactProvider()

            session_id = "sess_actions_bad_idx"
            ls.init_session(session_id)
            run = rs.create_run(session_id)

            await rs.execute_run(
                session_id=session_id,
                run_id=run.runId,
                message="bad sourceActionIndex",
                layer_service=ls,
                artifact_provider=ap,
            )
            status = rs.get_run(run.runId)
            assert status is not None and status.status == "failed"
            assert "sourceActionIndex out of range" in (status.error or "")
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())


def test_workflow_op_actions_create_without_show_autoshows_layer() -> None:
    async def _run() -> None:
        out = Path("data/test_actions_autoshow.geojson")
        out.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [],
                }
            ),
            encoding="utf-8",
        )
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _builder_factory(
            {
                "actions": [
                    {
                        "action": "create_layer_from_artifact",
                        "artifact": {
                            "path": str(out),
                            "format": "GEOJSON",
                            "description": "Auto-show layer",
                        },
                    }
                ],
                "outputs": [],
            }
        )
        try:
            rs = RunService()
            ls = LayerService()
            ap = LocalArtifactProvider()

            session_id = "sess_actions_autoshow"
            ls.init_session(session_id)
            run = rs.create_run(session_id)

            await rs.execute_run(
                session_id=session_id,
                run_id=run.runId,
                message="create only layer",
                layer_service=ls,
                artifact_provider=ap,
            )
            status = rs.get_run(run.runId)
            assert status is not None and status.status == "completed"

            layers = ls.list_layers(session_id)
            assert len(layers) == 1
            assert layers[0].visible is True
        finally:
            run_service_module.build_main_graph = original_builder
            if out.exists():
                out.unlink()

    asyncio.run(_run())
