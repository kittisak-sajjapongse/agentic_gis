"""Regression: non-empty legacy `outputs` must fail fast in run processing.

This protects BACKEND-017 contract enforcement:
- RunService no longer executes legacy outputs-based layer creation path.
- Any non-empty `outputs` payload should raise a clear contract error and
  transition run status to `failed`.
"""

from __future__ import annotations

import asyncio

import api.run_service as run_service_module
from api.run_service import RunService


class _FakeStateLegacyOutputs:
    def __init__(self):
        self.values = {
            "outputs": [
                {
                    "output_type": "GEOPARQUET_LAYER",
                    "description": "legacy payload",
                    "path": "/data/legacy.parquet",
                }
            ],
            "actions": [],
        }
        self.interrupts = []


class _FakeGraphLegacyOutputs:
    async def astream(self, inputs, config=None):
        if False:
            yield None

    async def aget_state(self, config=None):
        return _FakeStateLegacyOutputs()


async def _fake_build_main_graph():
    return _FakeGraphLegacyOutputs()


def test_legacy_outputs_fail_fast() -> None:
    async def _run() -> None:
        original_builder = run_service_module.build_main_graph
        run_service_module.build_main_graph = _fake_build_main_graph
        try:
            rs = RunService()
            run = rs.create_run("sess_legacy_outputs")

            await rs.execute_run(
                session_id="sess_legacy_outputs",
                run_id=run.runId,
                message="trigger legacy outputs",
            )

            final_run = rs.get_run(run.runId)
            assert final_run is not None
            assert final_run.status == "failed"
            assert final_run.error is not None
            assert "Legacy `outputs` payload is no longer supported" in final_run.error
        finally:
            run_service_module.build_main_graph = original_builder

    asyncio.run(_run())

