from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
import json
from pathlib import Path
from typing import Any


class PersistenceBackend(str, Enum):
    JSON = "json"
    SQLITE = "sqlite"


class PersistenceStore(ABC):
    """Abstract persistence interface for API state snapshots.

    Implementations can back this with JSON files, SQLite, or other stores.
    Callers should depend on this interface only.
    """

    @abstractmethod
    def load(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class JsonPersistenceStore(PersistenceStore):
    """JSON-file implementation of PersistenceStore for POC."""

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._path)


def build_persistence_store(
    backend: str,
    source: str,
) -> PersistenceStore:
    """Factory for persistence backends.

    Args:
        backend: backend selector (e.g. "json", "sqlite").
        source: backend source/DSN/path (for json: file path).
    """
    normalized = (backend or "").strip().lower()
    try:
        resolved = (
            PersistenceBackend.JSON
            if normalized == ""
            else PersistenceBackend(normalized)
        )
    except ValueError as exc:
        raise ValueError(
            f"Unsupported persistence backend: {backend!r}. "
            f"Supported: {PersistenceBackend.JSON.value}, {PersistenceBackend.SQLITE.value}"
        ) from exc

    if resolved == PersistenceBackend.JSON:
        return JsonPersistenceStore(source)
    if resolved == PersistenceBackend.SQLITE:
        raise NotImplementedError(
            "SQLite persistence backend is not implemented yet. "
            "Set POC_PERSISTENCE_BACKEND=json for now."
        )
    raise ValueError(f"Unsupported persistence backend: {backend!r}")
