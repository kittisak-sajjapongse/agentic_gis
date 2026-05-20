from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import BinaryIO

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import geopandas as gpd

from .layer_service import LayerService
from .run_service import RunService
from .session_service import SessionService
from domain.gis_catalog import GIS_COLLECTION
from domain.state_models import (
    CatalogImportRequest,
    ChatRequest,
    LayerDescriptor,
    LayerPatchRequest,
    LayerSource,
    LayerStyle,
    ResumeRunRequest,
)
from runtime.settings import AppSettings
from tools import LocalArtifactProvider


def create_app() -> FastAPI:
    app = FastAPI(title="04_hand_off API", version="0.1.0")
    settings = AppSettings.from_env()
    session_service = SessionService()
    layer_service = LayerService()
    run_service = RunService(data_mount_dir=settings.data_mount_dir)
    artifact_provider = LocalArtifactProvider()
    app.state.layer_service = layer_service
    app.state.run_service = run_service
    app.state.artifact_provider = artifact_provider
    catalog_index = {
        f"cat_{idx:03d}": item for idx, item in enumerate(GIS_COLLECTION, start=1)
    }

    def resolve_data_path(raw_path: str) -> Path:
        candidate = Path(raw_path)
        if candidate.exists():
            return candidate
        if raw_path.startswith("/data/"):
            return Path(settings.data_mount_dir) / raw_path.removeprefix("/data/")
        return candidate

    def convert_parquet_to_geojson(parquet_path: Path) -> Path:
        gdf = gpd.read_parquet(parquet_path)
        output_path = parquet_path.with_name(f"{parquet_path.stem}.catalog.geojson")
        output_path.write_text(gdf.to_json(default=str), encoding="utf-8")
        return output_path

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.post("/api/sessions")
    async def create_session() -> dict[str, str]:
        session = session_service.create_session()
        layer_service.init_session(session.sessionId)
        return {
            "sessionId": session.sessionId,
            "createdAt": session.createdAt,
        }

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> dict[str, str | None]:
        session = session_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "sessionId": session.sessionId,
            "status": session.status,
            "lastRunId": session.lastRunId,
        }

    @app.get("/api/sessions/{session_id}/layers")
    async def list_session_layers(session_id: str) -> dict[str, list[dict]]:
        session = session_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        layers = layer_service.list_layers(session_id)
        # Pydantic v2: model_dump() serializes each model to a JSON-ready dict.
        return {"layers": [layer.model_dump() for layer in layers]}

    @app.get("/api/catalog")
    async def list_catalog() -> dict[str, list[dict]]:
        items: list[dict] = []
        for catalog_id, item in catalog_index.items():
            items.append(
                {
                    "catalogItemId": catalog_id,
                    "description": item.get("description"),
                    "file": item.get("file"),
                    "type": item.get("type"),
                    "continent": item.get("continent"),
                    "country": item.get("country"),
                    "areaName": item.get("area_name"),
                    "year": item.get("year"),
                    "month": item.get("month"),
                    "day": item.get("day"),
                    "time": item.get("time"),
                }
            )
        return {"items": items}

    @app.post("/api/sessions/{session_id}/layers/import")
    async def import_catalog_layer(
        session_id: str, payload: CatalogImportRequest
    ) -> dict:
        session = session_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        catalog_item = catalog_index.get(payload.catalogItemId)
        if catalog_item is None:
            raise HTTPException(status_code=404, detail="Catalog item not found")

        raw_file = str(catalog_item.get("file", ""))
        resolved = resolve_data_path(raw_file)
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"Catalog file not found on backend host: {resolved}",
            )

        source_artifact_id: str
        kind = "geojson"
        source_type = "geojson"
        style = LayerStyle(preset="line-default")
        suffix = resolved.suffix.lower()
        catalog_type = str(catalog_item.get("type", "")).upper()

        if catalog_type == "GEOTIFF" or suffix in {".tif", ".tiff"}:
            kind = "raster"
            source_type = "raster"
            style = LayerStyle(preset="raster-default")
            artifact = artifact_provider.register_artifact(
                path=str(resolved), content_type="image/tiff"
            )
            source_artifact_id = artifact.artifact_id
        elif catalog_type == "GEOPARQUET" or suffix == ".parquet":
            artifact_provider.register_artifact(
                path=str(resolved), content_type="application/vnd.apache.parquet"
            )
            geojson_path = convert_parquet_to_geojson(resolved)
            converted = artifact_provider.register_artifact(
                path=str(geojson_path), content_type="application/geo+json"
            )
            source_artifact_id = converted.artifact_id
        elif suffix == ".geojson":
            artifact = artifact_provider.register_artifact(
                path=str(resolved), content_type="application/geo+json"
            )
            source_artifact_id = artifact.artifact_id
        else:
            artifact = artifact_provider.register_artifact(
                path=str(resolved), content_type="application/octet-stream"
            )
            source_artifact_id = artifact.artifact_id

        layer = LayerDescriptor(
            id=layer_service.create_layer_id(prefix="lyr_in"),
            name=payload.name or str(catalog_item.get("description", payload.catalogItemId)),
            kind=kind,  # type: ignore[arg-type]
            source=LayerSource(
                type=source_type,
                url=f"/api/artifacts/{source_artifact_id}/content",
            ),
            style=style,
            visible=True,
            origin="input",
            createdAt=layer_service.now_iso(),
        )
        layer_service.add_layer(session_id, layer)
        return layer.model_dump()

    @app.get("/api/layers/{layer_id}")
    async def get_layer(layer_id: str) -> dict:
        layer = layer_service.get_layer(layer_id)
        if layer is None:
            raise HTTPException(status_code=404, detail="Layer not found")
        # model_dump() is used so the HTTP response is plain JSON data.
        return layer.model_dump()

    @app.patch("/api/layers/{layer_id}")
    async def patch_layer(layer_id: str, patch: LayerPatchRequest) -> dict:
        if patch.opacity is not None and not (0.0 <= patch.opacity <= 1.0):
            raise HTTPException(
                status_code=400,
                detail="Invalid opacity: must be between 0.0 and 1.0",
            )
        layer = layer_service.update_layer(layer_id, patch)
        if layer is None:
            raise HTTPException(status_code=404, detail="Layer not found")
        # model_dump() serializes the updated Pydantic model for response output.
        return layer.model_dump()

    @app.post("/api/sessions/{session_id}/chat")
    async def chat(session_id: str, payload: ChatRequest) -> dict[str, str]:
        session = session_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        run = run_service.create_run(session_id)
        session_service.set_last_run(session_id, run.runId)

        # Schedule graph execution in the background and return runId immediately.
        # Clients observe progress/terminal state via GET /api/runs/{run_id}
        # (polling now; SSE stream endpoint is planned in BACKEND-006).
        # TODO(PROD): Replace in-process asyncio task scheduling with a durable
        # background job queue/worker so runs survive API restarts and support
        # multi-worker deployment semantics.
        asyncio.create_task(
            run_service.execute_run(
                session_id=session_id,
                run_id=run.runId,
                message=payload.message,
                layer_service=layer_service,
                artifact_provider=artifact_provider,
            )
        )
        return {"runId": run.runId}

    @app.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict:
        run = run_service.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run.model_dump()

    @app.get("/api/runs/{run_id}/stream")
    async def stream_run(run_id: str) -> StreamingResponse:
        if run_service.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")

        async def event_generator():
            async for event in run_service.subscribe(run_id):
                yield f"event: {event['type']}\n"
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    @app.post("/api/runs/{run_id}/resume")
    async def resume_run(run_id: str, payload: ResumeRunRequest) -> dict:
        try:
            # Validate resume request synchronously so API can fail fast on
            # invalid run/interrupt ids before scheduling background execution.
            run_service.validate_resume_request(run_id, payload.interruptId)
            # Resume runs in background so clients can subscribe to SSE first
            # and receive live events (layer_created, tool_end, done/error).
            asyncio.create_task(
                run_service.resume_run(
                    run_id=run_id,
                    interrupt_id=payload.interruptId,
                    answer=payload.answer,
                    layer_service=layer_service,
                    artifact_provider=artifact_provider,
                )
            )
            return {"runId": run_id}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/artifacts/{artifact_id}/content")
    async def get_artifact_content(artifact_id: str) -> StreamingResponse:
        metadata = artifact_provider.get_metadata(artifact_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Artifact not found")

        file_handle: BinaryIO = artifact_provider.open_content(artifact_id)
        return StreamingResponse(file_handle, media_type=metadata.content_type)

    return app


app = create_app()
