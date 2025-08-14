"""Tests for message forwarding helpers."""

# pylint: disable=protected-access,duplicate-code,import-error

import asyncio
import copy
import importlib
from collections import deque
from types import SimpleNamespace

import yaml
from telethon.tl.types import MessageEntityUrl

from bridge.config import config as config_module
from bridge.utils import extract_urls, transform_urls

from tests.fixtures import TEST_CONFIG_DATA, write_config


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


def test_process_message_text_summarizes_last_messages(tmp_path, monkeypatch):
    """Summary of last messages is appended when OpenAI is enabled."""
    cfg = copy.deepcopy(TEST_CONFIG_DATA)
    cfg["openai"]["enabled"] = True
    cfg["openai"]["api_key"] = "key"
    cfg["openai"]["organization"] = "org"
    cfg_file = tmp_path / "config.yml"
    with cfg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg, handle)
    monkeypatch.setattr(config_module, "_file_path", str(cfg_file))
    config_module._instances.clear()
    core = importlib.reload(importlib.import_module("bridge.core"))

    async def fake_sentiment(_self, _text):
        return "sentiment"

    async def fake_summary(_self, _messages):
        return "summary"

    monkeypatch.setattr(core.OpenAIHandler, "analyze_message_sentiment", fake_sentiment)
    monkeypatch.setattr(core.OpenAIHandler, "summarize_messages", fake_summary)

    last_messages = deque(["m"] * 10, maxlen=10)
    message = SimpleNamespace(message="hello", entities=None)
    result = asyncio.run(
        core.Bridge.process_message_text(
            message,
            strip_off_links=False,
            mention_everyone=False,
            mention_roles=[],
            openai_enabled=True,
            last_messages=last_messages,
        )
    )

    assert "Summary of last 10 messages" in result
