"""In-memory credential store for Telegram MFA secrets."""

from __future__ import annotations

import asyncio


class CredentialStore:
    """A simple in-memory store for Telegram login secrets.

    Credentials are kept only in memory and retrieved once. Accessors wait
    asynchronously for values to be supplied, enabling safe exchange between
    the API and the Telegram client without persisting secrets to disk.
    """

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}
        self._events: dict[str, asyncio.Event] = {}

    def set(self, key: str, value: str) -> None:
        """Set a secret and notify any waiters."""
        self._secrets[key] = value
        self._events.setdefault(key, asyncio.Event()).set()

    async def get(self, key: str, timeout: int) -> str:
        """Wait for a secret to be available and return it.

        Raises:
            TimeoutError: if the secret is not provided within *timeout* seconds.
        """
        event = self._events.setdefault(key, asyncio.Event())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except (
            asyncio.TimeoutError
        ) as exc:  # pragma: no cover - behaviour tested indirectly
            raise TimeoutError(f"Timeout waiting for {key}") from exc
        return self._secrets.pop(key)

    def clear(self) -> None:
        """Remove all stored secrets."""
        self._secrets.clear()
        self._events.clear()


credential_store = CredentialStore()
