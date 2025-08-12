"""Tests for message forwarding helpers."""

# pylint: disable=protected-access,duplicate-code,import-error

import asyncio
import importlib
from types import SimpleNamespace

from telethon.tl.types import MessageEntityUrl

from bridge.config import config as config_module
from bridge.utils import extract_urls, transform_urls

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


def test_extract_urls_and_transform():
    """URLs are extracted and Twitter links are converted."""
    url = "https://x.com/test"
    message = SimpleNamespace(
        message=f"check {url}",
        entities=[MessageEntityUrl(offset=6, length=len(url))],
    )

    cleaned, urls = extract_urls(message)
    assert cleaned == "check"
    assert urls == [url]

    assert transform_urls(urls) == ["https://fixupx.com/test"]
