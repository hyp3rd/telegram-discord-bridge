"""Initialize the config module."""

try:
    from .config import (APIConfig, ApplicationConfig, Config, ConfigSchema,
                         ConfigYAMLSchema, DiscordConfig, ForwarderConfig,
                         LoggerConfig, OpenAIConfig, TelegramConfig)
except ImportError as ex:
    raise ex
