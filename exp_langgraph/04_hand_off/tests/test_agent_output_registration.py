from __future__ import annotations

"""
Purpose
-------
Validate AGENT-002 behavior in RunService:
1) output artifacts are registered,
2) output layers are persisted in LayerService, and
3) `layer_created` SSE events are emitted.

Test style
----------
This is a controlled integration test for RunService internals, not a full
end-to-end graph test.

How it works
------------
1. Create a temporary GeoJSON output file under `data/`.
2. Monkeypatch `api.run_service.build_main_graph` so RunService receives a fake
   graph object instead of the real LangGraph graph.
3. The fake graph returns a synthetic state with one output item in
   `state.values["outputs"]`.
4. Run `RunService.execute_run(...)` with real LayerService and
   LocalArtifactProvider instances.
5. Subscribe to RunService events and capture the emitted sequence.
6. Assert:
   - run reaches terminal completed state,
   - one output layer is added to session layer registry,
   - layer source references `/api/artifacts/{artifact_id}/content`,
   - `layer_created` event is emitted before terminal event.
7. Restore the original `build_main_graph` and remove temp file in `finally`.

What this test does NOT validate
--------------------------------
- Real LLM execution
- Real MCP/tool execution
- Real LangGraph topology behavior from `build_main_graph()`

Those belong to a separate true end-to-end test path.
"""

import json
from pathlib import Path
import asyncio

import api.run_service as run_service_module
from api.layer_service import LayerService
from api.run_service import RunService
from tools.artifact_provider import LocalArtifactProvider


class FakeState:
    def __init__(self, output_path: str):
        self.values = {
            "outputs": [
                {
                    "output_type": "GEOPARQUET_LAYER",
                    "description": "Generated Test Layer",
                    "path": output_path,
                }
            ]
        }
        self.interrupts = []


class FakeGraph:
    def __init__(self, output_path: str):
        self._output_path = output_path

    async def astream(self, inputs, config=None):
        await asyncio.sleep(0.05)
        if False:
            yield None
        return

    async def aget_state(self, config=None):
        return FakeState(self._output_path)


def _build_fake_graph_factory(output_path: str):
    async def _fake_build_main_graph():
        return FakeGraph(output_path)

    return _fake_build_main_graph


async def _run_test_impl() -> None:
    output_file = Path("data/test_generated_output.geojson")
    output_file.write_text(
        json.dumps({"type": "FeatureCollection", "features": []}),
        encoding="utf-8",
    )

    original_builder = run_service_module.build_main_graph
    run_service_module.build_main_graph = _build_fake_graph_factory(str(output_file))

    try:
        run_service = RunService()
        layer_service = LayerService()
        artifact_provider = LocalArtifactProvider()

        session_id = "sess_test_output_register"
        layer_service.init_session(session_id)
        run = run_service.create_run(session_id)

        events: list[str] = []

        async def collect_events() -> None:
            async for event in run_service.subscribe(run.runId):
                events.append(event["type"])
                if event["type"] in {"done", "error"}:
                    break

        consumer = asyncio.create_task(collect_events())
        await asyncio.sleep(0)

        await run_service.execute_run(
            session_id=session_id,
            run_id=run.runId,
            message="generate one layer",
            layer_service=layer_service,
            artifact_provider=artifact_provider,
        )
        await consumer

        final_run = run_service.get_run(run.runId)
        layers = layer_service.list_layers(session_id)

        assert final_run is not None, "Run record must exist"
        assert final_run.status == "completed", f"Expected completed, got {final_run.status}"
        assert len(layers) == 1, f"Expected exactly 1 output layer, got {len(layers)}"
        assert layers[0].origin == "agent_output", "Output layer origin must be agent_output"
        assert layers[0].createdByRunId == run.runId, "Layer must reference originating run"
        assert "/api/artifacts/" in layers[0].source.url, "Layer source must point to artifact API"
        assert "layer_created" in events, f"Expected layer_created event, got {events}"
        assert events[-1] in {"done", "error"}, "Stream must end with terminal event"

        print("PASS: output layer registered and layer_created event emitted")
        print(f"run_id={run.runId} events={events} layer_id={layers[0].id}")
    finally:
        run_service_module.build_main_graph = original_builder
        if output_file.exists():
            output_file.unlink()


def test_agent_output_registration() -> None:
    asyncio.run(_run_test_impl())
