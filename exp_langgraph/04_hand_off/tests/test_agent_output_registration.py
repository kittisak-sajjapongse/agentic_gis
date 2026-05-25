from __future__ import annotations

"""
Purpose
-------
Validate actions-only behavior in RunService:
1) `show_layer` actions are applied through layer_show_service,
2) `layer_updated` SSE events are emitted, and
3) run reaches completed state.

Test style
----------
This is a controlled integration test for RunService internals, not a full
end-to-end graph test.

How it works
------------
2. Monkeypatch `api.run_service.build_main_graph` so RunService receives a fake
   graph object instead of the real LangGraph graph.
3. The fake graph returns a synthetic state with one action item in
   `state.values["actions"]`.
4. Run `RunService.execute_run(...)` with mocked layer show service.
5. Subscribe to RunService events and capture the emitted sequence.
6. Assert:
   - run reaches terminal completed state,
   - show-layer service was called with expected selector,
   - `layer_updated` event is emitted before terminal event.
6. Restore the original `build_main_graph`.

What this test does NOT validate
--------------------------------
- Real LLM execution
- Real MCP/tool execution
- Real LangGraph topology behavior from `build_main_graph()`

Those belong to a separate true end-to-end test path.
"""

import asyncio

import api.run_service as run_service_module
from api.run_service import RunService
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle


class FakeState:
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


class FakeGraph:
    async def astream(self, inputs, config=None):
        await asyncio.sleep(0.05)
        if False:
            yield None
        return

    async def aget_state(self, config=None):
        return FakeState()


def _build_fake_graph_factory():
    async def _fake_build_main_graph():
        return FakeGraph()

    return _fake_build_main_graph


async def _run_test_impl() -> None:
    original_builder = run_service_module.build_main_graph
    run_service_module.build_main_graph = _build_fake_graph_factory()

    try:
        run_service = RunService()

        session_id = "sess_test_output_register"
        run = run_service.create_run(session_id)
        
        class _MockLayerShowService:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str | None]] = []

            def show_layer(self, session_id: str, *, artifact=None, catalog_item_id=None, layer_id=None):
                self.calls.append((session_id, artifact))
                return LayerDescriptor(
                    id="lyr_stub_output_1",
                    name="Stub Layer",
                    kind="geojson",
                    source=LayerSource(type="geojson", url="/api/artifacts/stub/content"),
                    style=LayerStyle(preset="line-default"),
                    visible=True,
                    origin="input",
                    createdAt="2026-01-01T00:00:00Z",
                )

        action_service = _MockLayerShowService()

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
            layer_show_service=action_service,
        )
        await consumer

        final_run = run_service.get_run(run.runId)

        assert final_run is not None, "Run record must exist"
        assert final_run.status == "completed", f"Expected completed, got {final_run.status}"
        assert action_service.calls == [(session_id, "cat_001")]
        assert "layer_updated" in events, f"Expected layer_updated event, got {events}"
        assert events[-1] in {"done", "error"}, "Stream must end with terminal event"
    finally:
        run_service_module.build_main_graph = original_builder


def test_agent_output_registration() -> None:
    asyncio.run(_run_test_impl())
