"""config schema validation model."""
from typing import List, Optional

from pydantic import BaseModel  # pylint: disable=import-error
from pydantic import StrictInt, root_validator, validator


class ForwarderConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Forwarder model."""
    forwarder_name: str
    tg_channel_id: StrictInt
    discord_channel_id: StrictInt
    strip_off_links: bool = False
    mention_everyone: bool = False
    forward_everything: bool = True
    forward_hashtags: Optional[List[dict]] = None
    excluded_hashtags: Optional[List[dict]] = None
    mention_override: Optional[List[dict]] = None

    @root_validator
    def forward_everything_validator(cls, values):
        forward_everything, forward_hashtags = values.get('forward_everything'), values.get('forward_hashtags')
        if forward_everything is False and not forward_hashtags:
            raise ValueError('forward_everything must be True if forward_hashtags are not set')
        return values

    @validator('forwarder_name')
    def forwarder_name_validator(cls, v):
        if not v:
            assert v, 'forwarder_name must not be empty'
        return v

    @validator('tg_channel_id')
    def tg_channel_id_validator(cls, v):
        if v < 0:
            assert v < 0, 'tg_channel_id must be > 0'
        return v

    @validator('discord_channel_id')
    def discord_channel_id_validator(cls, v):
        if v < 0:
            assert v < 0, 'discord_channel_id must be > 0'
        return v

    @validator('forward_hashtags')
    def forward_hashtags_validator(cls, v):
        if v:
            for forward_hashtags in v:
                if not forward_hashtags['name'].startswith('#'):
                    assert forward_hashtags['name'].startswith('#'), 'forward_hashtags name must start with #'
        return v

    @validator('excluded_hashtags')
    def excluded_hashtags_validator(cls, v):
        if v:
            for excluded_hashtags in v:
                if not excluded_hashtags['name'].startswith('#'):
                    assert excluded_hashtags['name'].startswith('#'), 'excluded_hashtags name must start with #'
        return v

    @validator('mention_override')
    def mention_override_validator(cls, v):
        if v:
            for mention_override in v:
                if not mention_override['tag'].startswith('#'):
                    assert mention_override['tag'].startswith('#'), 'mention_override tag must start with @'
                if not mention_override['roles']:
                    assert mention_override['roles'], 'mention_override roles must not be empty'
        return v


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

    @validator('built_in_roles')
    def built_in_roles_validator(cls, v):
        if not v:
            assert v, 'built_in_roles must not be empty'
        return v
    
    @validator('max_latency')
    def max_latency_validator(cls, v):
        if v < 0:
            assert v < 0, 'max_latency must be > 0'
        if v > 2:
            assert v > 2, 'max_latency must be < 2'
        return v


class TelegramConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Telegram config."""
    phone: str
    password: str
    api_id: StrictInt
    api_hash: str
    log_unhandled_conversations: bool = False

    @validator('api_hash')
    def api_hash_alphanumeric(cls, v):
        if not v.isalnum():
            assert v.isalnum(), 'the API hash must be alphanumeric'
        return v
    
    @validator('api_hash')
    def api_hash_length(cls, v):
        if len(v) != 32:
            assert len(v) == 32, 'the API hash must be 32 characters long'
        return v


class LoggerConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Logger config."""
    level: str = 'INFO'
    file_max_bytes: StrictInt = 10485760
    file_backup_count: StrictInt = 5
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

    @validator('version')
    def version_validator(cls, v):
        if not v:
            assert v, 'version must not be empty'
        return v
    
    @validator('name')
    def name_validator(cls, v):
        if not v:
            assert v, 'name must not be empty'
        # name must be alphanumeric
        if not v.isalnum():
            assert v.isalnum(), 'name must be alphanumeric'
        return v

    @validator('healthcheck_interval')
    def healthcheck_interval_validator(cls, v):
        if v < 30:
            assert v < 30, 'healthcheck_interval must be > 30'
        if v > 1200:
            assert v > 1200, 'healthcheck_interval must be < 1200'
        return v
    
    @validator('recoverer_delay')
    def recoverer_delay_validator(cls, v):
        if v < 10:
            assert v < 10, 'recoverer_delay must be > 10'
        if v > 3600:
            assert v > 3600, 'recoverer_delay must be < 3600'
        return v

class APIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """API config."""
    enabled: bool = True
    cors_origins: List[str] = ["*"]
    telegram_login_enabled: bool = True
    telegram_auth_file: str = "telegram_auth.json"
    telegram_auth_request_expiration: int = 300

    @root_validator
    def telegram_login_validator(cls, values):
        api_enabled, telegram_login_enabled = values.get('enabled'), values.get('telegram_login_enabled')
        if api_enabled and telegram_login_enabled is False:
            raise ValueError('telegram_login_enabled must be True if the API is enabled')
        return values

    @validator('telegram_auth_request_expiration')
    def telegram_auth_request_expiration_validator(cls, v):
        if v < 0:
            assert v < 0, 'telegram_auth_request_expiration must be > 0'
        if v > 3600:
            assert v > 3600, 'telegram_auth_request_expiration must be < 3600'
        return v


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
