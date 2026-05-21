from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Optional
from uuid import uuid4


@dataclass(frozen=True)
class ArtifactMetadata:
    artifact_id: str
    path: str
    content_type: str
    size_bytes: int


class ArtifactProvider(ABC):
    """Storage abstraction for layer artifacts used by backend APIs.

    Planned usage in this project:
    - Register input datasets and agent-generated outputs (GeoTIFF, GeoParquet,
      GeoJSON, reports) and receive a stable `artifact_id`.
    - Store only `artifact_id` references in session/layer metadata contracts.
    - Serve raw bytes through `/api/artifacts/{artifact_id}/content` by looking
      up metadata and opening a readable stream via this interface.
    - Swap storage backend later (local filesystem -> S3-compatible provider)
      without changing the UI contract or endpoint shapes.
    """
    @abstractmethod
    def register_artifact(
        self, path: str, content_type: Optional[str] = None
    ) -> ArtifactMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        raise NotImplementedError

    @abstractmethod
    def open_content(self, artifact_id: str) -> BinaryIO:
        raise NotImplementedError


class LocalArtifactProvider(ArtifactProvider):
    """Local-filesystem implementation for POC.

    This provider is intentionally simple:
    - Keeps an in-memory map from `artifact_id` -> metadata/path.
    - Reads bytes directly from local disk for artifact content endpoints.

    Notes for GeoTIFF and GeoParquet:
    - Raw files can be registered and streamed as-is.
    - Map rendering may still require transformation (e.g., tiles/GeoJSON),
      but those derived outputs should also be registered as artifacts.
    """
    def __init__(
        self,
        initial_artifacts: Optional[dict[str, ArtifactMetadata]] = None,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize local artifact registry.

        Args:
            initial_artifacts: Optional preloaded artifact metadata map for
                startup restore from persistence.
            on_change: Optional callback fired when artifact metadata changes,
                so app-level persistence can flush updated state.
        """
        self._artifacts: dict[str, ArtifactMetadata] = initial_artifacts or {}
        self._on_change = on_change

    def register_artifact(
        self, path: str, content_type: Optional[str] = None
    ) -> ArtifactMetadata:
        # Called when a layer source or agent output is created/imported.
        # The returned artifact_id becomes the stable handle used by APIs.
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"Artifact path not found: {path}")

        artifact_id = f"art_{uuid4().hex[:12]}"
        resolved_path = str(file_path.resolve())
        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            path=resolved_path,
            content_type=content_type or "application/octet-stream",
            size_bytes=file_path.stat().st_size,
        )
        self._artifacts[artifact_id] = metadata
        self._notify_changed()
        return metadata

    def get_metadata(self, artifact_id: str) -> Optional[ArtifactMetadata]:
        # Used by API handlers to validate existence and determine response MIME.
        return self._artifacts.get(artifact_id)

    def open_content(self, artifact_id: str) -> BinaryIO:
        # Used by `/api/artifacts/{artifact_id}/content` to stream bytes.
        metadata = self.get_metadata(artifact_id)
        if metadata is None:
            raise KeyError(f"Unknown artifact id: {artifact_id}")
        return open(metadata.path, "rb")

    def dump_state(self) -> dict[str, dict]:
        """Return JSON-serializable snapshot of artifact metadata index.

        Persisted artifact entries allow API restart without losing
        `artifact_id -> file path/content-type` resolution.
        """
        return {
            artifact_id: {
                "artifact_id": meta.artifact_id,
                "path": meta.path,
                "content_type": meta.content_type,
                "size_bytes": meta.size_bytes,
            }
            for artifact_id, meta in self._artifacts.items()
        }

    def _notify_changed(self) -> None:
        if self._on_change is not None:
            self._on_change()
