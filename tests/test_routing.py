"""Tests for routing utilities."""

# pylint: disable=protected-access,import-error

import importlib
from unittest.mock import MagicMock

from bridge.config import config as config_module
from tests.fixtures import write_config


def test_get_matching_forwarders(tmp_path, monkeypatch):
    """Bridge returns forwarder matching the channel id."""
    cfg_file = write_config(tmp_path)
    monkeypatch.setattr(config_module, "_file_path", cfg_file)
    config_module._instances.clear()

    core = importlib.reload(importlib.import_module("bridge.core"))
    bridge = core.Bridge(MagicMock(), MagicMock())

    result = bridge.get_matching_forwarders(1)
    assert len(result) == 1
