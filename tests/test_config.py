"""Tests for configuration loading."""

# pylint: disable=import-error

from bridge.config.config import Config

from tests.fixtures import write_config


def test_config_loads(tmp_path):
    """Config can be loaded from a YAML file."""
    cfg_path = write_config(tmp_path)
    cfg = Config.load_instance(cfg_path)

    assert cfg.application.name == "bridge"
    assert cfg.telegram_forwarders[0].tg_channel_id == 1
