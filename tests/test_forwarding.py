"""Tests for message forwarding helpers."""

# pylint: disable=protected-access,duplicate-code,import-error

import asyncio
import importlib
from types import SimpleNamespace

import yaml

from bridge.config import config as config_module


def _write_config(tmp_path):
    data = {
        "application": {
            "name": "bridge",
            "version": "0.0",
            "description": "test",
            "debug": True,
            "healthcheck_interval": 60,
            "recoverer_delay": 60,
            "anti_spam_enabled": False,
            "anti_spam_similarity_timeframe": 60,
            "anti_spam_similarity_threshold": 0.8,
        },
        "api": {
            "enabled": False,
            "telegram_login_enabled": False,
            "telegram_auth_file": "auth.json",
            "telegram_auth_request_expiration": 300,
            "cors_origins": [],
        },
        "logger": {
            "level": "INFO",
            "file_max_bytes": 1024,
            "file_backup_count": 1,
            "format": "%(message)s",
            "date_format": "%Y-%m-%d",
            "console": True,
        },
        "telegram": {
            "phone": "+10000000000",
            "password": "pwd",
            "api_id": 1,
            "api_hash": "h" * 32,
            "log_unhandled_conversations": False,
            "subscribe_to_edit_events": True,
            "subscribe_to_delete_events": True,
        },
        "discord": {
            "bot_token": "token",
            "built_in_roles": ["everyone"],
            "max_latency": 1.0,
        },
        "openai": {
            "enabled": False,
            "api_key": "",
            "organization": "",
            "sentiment_analysis_prompt": ["Analyze #text_to_parse"],
        },
        "telegram_forwarders": [
            {
                "forwarder_name": "fwd",
                "tg_channel_id": 1,
                "discord_channel_id": 2,
                "forward_everything": True,
            }
        ],
from tests.fixtures import TEST_CONFIG_DATA

def _write_config(tmp_path):
    data = TEST_CONFIG_DATA
    cfg_file = tmp_path / "config.yml"
    with cfg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle)
    return cfg_file


def test_process_message_text(tmp_path, monkeypatch):
    """Processed text includes mentions and roles."""
    cfg_file = _write_config(tmp_path)
    monkeypatch.setattr(config_module, "_file_path", str(cfg_file))
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
