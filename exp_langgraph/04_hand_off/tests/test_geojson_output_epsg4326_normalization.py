from __future__ import annotations

import asyncio
import json
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
    source_geojson = Path("data/test_projected_source.geojson")
    source_geojson.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "projected-square"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [537940.0, 2207140.0],
                                    [537940.0, 2207120.0],
                                    [537960.0, 2207120.0],
                                    [537960.0, 2207140.0],
                                    [537940.0, 2207140.0],
                                ]
                            ],
                        },
                    }
                ],
                "crs": {
                    "type": "name",
                    "properties": {"name": "urn:ogc:def:crs:EPSG::32647"},
                },
            }
        ),
        encoding="utf-8",
    )

    outputs = [
        {
            "description": "Projected geojson output",
            "path": str(source_geojson),
        }
    ]

    original_builder = run_service_module.build_main_graph
    run_service_module.build_main_graph = _build_fake_graph_factory(outputs)

    try:
        run_service = RunService()
        run = run_service.create_run("sess_geojson_norm")

        await run_service.execute_run(
            session_id="sess_geojson_norm",
            run_id=run.runId,
            message="normalize geojson output",
        )

        final = run_service.get_run(run.runId)
        assert final is not None and final.status == "failed"
        assert "Legacy `outputs` payload is no longer supported" in (final.error or "")
    finally:
        run_service_module.build_main_graph = original_builder
        if source_geojson.exists():
            source_geojson.unlink()


def test_geojson_output_epsg4326_normalization() -> None:
    asyncio.run(_run_test_impl())
