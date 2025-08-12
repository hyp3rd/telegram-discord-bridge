"""Tests for pluggable history storage backends."""

# pylint: disable=import-error,protected-access

import importlib
from pathlib import Path

import asyncio
import json
import yaml

from bridge.config import config as config_module

from tests.fixtures import TEST_CONFIG_DATA


def _write_config(tmp_path: Path, history_section: dict) -> str:
    data = TEST_CONFIG_DATA.copy()
    data["history"] = history_section
    cfg_file = tmp_path / "config.yml"
    with cfg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle)
    return str(cfg_file)


def test_json_backend_rotation(tmp_path, monkeypatch):
    """JSON backend persists mappings and supports rotation."""
    cfg_path = _write_config(
        tmp_path,
        {
            "backend": "json",
            "db_url": None,
            "file_max_bytes": 50,
            "file_backup_count": 1,
        },
    )
    monkeypatch.setattr(config_module, "_file_path", cfg_path)
    config_module._instances.clear()
    monkeypatch.chdir(tmp_path)
    history_module = importlib.reload(importlib.import_module("bridge.history.history"))
    handler = history_module.MessageHistoryHandler()
    for i in range(5):
        asyncio.run(handler.save_mapping_data("fwd", i, i))
    path = tmp_path / "messages_history.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["fwd"]["4"] == 4


def test_sqlite_backend_roundtrip(tmp_path, monkeypatch):
    """SQLite backend can store and retrieve mappings."""
    db_path = tmp_path / "history.db"
    cfg_path = _write_config(
        tmp_path,
        {
            "backend": "sqlite",
            "db_url": str(db_path),
            "file_max_bytes": 1000,
            "file_backup_count": 1,
        },
    )
    monkeypatch.setattr(config_module, "_file_path", cfg_path)
    config_module._instances.clear()
    history_module = importlib.reload(importlib.import_module("bridge.history.history"))
    handler = history_module.MessageHistoryHandler()
    asyncio.run(handler.save_mapping_data("fwd", 1, 99))
    discord_id = asyncio.run(handler.get_discord_message_id("fwd", 1))
    assert discord_id == 99
