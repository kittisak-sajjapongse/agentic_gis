from __future__ import annotations

from datetime import datetime, timezone
from typing import BinaryIO

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .layer_service import LayerService
from .session_service import SessionService
from domain.state_models import LayerPatchRequest
from tools import LocalArtifactProvider


def create_app() -> FastAPI:
    app = FastAPI(title="04_hand_off API", version="0.1.0")
    session_service = SessionService()
    layer_service = LayerService()
    artifact_provider = LocalArtifactProvider()
    app.state.layer_service = layer_service
    app.state.artifact_provider = artifact_provider

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
        return {"layers": [layer.model_dump() for layer in layers]}

    @app.get("/api/layers/{layer_id}")
    async def get_layer(layer_id: str) -> dict:
        layer = layer_service.get_layer(layer_id)
        if layer is None:
            raise HTTPException(status_code=404, detail="Layer not found")
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
        return layer.model_dump()

    @app.get("/api/artifacts/{artifact_id}/content")
    async def get_artifact_content(artifact_id: str) -> StreamingResponse:
        metadata = artifact_provider.get_metadata(artifact_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Artifact not found")

        file_handle: BinaryIO = artifact_provider.open_content(artifact_id)
        return StreamingResponse(file_handle, media_type=metadata.content_type)

    return app


app = create_app()
