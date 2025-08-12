"""Tests for message forwarding helpers."""

# pylint: disable=protected-access,duplicate-code,import-error

import asyncio
import importlib
from types import SimpleNamespace

from bridge.config import config as config_module

from tests.fixtures import write_config


def test_process_message_text(tmp_path, monkeypatch):
    """Processed text includes mentions and roles."""
    cfg_file = write_config(tmp_path)
    monkeypatch.setattr(config_module, "_file_path", cfg_file)
    config_module._instances.clear()
    core = importlib.reload(importlib.import_module("bridge.core"))

    message = SimpleNamespace(message="hello", entities=None)
    result = asyncio.run(
        core.Bridge.process_message_text(
            message,
            strip_off_links=False,
            mention_everyone=True,
            mention_roles=["Admin"],
            openai_enabled=False,
        )
    )

    assert "@everyone" in result
    assert result.startswith("Admin")
