from __future__ import annotations

import asyncio
import json
from pathlib import Path

import api.run_service as run_service_module
from api.layer_service import LayerService
from api.run_service import RunService
from tools.artifact_provider import LocalArtifactProvider


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

    normalized_geojson_path: Path | None = None
    try:
        run_service = RunService()
        layer_service = LayerService()
        artifact_provider = LocalArtifactProvider()

        session_id = "sess_geojson_norm"
        layer_service.init_session(session_id)
        run = run_service.create_run(session_id)

        await run_service.execute_run(
            session_id=session_id,
            run_id=run.runId,
            message="normalize geojson output",
            layer_service=layer_service,
            artifact_provider=artifact_provider,
        )

        layers = layer_service.list_layers(session_id)
        assert len(layers) == 1, f"Expected 1 layer, got {len(layers)}"
        layer = layers[0]
        assert layer.source.type == "geojson"

        artifact_id = layer.source.url.split("/")[3]
        source_meta = artifact_provider.get_metadata(artifact_id)
        assert source_meta is not None, "Expected source artifact metadata"

        normalized_geojson_path = Path(source_meta.path)
        assert normalized_geojson_path.suffix == ".geojson", source_meta.path
        assert normalized_geojson_path.exists(), source_meta.path
        assert ".epsg4326.geojson" in normalized_geojson_path.name, source_meta.path

        content = json.loads(normalized_geojson_path.read_text(encoding="utf-8"))
        assert content.get("type") == "FeatureCollection"
        coords = content["features"][0]["geometry"]["coordinates"][0][0]
        lon, lat = coords
        assert -180.0 <= lon <= 180.0, f"Unexpected longitude: {lon}"
        assert -90.0 <= lat <= 90.0, f"Unexpected latitude: {lat}"

        print("PASS: direct GeoJSON output normalized to EPSG:4326 artifact")
        print(
            f"run_id={run.runId} layer_id={layer.id} geojson={normalized_geojson_path}"
        )
    finally:
        run_service_module.build_main_graph = original_builder
        if source_geojson.exists():
            source_geojson.unlink()
        if normalized_geojson_path and normalized_geojson_path.exists():
            normalized_geojson_path.unlink()


def test_geojson_output_epsg4326_normalization() -> None:
    asyncio.run(_run_test_impl())
