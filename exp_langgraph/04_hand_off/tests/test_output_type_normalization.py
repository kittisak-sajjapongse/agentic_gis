from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


async def _run_test() -> None:
    parquet_path = str(Path("data/hotspot_2025.parquet"))
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

    logger = logging.getLogger("api.run_service")
    captured_logs: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured_logs.append(self.format(record))

    handler = _Capture()
    handler.setLevel(logging.WARNING)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)

    try:
        run_service = RunService()
        layer_service = LayerService()
        artifact_provider = LocalArtifactProvider()

        session_id = "sess_norm"
        layer_service.init_session(session_id)
        run = run_service.create_run(session_id)

        await run_service.execute_run(
            session_id=session_id,
            run_id=run.runId,
            message="test output type normalization",
            layer_service=layer_service,
            artifact_provider=artifact_provider,
        )

        layers = layer_service.list_layers(session_id)
        assert len(layers) == 3, f"Expected 3 layers, got {len(layers)}"
        assert all("/api/artifacts/" in layer.source.url for layer in layers)
        assert any("Unknown output_type=SOME_UNKNOWN_TYPE" in line for line in captured_logs), (
            "Expected warning log for unknown output type"
        )

        print("PASS: output type normalization and unknown-type warning behavior")
        print(f"run_id={run.runId} layers={len(layers)} warnings={len(captured_logs)}")
    finally:
        run_service_module.build_main_graph = original_builder
        logger.removeHandler(handler)


if __name__ == "__main__":
    asyncio.run(_run_test())
