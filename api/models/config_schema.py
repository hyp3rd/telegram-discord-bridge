"""config schema validation model."""
from typing import List, Optional

from pydantic import BaseModel  # pylint: disable=import-error


class Forwarder(BaseModel):  # pylint: disable=too-few-public-methods
    """Forwarder model."""
    forwarder_name: str
    tg_channel_id: int
    discord_channel_id: int
    strip_off_links: bool
    mention_everyone: bool
    forward_everything: bool
    forward_hashtags: Optional[List[dict]] = None
    excluded_hashtags: Optional[List[dict]] = None
    mention_override: Optional[List[dict]] = None


class OpenAIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """OpenAI config."""
    enabled: bool
    api_key: str
    organization: str
    sentiment_analysis_prompt: List[str]


class DiscordConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Discord config."""
    bot_token: str
    built_in_roles: List[str]
    max_latency: float


class TelegramConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Telegram config."""
    phone: str
    password: str
    api_id: int
    api_hash: str


class LoggerConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Logger config."""
    level: str
    file_max_bytes: int
    file_backup_count: int
    format: str
    date_format: str
    console: bool


class ApplicationConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Application config."""
    name: str
    version: str
    description: str
    debug: bool
    healthcheck_interval: int
    recoverer_delay: float


class APIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """API config."""
    cors_origins: List[str]
    telegram_login_enabled: bool
    telegram_auth_file: str
    telegram_auth_request_expiration: int


class ConfigSummary(BaseModel):  # pylint: disable=too-few-public-methods
    """Config summary."""
    application: ApplicationConfig
    api: APIConfig


class ConfigSchema(BaseModel):  # pylint: disable=too-few-public-methods
    """Config model."""
    application: ApplicationConfig
    logger: LoggerConfig
    telegram: TelegramConfig
    discord: DiscordConfig
    openai: OpenAIConfig
    telegram_forwarders: List[Forwarder]
