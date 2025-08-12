"""Tests for configuration loading."""

# pylint: disable=duplicate-code,import-error

import yaml

from bridge.config.config import Config


def test_config_loads(tmp_path):
    """Config can be loaded from a YAML file."""
def get_config_data():
    return {
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
    }
    cfg_file = tmp_path / "config.yml"
    with cfg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config_data, handle)

    cfg = Config.load_instance(str(cfg_file))

    assert cfg.application.name == "bridge"
    assert cfg.telegram_forwarders[0].tg_channel_id == 1
