"""Configuration handler."""
import sys
from typing import Any

import yaml

from logger import app_logger

logger = app_logger()


def load_config() -> Any:
    """Load configuration from the 'config.yml' file."""
    try:
        with open('config.yml', 'rb') as config_file:
            config_data = yaml.safe_load(config_file)
    except FileNotFoundError:
        logger.error("Error: Configuration file 'config.yml' not found.")
        sys.exit(1)
    except yaml.YAMLError as ex:
        logger.error("Error parsing configuration file: %s", ex)
        sys.exit(1)

    required_keys = [
        "app_name",
        "telegram_phone",
        "telegram_password",
        "telegram_api_id",
        "telegram_api_hash",
        "telegram_input_channels",
        "discord_bot_token",
    ]

    for key in required_keys:
        if key not in config_data:
            logger.error(
                "Error: Key '%s' not found in the configuration file.", key)
            sys.exit(1)

    logger.info(config_data)

    return config_data
