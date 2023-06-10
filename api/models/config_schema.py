"""config schema validation model."""
from typing import List, Optional

from pydantic import BaseModel  # pylint: disable=import-error


class ForwarderConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Forwarder model."""
    forwarder_name: str
    tg_channel_id: int
    discord_channel_id: int
    strip_off_links: bool = False
    mention_everyone: bool = False
    forward_everything: bool = True
    forward_hashtags: Optional[List[dict]] = None
    excluded_hashtags: Optional[List[dict]] = None
    mention_override: Optional[List[dict]] = None


class OpenAIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """OpenAI config."""
    enabled: bool = False
    api_key: str
    organization: str
    sentiment_analysis_prompt: List[str]


class DiscordConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Discord config."""
    bot_token: str
    built_in_roles: List[str]
    max_latency: float = 0.5


class TelegramConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Telegram config."""
    phone: str
    password: str
    api_id: int
    api_hash: str
    log_unhandled_conversations: bool = False


class LoggerConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Logger config."""
    level: str = 'INFO'
    file_max_bytes: int = 10485760
    file_backup_count: int = 5
    format: str = "%(asctime)s %(levelprefix)s %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    console: bool = True


class ApplicationConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Application config."""
    name: str = "hyp3rbridg3"
    version: str
    description: str = "A bridge to forward messages from those pesky Telegram channels."
    debug: bool = False
    healthcheck_interval: int = 60
    recoverer_delay: float = 60.0


class APIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """API config."""
    enabled: bool = True
    cors_origins: List[str] = ["*"]
    telegram_login_enabled: bool = True
    telegram_auth_file: str = "telegram_auth.json"
    telegram_auth_request_expiration: int = 300


class ConfigSummary(BaseModel):  # pylint: disable=too-few-public-methods
    """Config summary."""
    application: ApplicationConfig
    api: APIConfig

class ConfigYAMLSchema(BaseModel):  # pylint: disable=too-few-public-methods
    """Config YAML schema."""
    application: ApplicationConfig
    logger: LoggerConfig
    api: APIConfig
    telegram: TelegramConfig
    discord: DiscordConfig
    openai: OpenAIConfig
    telegram_forwarders: List[ForwarderConfig]

class ConfigSchema(BaseModel):  # pylint: disable=too-few-public-methods
    """Config model."""
    config: ConfigYAMLSchema
