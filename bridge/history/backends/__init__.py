"""History storage backend implementations."""

from __future__ import annotations

from bridge.config.config import HistoryConfig

from .base import HistoryStorageBackend
from .json_backend import JSONHistoryBackend
from .sqlite_backend import SQLiteHistoryBackend


def get_backend(config: HistoryConfig) -> HistoryStorageBackend:
    """Instantiate the configured history backend."""
    mapping = {
        "json": JSONHistoryBackend,
        "sqlite": SQLiteHistoryBackend,
    }
    backend_cls = mapping.get(config.backend)
    if backend_cls is None:
        raise ValueError(f"Unsupported history backend {config.backend}")
    return backend_cls()


__all__ = [
    "HistoryStorageBackend",
    "JSONHistoryBackend",
    "SQLiteHistoryBackend",
    "get_backend",
]
