from __future__ import annotations

import asyncio
from pathlib import Path

import api.run_service as run_service_module
from api.run_service import RunService


class FakeState:
    def __init__(self, outputs):
        self.values = {"outputs": outputs}
        self.interrupts = []


class FakeGraph:
    def __init__(self, outputs):
        self._outputs = outputs

    async def astream(self, inputs, config=None):
        if False:
            yield None

    async def aget_state(self, config=None):
        return FakeState(self._outputs)


def _build_fake_graph_factory(outputs):
    async def _fake_build_main_graph():
        return FakeGraph(outputs)

    return _fake_build_main_graph


async def _run_test_impl() -> None:
    parquet_path = str(Path("data/burnscar_2025_01.parquet"))
    assert Path(parquet_path).exists(), "Expected fixture parquet file under data/"

    outputs = [
        {
            "output_type": "GEOPARQUET",
            "description": "Variant A",
            "path": parquet_path,
        },
        {
            "output_type": "GEOPARQUET_LAYER",
            "description": "Variant B",
            "path": parquet_path,
        },
        {
            "output_type": "SOME_UNKNOWN_TYPE",
            "description": "Variant C fallback by suffix",
            "path": parquet_path,
        },
    ]

    original_builder = run_service_module.build_main_graph
    run_service_module.build_main_graph = _build_fake_graph_factory(outputs)

    try:
        run_service = RunService()
        run = run_service.create_run("sess_norm")

        await run_service.execute_run(
            session_id="sess_norm",
            run_id=run.runId,
            message="test output type normalization",
        )

        final = run_service.get_run(run.runId)
        assert final is not None and final.status == "failed"
        assert "Legacy `outputs` payload is no longer supported" in (final.error or "")
    finally:
        run_service_module.build_main_graph = original_builder


def test_output_type_normalization() -> None:
    asyncio.run(_run_test_impl())
