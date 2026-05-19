from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import logging
import traceback
from typing import Any, AsyncIterator
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from api.layer_service import LayerService
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle, RunModel
from graphs.main_graph import build_main_graph
from graphs.input_retrieval_graph import IR_CLARIFICATION_INTERRUPT_TYPE
from graphs.output_producer_graph import OP_CLARIFICATION_INTERRUPT_TYPE
from tools.artifact_provider import ArtifactProvider

logger = logging.getLogger(__name__)


class RunService:
    def __init__(self, data_mount_dir: str | None = None) -> None:
        self._runs: dict[str, RunModel] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        # POC in-memory execution context store for resume support.
        self._graphs: dict[str, Any] = {}
        self._configs: dict[str, dict[str, Any]] = {}
        self._data_mount_dir = (
            Path(data_mount_dir) if data_mount_dir else (Path.cwd() / "data")
        )

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_run(self, session_id: str) -> RunModel:
        run = RunModel(
            runId=f"run_{uuid4().hex[:12]}",
            sessionId=session_id,
            status="queued",
            startedAt=self._now_iso(),
        )
        self._runs[run.runId] = run
        return run

    def get_run(self, run_id: str) -> RunModel | None:
        return self._runs.get(run_id)

    def _update_run(self, run_id: str, **updates: Any) -> RunModel | None:
        run = self.get_run(run_id)
        if run is None:
            return None
        updated = run.model_copy(update=updates)
        self._runs[run_id] = updated
        return updated

    def _emit_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        run = self.get_run(run_id)
        if run is None:
            return
        event = {
            "type": event_type,
            "runId": run_id,
            "sessionId": run.sessionId,
            "timestamp": self._now_iso(),
            "payload": payload,
        }
        for queue in self._subscribers.get(run_id, []):
            queue.put_nowait(event)

    def _terminal_event_for_run(self, run: RunModel) -> dict[str, Any] | None:
        if run.status == "completed":
            payload: dict[str, Any] = {"status": "completed"}
            if run.declineMessage:
                payload["declineMessage"] = run.declineMessage
            return {
                "type": "done",
                "runId": run.runId,
                "sessionId": run.sessionId,
                "timestamp": self._now_iso(),
                "payload": payload,
            }
        if run.status == "interrupted":
            return {
                "type": "clarification_required",
                "runId": run.runId,
                "sessionId": run.sessionId,
                "timestamp": self._now_iso(),
                "payload": {
                    "interruptId": run.pendingInterruptId,
                    "question": run.pendingQuestion or "Need clarification to continue.",
                },
            }
        if run.status == "failed":
            return {
                "type": "error",
                "runId": run.runId,
                "sessionId": run.sessionId,
                "timestamp": self._now_iso(),
                "payload": {
                    "status": run.status,
                    "message": run.error or "Run interrupted",
                },
            }
        return None

    def _extract_clarification(self, state: Any) -> tuple[str | None, str | None]:
        if not state or not getattr(state, "interrupts", None):
            return None, None
        matches = [
            intr
            for intr in state.interrupts
            if isinstance(getattr(intr, "value", None), dict)
            and intr.value.get("type")
            in {IR_CLARIFICATION_INTERRUPT_TYPE, OP_CLARIFICATION_INTERRUPT_TYPE}
        ]
        if len(matches) != 1:
            return None, None
        matched = matches[0]
        return matched.id, matched.value.get("question")

    def _actionable_error_message(self, exc: Exception) -> str:
        msg = str(exc)
        lowered = msg.lower()
        if "api_key" in lowered or "openai_api_key" in lowered:
            return (
                "Missing OpenAI API key. Set OPENAI_API_KEY in .env or env vars, "
                "then restart the API server."
            )
        if "all connection attempts failed" in lowered or "connecterror" in lowered:
            return (
                "Failed to connect to MCP SSE server. Start mcp_server.py and/or set "
                "MCP_SERVER_URL to a reachable endpoint, then retry."
            )
        if "taskgroup" in lowered:
            return (
                "A background task group failed. Check the traceback above for the "
                "first nested exception (often MCP/OpenAI connectivity)."
            )
        return "Run failed. Check traceback in backend logs for root cause."

    def _build_layer_from_output(
        self,
        session_id: str,
        run_id: str,
        output: dict[str, Any],
        layer_service: LayerService,
        artifact_provider: ArtifactProvider,
    ) -> LayerDescriptor | None:
        output_path = output.get("path")
        output_type = output.get("output_type")
        description = output.get("description", "Generated output layer")
        if not isinstance(output_path, str) or not output_path:
            return None

        file_path = self._resolve_output_path(output_path)
        if not file_path.exists() or not file_path.is_file():
            return None

        suffix = file_path.suffix.lower()
        normalized_output_type = self._normalize_output_type(output_type)
        known_output_types = {"GEOPARQUET_LAYER", "GEOTIFF_LAYER"}
        if (
            normalized_output_type is not None
            and normalized_output_type not in known_output_types
        ):
            logger.warning(
                "Unknown output_type=%s for path=%s; applying suffix-based fallback",
                output_type,
                str(file_path),
            )
        content_type = "application/octet-stream"
        kind = "geojson"
        source_type = "geojson"
        style = LayerStyle(preset="line-default")
        source_artifact_id: str | None = None

        if normalized_output_type == "GEOTIFF_LAYER" or suffix in {".tif", ".tiff"}:
            content_type = "image/tiff"
            kind = "raster"
            source_type = "raster"
            style = LayerStyle(preset="raster-default")
        elif normalized_output_type == "GEOPARQUET_LAYER" or suffix == ".parquet":
            content_type = "application/vnd.apache.parquet"
            kind = "geojson"
            source_type = "geojson"
            style = LayerStyle(preset="line-default")
            # Keep raw parquet artifact for audit/download and create a converted
            # GeoJSON artifact for map rendering compatibility in the POC.
            artifact_provider.register_artifact(
                path=str(file_path),
                content_type=content_type,
            )
            geojson_path = self._convert_parquet_to_geojson(file_path, run_id)
            if geojson_path is not None:
                converted = artifact_provider.register_artifact(
                    path=str(geojson_path),
                    content_type="application/geo+json",
                )
                source_artifact_id = converted.artifact_id
            else:
                logger.warning(
                    "GeoParquet conversion failed for path=%s; falling back to raw artifact source",
                    str(file_path),
                )
        elif suffix == ".geojson":
            content_type = "application/geo+json"
            kind = "geojson"
            source_type = "geojson"
            style = LayerStyle(preset="line-default")

        if source_artifact_id is None:
            artifact = artifact_provider.register_artifact(
                path=str(file_path),
                content_type=content_type,
            )
            source_artifact_id = artifact.artifact_id
        layer_id = layer_service.create_layer_id(prefix="lyr_out")
        layer = LayerDescriptor(
            id=layer_id,
            name=description,
            kind=kind,  # type: ignore[arg-type]
            source=LayerSource(
                type=source_type,
                url=f"/api/artifacts/{source_artifact_id}/content",
            ),
            style=style,
            visible=True,
            origin="agent_output",
            createdByRunId=run_id,
            createdAt=layer_service.now_iso(),
        )
        layer_service.add_layer(session_id, layer)
        return layer

    def _resolve_output_path(self, output_path: str) -> Path:
        raw = Path(output_path)
        if raw.exists():
            return raw
        # Agent tooling often emits container paths under /data/<file>.*
        # Map those to backend-visible host mount dir (default: <repo>/data).
        if output_path.startswith("/data/"):
            return self._data_mount_dir / output_path.removeprefix("/data/")
        return raw

    def _convert_parquet_to_geojson(self, parquet_path: Path, run_id: str) -> Path | None:
        try:
            import geopandas as gpd

            gdf = gpd.read_parquet(parquet_path)
            output_path = parquet_path.with_name(
                f"{parquet_path.stem}.run_{run_id}.geojson"
            )
            output_path.write_text(gdf.to_json(default=str), encoding="utf-8")
            return output_path
        except Exception as exc:
            logger.exception(
                "Failed to convert GeoParquet to GeoJSON path=%s run_id=%s error=%s",
                str(parquet_path),
                run_id,
                str(exc),
            )
            return None

    def _normalize_output_type(self, output_type: Any) -> str | None:
        if not isinstance(output_type, str):
            return None
        normalized = output_type.strip().upper()
        aliases = {
            "GEOPARQUET": "GEOPARQUET_LAYER",
            "GEOPARQUET_LAYER": "GEOPARQUET_LAYER",
            "GEOTIFF": "GEOTIFF_LAYER",
            "GEOTIFF_LAYER": "GEOTIFF_LAYER",
        }
        return aliases.get(normalized, normalized)

    def _emit_decline_if_present(self, run_id: str, state: Any) -> None:
        if not state or not getattr(state, "values", None):
            return
        decline_message = state.values.get("decline_message")
        if isinstance(decline_message, str) and decline_message.strip():
            clean_message = decline_message.strip()
            self._update_run(run_id, declineMessage=clean_message)
            self._emit_event(
                run_id,
                "decline",
                {"message": clean_message},
            )

    def subscribe(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to run events as an async iterator for SSE streaming.

        How it works:
        1. Each subscriber gets its own asyncio.Queue attached to `run_id`.
        2. `execute_run()` emits events through `_emit_event(...)`, which pushes
           event dicts into all subscriber queues for that run.
        3. On connect, subscriber immediately receives a synthetic `message`
           event containing current run status for state sync.
        4. If run is already terminal (`completed`, `failed`, `interrupted`),
           subscriber receives a terminal catch-up event (`done` or `error`) and
           returns without waiting.
        5. Otherwise it waits for queued events and yields them in FIFO order.
        6. On terminal event, iterator exits and subscriber queue is removed.

        Important: subscribe() does not talk to LangGraph directly. It consumes
        status/events produced by RunService methods while `execute_run()` runs.
        """
        if self.get_run(run_id) is None:
            raise KeyError(f"Run not found: {run_id}")

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)

        async def _iter() -> AsyncIterator[dict[str, Any]]:
            try:
                # Send current run status immediately so clients can sync on connect.
                run = self.get_run(run_id)
                if run is not None:
                    yield {
                        "type": "message",
                        "runId": run.runId,
                        "sessionId": run.sessionId,
                        "timestamp": self._now_iso(),
                        "payload": {"status": run.status},
                    }
                    terminal = self._terminal_event_for_run(run)
                    if terminal is not None:
                        yield terminal
                        return

                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        # Catch terminal state even if subscriber connected after
                        # events were emitted and no queue messages remain.
                        run = self.get_run(run_id)
                        if run is not None:
                            terminal = self._terminal_event_for_run(run)
                            if terminal is not None:
                                yield terminal
                                break
                        continue
                    yield event
                    if event["type"] in {"done", "error", "clarification_required"}:
                        break
            finally:
                subscribers = self._subscribers.get(run_id, [])
                if queue in subscribers:
                    subscribers.remove(queue)
                if not subscribers and run_id in self._subscribers:
                    self._subscribers.pop(run_id, None)

        return _iter()

    async def execute_run(
        self,
        session_id: str,
        run_id: str,
        message: str,
        layer_service: LayerService | None = None,
        artifact_provider: ArtifactProvider | None = None,
    ) -> None:
        """Execute one chat run against LangGraph and publish run events.

        Status source of truth:
        - LangGraph execution itself is driven here (`graph.astream(...)`).
        - As execution progresses/completes/fails, this method updates RunModel
          via `_update_run(...)` and emits events via `_emit_event(...)`.
        - `subscribe()` readers receive those emitted events through queues.
        """
        self._update_run(run_id, status="running", declineMessage=None)
        self._emit_event(run_id, "message", {"text": "Run started", "status": "running"})
        self._emit_event(run_id, "tool_start", {"tool": "main_graph", "status": "started"})
        try:
            # TODO: Move to session-scoped graph caching (lazy init + TTL cleanup)
            # to avoid rebuilding the graph/tool stack on every chat run.
            graph = await build_main_graph()
            config = {"configurable": {"thread_id": session_id}}
            self._graphs[run_id] = graph
            self._configs[run_id] = config
            inputs = {"_messages": [HumanMessage(content=message)]}

            async for _ in graph.astream(inputs, config=config):
                pass

            state = await graph.aget_state(config)
            self._emit_decline_if_present(run_id, state)
            if layer_service is not None and artifact_provider is not None:
                outputs = state.values.get("outputs") if state and state.values else None
                if isinstance(outputs, list):
                    for output in outputs:
                        if not isinstance(output, dict):
                            continue
                        layer = self._build_layer_from_output(
                            session_id=session_id,
                            run_id=run_id,
                            output=output,
                            layer_service=layer_service,
                            artifact_provider=artifact_provider,
                        )
                        if layer is not None:
                            self._emit_event(
                                run_id,
                                "layer_created",
                                {"layerId": layer.id},
                            )

            if state.interrupts:
                interrupt_id, question = self._extract_clarification(state)
                self._update_run(
                    run_id,
                    status="interrupted",
                    pendingInterruptId=interrupt_id,
                    pendingQuestion=question,
                )
                self._emit_event(
                    run_id,
                    "tool_end",
                    {"tool": "main_graph", "status": "interrupted"},
                )
                self._emit_event(
                    run_id,
                    "clarification_required",
                    {
                        "interruptId": interrupt_id,
                        "question": question or "Need clarification to continue.",
                    },
                )
                return

            self._update_run(
                run_id,
                status="completed",
                finishedAt=self._now_iso(),
                pendingInterruptId=None,
                pendingQuestion=None,
            )
            self._emit_event(
                run_id,
                "tool_end",
                {"tool": "main_graph", "status": "completed"},
            )
            self._emit_event(
                run_id,
                "done",
                {"status": "completed"},
            )
            self._graphs.pop(run_id, None)
            self._configs.pop(run_id, None)
        except Exception as exc:
            actionable = self._actionable_error_message(exc)
            logger.exception(
                "Run failed run_id=%s session_id=%s error=%s actionable=%s\n%s",
                run_id,
                session_id,
                str(exc),
                actionable,
                traceback.format_exc(),
            )
            self._update_run(
                run_id,
                status="failed",
                error=str(exc),
                finishedAt=self._now_iso(),
            )
            self._emit_event(
                run_id,
                "tool_end",
                {"tool": "main_graph", "status": "failed"},
            )
            self._emit_event(
                run_id,
                "error",
                {"message": str(exc), "actionable": actionable},
            )
            self._graphs.pop(run_id, None)
            self._configs.pop(run_id, None)

    async def resume_run(
        self,
        run_id: str,
        interrupt_id: str,
        answer: str,
        layer_service: LayerService | None = None,
        artifact_provider: ArtifactProvider | None = None,
    ) -> RunModel:
        run, graph, config = self.validate_resume_request(run_id, interrupt_id)

        self._update_run(
            run_id,
            status="running",
            pendingInterruptId=None,
            pendingQuestion=None,
            error=None,
            declineMessage=None,
        )
        self._emit_event(run_id, "message", {"text": "Run resumed", "status": "running"})
        self._emit_event(run_id, "tool_start", {"tool": "main_graph", "status": "resumed"})
        try:
            inputs = Command(resume={interrupt_id: answer})
            async for _ in graph.astream(inputs, config=config):
                pass

            state = await graph.aget_state(config)
            self._emit_decline_if_present(run_id, state)
            if layer_service is not None and artifact_provider is not None:
                outputs = state.values.get("outputs") if state and state.values else None
                if isinstance(outputs, list):
                    for output in outputs:
                        if not isinstance(output, dict):
                            continue
                        layer = self._build_layer_from_output(
                            session_id=run.sessionId,
                            run_id=run_id,
                            output=output,
                            layer_service=layer_service,
                            artifact_provider=artifact_provider,
                        )
                        if layer is not None:
                            self._emit_event(run_id, "layer_created", {"layerId": layer.id})

            if state.interrupts:
                interrupt_id2, question2 = self._extract_clarification(state)
                self._update_run(
                    run_id,
                    status="interrupted",
                    pendingInterruptId=interrupt_id2,
                    pendingQuestion=question2,
                )
                self._emit_event(run_id, "tool_end", {"tool": "main_graph", "status": "interrupted"})
                self._emit_event(
                    run_id,
                    "clarification_required",
                    {
                        "interruptId": interrupt_id2,
                        "question": question2 or "Need clarification to continue.",
                    },
                )
                return self.get_run(run_id)  # type: ignore[return-value]

            self._update_run(
                run_id,
                status="completed",
                finishedAt=self._now_iso(),
                pendingInterruptId=None,
                pendingQuestion=None,
            )
            self._emit_event(run_id, "tool_end", {"tool": "main_graph", "status": "completed"})
            self._emit_event(run_id, "done", {"status": "completed"})
            self._graphs.pop(run_id, None)
            self._configs.pop(run_id, None)
            return self.get_run(run_id)  # type: ignore[return-value]
        except Exception as exc:
            actionable = self._actionable_error_message(exc)
            logger.exception(
                "Run resume failed run_id=%s session_id=%s error=%s actionable=%s\n%s",
                run_id,
                run.sessionId,
                str(exc),
                actionable,
                traceback.format_exc(),
            )
            self._update_run(
                run_id,
                status="failed",
                error=str(exc),
                finishedAt=self._now_iso(),
            )
            self._emit_event(run_id, "tool_end", {"tool": "main_graph", "status": "failed"})
            self._emit_event(run_id, "error", {"message": str(exc), "actionable": actionable})
            self._graphs.pop(run_id, None)
            self._configs.pop(run_id, None)
            return self.get_run(run_id)  # type: ignore[return-value]

    def validate_resume_request(self, run_id: str, interrupt_id: str) -> tuple[RunModel, Any, dict[str, Any]]:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError("Run not found")
        if run.status != "interrupted":
            raise ValueError("Run is not in interrupted state")
        if run.pendingInterruptId != interrupt_id:
            raise ValueError("Interrupt ID does not match pending run interrupt")

        graph = self._graphs.get(run_id)
        config = self._configs.get(run_id)
        if graph is None or config is None:
            raise RuntimeError(
                "Resume context unavailable for run. "
                "Start a new run (POC limitation: in-memory graph context)."
            )
        return run, graph, config
