from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from typing import List, Optional
from uuid import uuid4

from domain.state_models import LayerDescriptor, LayerPatchRequest


class LayerService:
    def __init__(
        self,
        initial_layers_by_session: Optional[dict[str, list[LayerDescriptor]]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize layer registry service.

        Args:
            initial_layers_by_session: Optional preloaded session->layers map
                used to restore state on backend startup.
            on_change: Optional callback fired whenever layer state changes, so
                app-level persistence can flush updated snapshots.
        """
        # TODO(PROD): Replace in-memory storage with a durable repository
        # (e.g., PostgreSQL) keyed by session_id/layer_id, and optionally add
        # Redis caching for hot reads. Current dict-based storage is POC-only.
        self._layers_by_session: dict[str, list[LayerDescriptor]] = (
            initial_layers_by_session or {}
        )
        self._layer_index: dict[str, LayerDescriptor] = {}
        self._on_change = on_change
        self._rebuild_index()

    def init_session(self, session_id: str) -> None:
        if session_id not in self._layers_by_session:
            self._layers_by_session[session_id] = []
            self._notify_changed()

    def list_layers(self, session_id: str) -> List[LayerDescriptor]:
        return list(self._layers_by_session.get(session_id, []))

    def get_layer(self, layer_id: str) -> Optional[LayerDescriptor]:
        return self._layer_index.get(layer_id)

    def update_layer(
        self, layer_id: str, patch: LayerPatchRequest
    ) -> Optional[LayerDescriptor]:
        existing = self.get_layer(layer_id)
        if existing is None:
            return None

        # Pydantic v2: model_dump() converts the patch model into a plain dict.
        # exclude_none=True keeps only fields explicitly provided by the client.
        updates = patch.model_dump(exclude_none=True)
        if not updates:
            return existing

        # Pydantic v2: model_copy(update=...) creates a new model where only
        # keys in `updates` are replaced; all other existing fields are preserved.
        updated = existing.model_copy(update=updates)
        self._layer_index[layer_id] = updated

        for session_id, layers in self._layers_by_session.items():
            for idx, layer in enumerate(layers):
                if layer.id == layer_id:
                    layers[idx] = updated
                    break
            else:
                continue
            break

        self._notify_changed()
        return updated

    def add_layer(self, session_id: str, layer: LayerDescriptor) -> LayerDescriptor:
        self.init_session(session_id)
        self._layers_by_session[session_id].append(layer)
        self._layer_index[layer.id] = layer
        self._notify_changed()
        return layer

    def create_layer_id(self, prefix: str = "lyr") -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def dump_state(self) -> dict[str, list[dict]]:
        """Return JSON-serializable snapshot of session-layer registry.

        Output shape is `session_id -> [LayerDescriptor as dict, ...]` and is
        consumed by persistence restore on backend startup.
        """
        return {
            sid: [layer.model_dump() for layer in layers]
            for sid, layers in self._layers_by_session.items()
        }

    def _rebuild_index(self) -> None:
        self._layer_index = {}
        for layers in self._layers_by_session.values():
            for layer in layers:
                self._layer_index[layer.id] = layer

    def _notify_changed(self) -> None:
        if self._on_change is not None:
            self._on_change()
