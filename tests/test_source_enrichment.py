"""Tests for message source enrichment."""

# pylint: disable=protected-access,import-error

import asyncio
import copy
import importlib
from types import SimpleNamespace

from tests.fixtures import TEST_CONFIG_DATA, patch_config


def test_enrich_and_send_sources(tmp_path, monkeypatch):
    """Source links are sent when enrichment is enabled."""

    cfg = copy.deepcopy(TEST_CONFIG_DATA)
    cfg["openai"]["enabled"] = True
    cfg["openai"]["api_key"] = "key"
    cfg["openai"]["organization"] = "org"
    cfg["openai"]["enrich_with_sources"] = True
    patch_config(cfg, tmp_path, monkeypatch)
    core = importlib.reload(importlib.import_module("bridge.core"))

    async def fake_analyze(_self, _text):
        return [
            {
                "claim": "Python created in 1991",
                "query": "Python programming language 1991",
            }
        ]

    async def fake_lookup(_self, _queries):
        return [("Python created in 1991", "https://example.com/python")]

    captured = {}

    async def fake_forward(_discord_channel, message_text, **_kwargs):
        captured["text"] = message_text
        return []

    monkeypatch.setattr(
        core.OpenAIHandler, "analyze_message_and_generate_suggestions", fake_analyze
    )
    monkeypatch.setattr(core.Bridge, "lookup_sources", fake_lookup)
    monkeypatch.setattr(
        core.DiscordHandler, "forward_message", staticmethod(fake_forward)
    )

    bridge = core.Bridge(SimpleNamespace(), SimpleNamespace())
    channel = SimpleNamespace()
    asyncio.run(bridge.enrich_and_send_sources("Python is great", channel))

    assert "https://example.com/python" in captured["text"]
