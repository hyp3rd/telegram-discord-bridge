"""the bridge config schema."""

try:
    from .auth_schema import TelegramAuthResponseSchema, TelegramAuthResponse, TelegramAuthSchema
    from .bridge_schema import BridgeResponse, BridgeResponseSchema
    from .config_schema import (APIConfig, ApplicationConfig, ConfigSchema,
                                ConfigSummary, DiscordConfig, LoggerConfig,
                                OpenAIConfig, TelegramConfig)
    from .health_schema import Health, HealthSchema
except ImportError as ex:
    raise ex
