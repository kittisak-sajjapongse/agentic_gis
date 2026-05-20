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
    parquet_path = Path("data/burnscar_2025_01.parquet")
    assert parquet_path.exists(), "Expected data/burnscar_2025_01.parquet to exist"

    outputs = [
        {
            "output_type": "GEOPARQUET",
            "description": "Hotspot points (converted)",
            "path": str(parquet_path),
        }
    ]

    original_builder = run_service_module.build_main_graph
    run_service_module.build_main_graph = _build_fake_graph_factory(outputs)

    converted_geojson_path: Path | None = None
    try:
        run_service = RunService()
        layer_service = LayerService()
        artifact_provider = LocalArtifactProvider()

        session_id = "sess_render_conv"
        layer_service.init_session(session_id)
        run = run_service.create_run(session_id)

        await run_service.execute_run(
            session_id=session_id,
            run_id=run.runId,
            message="generate parquet output",
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

        converted_geojson_path = Path(source_meta.path)
        assert converted_geojson_path.suffix == ".geojson", source_meta.path
        assert converted_geojson_path.exists(), source_meta.path

        content = json.loads(converted_geojson_path.read_text(encoding="utf-8"))
        assert content.get("type") == "FeatureCollection"

        print("PASS: GeoParquet output converted and layer source points to GeoJSON artifact")
        print(f"run_id={run.runId} layer_id={layer.id} geojson={converted_geojson_path}")
    finally:
        run_service_module.build_main_graph = original_builder
        if converted_geojson_path and converted_geojson_path.exists():
            converted_geojson_path.unlink()


def test_geoparquet_conversion_render_source() -> None:
    asyncio.run(_run_test_impl())
