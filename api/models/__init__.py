"""the bridge config schema."""

try:
    from .auth_schema import TelegramAuthSchema
    from .config_schema import (APIConfig, ApplicationConfig, ConfigSchema,
                                ConfigSummary, DiscordConfig, LoggerConfig,
                                OpenAIConfig, TelegramConfig)
    from .health_schema import HealthSchema
except ImportError as ex:
    raise ex
