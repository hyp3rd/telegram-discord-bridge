"""Common test fixtures and helpers."""

from __future__ import annotations

import yaml

# Central configuration sample reused across tests
TEST_CONFIG_DATA = {
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
        "anti_spam_strategy": "heuristic",
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
        "compress": False,
    },
    "history": {
        "backend": "json",
        "db_url": None,
        "file_max_bytes": 1024,
        "file_backup_count": 1,
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
        "model": "gpt-4o-mini",
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


def write_config(tmp_path) -> str:
    """Write the shared config to ``tmp_path`` and return the path."""
    cfg_file = tmp_path / "config.yml"
    with cfg_file.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(TEST_CONFIG_DATA, handle)
    return str(cfg_file)
