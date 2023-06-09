"""the bridge config schema."""

try:
    from .auth_schema import (TelegramAuthResponse, TelegramAuthResponseSchema,
                              TelegramAuthSchema)
    from .base_response_schema import BaseResponse
    from .bridge_schema import BridgeResponse, BridgeResponseSchema
    from .config_schema import (APIConfig, ApplicationConfig, ConfigSchema,
                                ConfigSummary, ConfigYAMLSchema, DiscordConfig,
                                ForwarderConfig, LoggerConfig, OpenAIConfig,
                                TelegramConfig)
    from .health_schema import (Health, HealthHistory, HealtHistoryManager,
                                HealthSchema)
except ImportError as ex:
    raise ex
