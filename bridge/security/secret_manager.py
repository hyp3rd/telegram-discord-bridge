"""In-memory secret manager for ephemeral credentials."""

import asyncio
from typing import Any, Dict

from core import SingletonMeta


class SecretManager(metaclass=SingletonMeta):
    """Simple in-memory secret store with async wait capabilities."""

    def __init__(self) -> None:
        self._secrets: Dict[str, Any] = {}
        self._events: Dict[str, asyncio.Event] = {}

    async def set(self, key: str, value: Any) -> None:
        """Store a secret and notify waiters."""
        self._secrets[key] = value
        event = self._events.setdefault(key, asyncio.Event())
        event.set()

    async def get(self, key: str, timeout: int | None = None) -> Any:
        """Retrieve a secret waiting until it becomes available."""
        if key in self._secrets:
            return self._secrets[key]
        event = self._events.setdefault(key, asyncio.Event())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError as ex:
            raise TimeoutError(f"Timeout waiting for {key}") from ex
        return self._secrets.get(key)

    def clear(self, key: str) -> None:
        """Remove a secret from the store."""
        self._secrets.pop(key, None)
        if key in self._events:
            self._events[key].clear()

    @staticmethod
    def get_instance() -> "SecretManager":
        """Return the singleton instance."""
        return SecretManager()
