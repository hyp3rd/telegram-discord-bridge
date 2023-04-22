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
        "discord_bot_token",
        "discord_built_in_roles",
        "telegram_forwarders",
    ]

    for key in required_keys:
        if key not in config_data:
            logger.error(
                "Error: Key '%s' not found in the configuration file.", key)
            sys.exit(1)

    # warning: logging the `config_data` will print sensitive data in the console
    logger.debug(config_data)

    validate_config(config_data)

    return config_data


def validate_config(config):
    """Validate the configuration."""
    forwarders = config["telegram_forwarders"]
    forwarder_combinations = set()

    for forwarder in forwarders:
        tg_channel_id = forwarder["tg_channel_id"]
        discord_channel_id = forwarder["discord_channel_id"]
        mention_everyone = forwarder["mention_everyone"]
        forward_hashtags = forwarder["forward_hashtags"]

        # Check for valid types
        if not isinstance(tg_channel_id, int):
            logger.error(
                "Invalid configuration: `tg_channel_id` must be an integer: forwarder with `tg_channel_id` %s",  # pylint: disable=line-too-long
                tg_channel_id)
            sys.exit(1)

        if not isinstance(discord_channel_id, int):
            logger.error(
                "Invalid configuration: `discord_channel_id` must be an integer: forwarder with `tg_channel_id` %s",  # pylint: disable=line-too-long
                tg_channel_id)
            sys.exit(1)

        # Check for unique combination of tg_channel_id and discord_channel_id
        combination = (tg_channel_id, discord_channel_id)
        if combination in forwarder_combinations:
            logger.error(
                "Invalid configuration: duplicate forwarder with combination %s", combination)
            sys.exit(1)
        forwarder_combinations.add(combination)

        # Check for mention_everyone and override_mention_everyone conflict
        if mention_everyone and any(tag.get("override_mention_everyone", False) for tag in forward_hashtags):
            logger.error(
                "Invalid configuration: `override_mention_everyone` has no effect when `mention_everyone` set to True: forwarder with `tg_channel_id` %s",  # pylint: disable=line-too-long
                tg_channel_id)
            sys.exit(1)

    # Check for shared hashtags in forwarders with the same tg_channel_id
    tg_channel_hashtags = {}
    for forwarder in forwarders:
        tg_channel_id = forwarder["tg_channel_id"]
        forward_hashtags = [tag["name"].lower()
                            for tag in forwarder["forward_hashtags"]]

        if tg_channel_id not in tg_channel_hashtags:
            tg_channel_hashtags[tg_channel_id] = set(forward_hashtags)
        else:
            shared_hashtags = tg_channel_hashtags[tg_channel_id].intersection(
                forward_hashtags)
            if shared_hashtags:
                logger.warning(
                    "Shared hashtags %s found for forwarders with tg_channel_id %s. The same message will be forwarded multiple times.",
                    shared_hashtags, tg_channel_id)
