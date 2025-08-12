"""Tests for mention override triggered by substrings."""

# pylint: disable=protected-access

import importlib
from types import SimpleNamespace

from bridge.config import config as config_module
from tests.fixtures import write_config


def test_mention_override_by_string(tmp_path, monkeypatch):
    """Roles are mentioned when override tag is found in message text."""
    cfg_file = write_config(tmp_path)
    monkeypatch.setattr(config_module, "_file_path", cfg_file)
    config_module._instances.clear()

    discord_module = importlib.import_module("bridge.discord.core")
    handler = discord_module.DiscordHandler.__new__(discord_module.DiscordHandler)
    roles = handler.get_mention_roles(
        message_forward_hashtags=[],
        mention_override_tags=[{"tag": "+++", "roles": ["everyone", "Admin"]}],
        discord_built_in_roles=["everyone", "here"],
        server_roles=[SimpleNamespace(name="Admin", mention="@Admin")],
        message_text="Important news +++",
    )

    assert "@everyone" in roles
    assert "@Admin" in roles
