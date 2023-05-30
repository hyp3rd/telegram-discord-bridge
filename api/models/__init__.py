"""the bridge config schema."""

try:
    from .auth_schema import (TelegramAuthResponse, TelegramAuthResponseSchema,
                              TelegramAuthSchema)
    from .bridge_schema import BridgeResponse, BridgeResponseSchema
    from .config_schema import (APIConfig, ApplicationConfig, ConfigSchema,
                                ConfigSummary, DiscordConfig, LoggerConfig,
                                OpenAIConfig, TelegramConfig)
    from .health_schema import (Health, HealthHistory, HealtHistoryManager,
                                HealthSchema)
except ImportError as ex:
    raise ex
