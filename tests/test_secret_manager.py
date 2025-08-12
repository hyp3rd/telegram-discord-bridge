"""Tests for the in-memory secret manager."""

import asyncio

from bridge.security.secret_manager import SecretManager


def test_secret_manager_set_get():
    """Secrets can be stored and retrieved asynchronously."""

    async def runner():
        manager = SecretManager.get_instance()
        await manager.set("code", 1234)
        value = await manager.get("code", timeout=1)
        assert value == 1234
        manager.clear("code")

    asyncio.run(runner())
