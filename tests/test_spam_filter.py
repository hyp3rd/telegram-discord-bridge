"""Tests for the ML-based spam filter."""

from __future__ import annotations

# pylint: disable=protected-access

import asyncio
import importlib
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

import yaml

from bridge.config import config as config_module
from tests.fixtures import TEST_CONFIG_DATA


class DummyClient:  # pylint: disable=too-few-public-methods
    """Telegram client stub returning no messages."""

    async def iter_messages(self, *_args, **_kwargs):
        """Asynchronous generator yielding no messages."""
        for _ in []:
            yield _


def test_spam_filter_ml(tmp_path, monkeypatch):
    """When ML strategy is enabled, spam is flagged via OpenAI."""

    cfg = deepcopy(TEST_CONFIG_DATA)
    cfg["application"]["anti_spam_enabled"] = True
    cfg["application"]["anti_spam_strategy"] = "ml"
    cfg["openai"]["enabled"] = True
    cfg["openai"]["api_key"] = "key"
    cfg["openai"]["organization"] = "org"

    cfg_file = tmp_path / "config.yml"
    with cfg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg, handle)

    monkeypatch.setattr(config_module, "_file_path", str(cfg_file))
    config_module._instances.clear()
    history_module = importlib.reload(importlib.import_module("bridge.history.history"))

    async def fake_is_spam(self, text):  # pylint: disable=unused-argument
        return True

    monkeypatch.setattr(history_module.OpenAIHandler, "__init__", lambda self: None)
    monkeypatch.setattr(history_module.OpenAIHandler, "is_spam", fake_is_spam)

    message = SimpleNamespace(id=1, text="buy now", date=datetime.now())

    handler = history_module.MessageHistoryHandler()
    result = asyncio.run(
        handler.spam_filter(telegram_message=message, channel_id=1, tgc=DummyClient())
    )
    assert result is True
