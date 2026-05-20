from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from typing import BinaryIO

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .layer_service import LayerService
from .run_service import RunService
from .session_service import SessionService
from domain.state_models import ChatRequest, LayerPatchRequest, ResumeRunRequest
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
