"""Configuration handler."""
import sys
from typing import Any

import yaml

from logger import app_logger

logger = app_logger()


class TelegramConfig:  # pylint: disable=too-few-public-methods
    """Telegram configuration handler."""

    def __init__(self, config_data):
        self.phone = config_data["telegram_phone"]
        self.password = config_data["telegram_password"]
        self.api_id = config_data["telegram_api_id"]
        self.api_hash = config_data["telegram_api_hash"]


class DiscordConfig:  # pylint: disable=too-few-public-methods
    """Discord configuration handler."""

    def __init__(self, config_data):
        self.bot_token = config_data["discord_bot_token"]
        self.built_in_roles = config_data["discord_built_in_roles"]


class OpenAIConfig:  # pylint: disable=too-few-public-methods
    """OpenAI configuration handler."""

    def __init__(self, config_data):
        self.api_key = config_data["openai_api_key"]
        self.organization = config_data["openai_organization"]
        self.enabled = config_data["openai_enabled"]
        self.sentiment_analysis_prompt = config_data["openai_sentiment_analysis_prompt"]


class Config:
    """Configuration handler."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.app_name = None
            self.telegram = None
            self.discord = None
            self.openai = None
            self.telegram_forwarders = None
            self.load_config()

    def load_config(self) -> Any:
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

        Config.validate_config(config_data)

        self.app_name = config_data["app_name"]
        self.telegram = TelegramConfig(config_data)
        self.discord = DiscordConfig(config_data)
        self.openai = OpenAIConfig(config_data)
        self.telegram_forwarders = config_data["telegram_forwarders"]

        return config_data

    @ staticmethod
    def validate_openai_enabled(config):
        """Check for valid types"""
        if config["openai_enabled"]:
            if config["openai_api_key"] == "" or config["openai_organization"] == "" or config["openai_sentiment_analysis_prompt"] is None:
                logger.error(
                    "Invalid configuration: `openai_api_key`, `openai_organization`, and `openai_sentiment_analysis_prompt` must be set when `openai_enabled` is True.")  # pylint: disable=line-too-long
                sys.exit(1)

    @ staticmethod
    def validate_forwarder_types(forwarder):
        """Check for valid types"""
        tg_channel_id = forwarder["tg_channel_id"]
        discord_channel_id = forwarder["discord_channel_id"]

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

    @ staticmethod
    def validate_forwarder_combinations(forwarder, forwarder_combinations):
        """Check for unique combination of tg_channel_id and discord_channel_id"""
        tg_channel_id = forwarder["tg_channel_id"]
        discord_channel_id = forwarder["discord_channel_id"]

        combination = (tg_channel_id, discord_channel_id)
        if combination in forwarder_combinations:
            logger.error(
                "Invalid configuration: duplicate forwarder with combination %s", combination)
            sys.exit(1)
        forwarder_combinations.add(combination)

    @ staticmethod
    def validate_mention_everyone_and_override(forwarder, forward_hashtags):
        """Check for mention_everyone and override_mention_everyone conflict"""
        tg_channel_id = forwarder["tg_channel_id"]
        mention_everyone = forwarder["mention_everyone"]

        if mention_everyone and any(tag.get("override_mention_everyone", False) for tag in forward_hashtags):
            logger.error(
                "Invalid configuration: `override_mention_everyone` has no effect when `mention_everyone` set to True: forwarder with `tg_channel_id` %s",  # pylint: disable=line-too-long
                tg_channel_id)
            sys.exit(1)

    @ staticmethod
    def validate_shared_hashtags(forwarders):
        """Check for shared hashtags in forwarders with the same tg_channel_id"""
        tg_channel_hashtags = {}
        for forwarder in forwarders:
            tg_channel_id = forwarder["tg_channel_id"]
            forward_hashtags = {tag["name"].lower() for tag in forwarder.get(
                "forward_hashtags", [])} if forwarder.get("forward_hashtags") else set()

            if forward_hashtags:  # Only process non-empty forward_hashtags
                if tg_channel_id not in tg_channel_hashtags:
                    tg_channel_hashtags[tg_channel_id] = [forward_hashtags]
                else:
                    for existing_hashtags in tg_channel_hashtags[tg_channel_id]:
                        shared_hashtags = existing_hashtags.intersection(
                            forward_hashtags)
                        if shared_hashtags:
                            logger.warning(
                                "Shared hashtags %s found for forwarders with tg_channel_id %s. The same message will be forwarded multiple times.",
                                shared_hashtags, tg_channel_id)
                    tg_channel_hashtags[tg_channel_id].append(forward_hashtags)

    @ staticmethod
    def get_forward_hashtags(forwarder):
        """Get forward_hashtags from forwarder or set an empty list."""
        if "forward_hashtags" in forwarder:
            forward_hashtags = forwarder["forward_hashtags"]
        else:
            tg_channel_id = forwarder["tg_channel_id"]
            logger.debug(
                "No hashtags found for forwarder with `tg_channel_id` %s", tg_channel_id)
            if not forwarder["forward_everything"]:
                logger.error(
                    "Invalid configuration: forwarder with `tg_channel_id` %s must either forward everything or forward hashtags",  # pylint: disable=line-too-long
                    tg_channel_id)
                sys.exit(1)

            forward_hashtags = []

        return forward_hashtags

    @ staticmethod
    def validate_config(config):
        """Validate the configuration."""
        forwarders = config["telegram_forwarders"]
        forwarder_combinations = set()

        Config.validate_openai_enabled(config)

        for forwarder in forwarders:
            forward_hashtags = Config.get_forward_hashtags(forwarder)

            Config.validate_forwarder_types(forwarder)
            Config.validate_forwarder_combinations(
                forwarder, forwarder_combinations)
            Config.validate_mention_everyone_and_override(
                forwarder, forward_hashtags)

        Config.validate_shared_hashtags(forwarders)
