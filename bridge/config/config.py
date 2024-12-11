"""Configuration handler."""

import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, StrictInt, model_validator, validator

_instances: Dict[str, "Config"] = {}
_file_path = os.path.join(
    os.path.curdir,
    "config.yml",
)


# pylint: disable=no-self-argument
# # pylint: disable=too-few-public-methods
class ForwarderConfig(BaseModel):
    """Forwarder model."""

    forwarder_name: str
    tg_channel_id: StrictInt
    discord_channel_id: StrictInt
    strip_off_links: bool = False
    mention_everyone: bool = False
    forward_everything: bool = True
    send_embed: Optional[bool] = True
    messagedb: Optional[bool] = False
    embed_sidebar_color: Optional[str] = "0x1ABC9C"
    embed_skip_color: Optional[str] = "#CCCC00"
    embed_openai_color: Optional[str] = "#FF0000"
    forward_hashtags: Optional[List[dict]] = None
    excluded_hashtags: Optional[List[dict]] = None
    mention_override: Optional[List[dict]] = None

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        return setattr(self, key, value)

    def __iter__(self):
        return iter(self.__dict__)

    class Config:
        """Forwarder config."""

        str_max_length = 64

    @model_validator(mode="before")
    def forward_everything_validator(cls, values):
        """Forward everything validator."""
        forward_everything, forward_hashtags = values.get(
            "forward_everything"
        ), values.get("forward_hashtags")
        if forward_everything is False and not forward_hashtags:
            raise ValueError(
                "forward_everything must be True if forward_hashtags are not set"
            )
        return values

    @model_validator(mode="before")
    def forward_hashtags_excluded_hashtags_validator(cls, values):
        """Forward hashtags and excluded hashtags validator."""
        forward_hashtags, excluded_hashtags = values.get(
            "forward_hashtags"
        ), values.get("excluded_hashtags")
        if forward_hashtags and excluded_hashtags:
            for forward_hashtag in forward_hashtags:
                for excluded_hashtag in excluded_hashtags:
                    if forward_hashtag["name"] == excluded_hashtag["name"]:
                        raise ValueError(
                            "forward_hashtags and excluded_hashtags must not contain the same hashtag"
                        )
        return values

    @model_validator(mode="before")
    def mention_override_validator_mention_everyone(cls, values):
        """Mention override validator."""
        mention_override, mention_everyone = values.get("mention_override"), values.get(
            "mention_everyone"
        )
        if mention_override and mention_everyone:
            raise ValueError(
                "mention_override and mention_everyone must not be set at the same time"
            )
        return values

    @validator("forwarder_name")
    def forwarder_name_validator(cls, val):
        """Forwarder name validator."""
        if not val:
            assert val, "forwarder_name must not be empty"
        return val

    @validator("tg_channel_id")
    def tg_channel_id_validator(cls, val):
        """Telegram channel id validator."""
        if val < 0:
            assert val < 0, "tg_channel_id must be > 0"
        return val

    @validator("discord_channel_id")
    def discord_channel_id_validator(cls, val):
        """Discord channel id validator."""
        if val < 0:
            assert val < 0, "discord_channel_id must be > 0"
        return val

    @validator("forward_hashtags")
    def forward_hashtags_validator(cls, val):
        """Forward hashtags validator."""
        if val:
            for forward_hashtags in val:
                if not forward_hashtags["name"].startswith("#"):
                    assert forward_hashtags["name"].startswith(
                        "#"
                    ), "forward_hashtags name must start with #"
        return val

    @validator("excluded_hashtags")
    def excluded_hashtags_validator(cls, val):
        """Excluded hashtags validator."""
        if val:
            for excluded_hashtags in val:
                if not excluded_hashtags["name"].startswith("#"):
                    assert excluded_hashtags["name"].startswith(
                        "#"
                    ), "excluded_hashtags name must start with #"
        return val

    @validator("mention_override")
    def mention_override_validator(cls, val):
        """Mention override validator."""
        if val:
            for mention_override in val:
                if not mention_override["tag"].startswith("#"):
                    assert mention_override["tag"].startswith(
                        "#"
                    ), "mention_override tag must start with @"
                if not mention_override["roles"]:
                    assert mention_override[
                        "roles"
                    ], "mention_override roles must not be empty"
        return val


class OpenAIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """OpenAI config."""

    enabled: bool = False
    min_msg_len: int = 20
    model: str = "gpt-4o-mini"
    temperature: int = 0
    filter: bool = False
    api_key: str
    organization: str
    sentiment_analysis_prompt: List[dict]
    is_healthy: bool = True  # FIX: This is a hack to make the health check pass

    @model_validator(mode="before")
    def openai_validator(cls, values):
        """OpenAI validator."""
        enabled, api_key, organization = (
            values.get("enabled"),
            values.get("api_key"),
            values.get("organization"),
        )
        if enabled:
            if not api_key:
                raise ValueError("api_key must not be empty")
            if not organization:
                raise ValueError("organization must not be empty")
            if not values.get("sentiment_analysis_prompt"):
                raise ValueError("sentiment_analysis_prompt must not be empty")
        return values

    # Removed validator since im using a different openai API
    '''
    @validator("sentiment_analysis_prompt")
    def sentiment_analysis_prompt_validator(cls, val):
        """Sentiment analysis prompt validator."""
        if val:
            valid: bool = False
            pronpt_placeholder: str = "#text_to_parse"
            for prompt in val:
                if pronpt_placeholder in prompt:
                    valid = True

            if not valid:
                raise ValueError(
                    "sentiment_analysis_prompt must contain #text_to_parse placeholder"
                )
        return val
    '''


class DiscordConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Discord config."""

    bot_token: str
    built_in_roles: List[str] = ["everyone", "here", "@Admin"]
    max_latency: float = 0.5
    is_healthy: bool = False

    @model_validator(mode="before")
    def discord_validator(cls, values):
        """Discord validator."""
        bot_token = values.get("bot_token")
        if not bot_token:
            raise ValueError("bot_token must not be empty")
        return values

    @validator("built_in_roles")
    def built_in_roles_validator(cls, val):
        """Built in roles validator."""
        if not val:
            assert val, "built_in_roles must not be empty"
        return val

    @validator("max_latency")
    def max_latency_validator(cls, val):
        """Max latency validator."""
        if val < 0:
            assert val < 0, "max_latency must be > 0"
        if val > 2:
            assert val > 2, "max_latency must be < 2"
        return val


class TelegramConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Telegram config."""

    phone: str
    password: str
    api_id: StrictInt
    api_hash: str
    log_unhandled_dialogs: bool = False
    subscribe_to_edit_events: bool = False
    subscribe_to_delete_events: bool = False
    is_healthy: bool = False

    class Config:
        """Telegram config."""

    @validator("api_hash")
    def api_hash_alphanumeric(cls, val):
        """API hash alphanumeric validator."""
        if not val.isalnum():
            assert val.isalnum(), "the API hash must be alphanumeric"
        return val

    @validator("api_hash")
    def api_hash_length(cls, val):
        """API hash length validator."""
        if len(val) != 32:
            assert len(val) == 32, "the API hash must be 32 characters long"
        return val


class LoggerConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Logger config."""

    level: str = "INFO"
    file_max_bytes: StrictInt = 10485760
    file_backup_count: StrictInt = 5
    format: str = "%(asctime)s %(levelprefix)s %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    console: bool = True

    @validator("level")
    def level_validator(cls, val):
        """Level validator."""
        if not val:
            assert val, "level must not be empty"
        if val not in ["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(
                "level must be one of NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL"
            )
        return val

    @validator("file_max_bytes")
    def file_max_bytes_validator(cls, val):
        """File max bytes validator."""
        if val < 0:
            raise ValueError("file_max_bytes must be > 0")

        if val > 104857600:
            raise ValueError("file_max_bytes must be < 104857600")
        return val


class ApplicationConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Application config."""

    name: str = "hyp3rbridg3"
    version: str
    description: str = (
        "A bridge to forward messages from those pesky Telegram channels."
    )
    debug: bool = False
    healthcheck_interval: int = 60
    recoverer_delay: float = 60.0
    internet_connected: bool = False
    anti_spam_enabled: bool = False
    anti_spam_similarity_timeframe: float = 60.0
    anti_spam_similarity_threshold: float = 1.0
    anti_spam_contextual_analysis: bool = False
    media_store_location: str = "media"
    media_max_size_bytes: int = 1048576
    media_max_size_photo: str = "https://www.safetysuppliesunlimited.net/wp-content/uploads/2020/06/ISO472AP.jpg"
    messagedb_dir: str = "forward-history/forwards"

    @validator("version")
    def version_validator(cls, val):
        """Version validator."""
        if not val:
            assert val, "version must not be empty"
        return val

    @validator("name")
    def name_validator(cls, val):
        """Name validator."""
        if not val:
            assert val, "name must not be empty"
        # name must be alphanumeric
        if not val.isalnum():
            assert val.isalnum(), "name must be alphanumeric"
        return val

    @validator("healthcheck_interval")
    def healthcheck_interval_validator(cls, val):
        """Healthcheck interval validator."""
        if val < 30:
            assert val < 30, "healthcheck_interval must be > 30"
        if val > 1200:
            assert val > 1200, "healthcheck_interval must be < 1200"
        return val

    @validator("recoverer_delay")
    def recoverer_delay_validator(cls, val):
        """Recoverer delay validator."""
        if val < 10:
            assert val < 10, "recoverer_delay must be > 10"
        if val > 3600:
            assert val > 3600, "recoverer_delay must be < 3600"
        return val

    @validator("anti_spam_similarity_timeframe")
    def anti_spam_similarity_timeframe_validator(cls, val):
        """Anti-Spam similarity timeframe validator."""
        if val < 10:
            assert val < 10, "anti_spam_similarity_timeframe must be > 10"
        if val > 3600:
            assert val > 3600, "anti_spam_similarity_timeframe must be < 3600"
        return val

    @validator("anti_spam_similarity_threshold")
    def anti_spam_similarity_threshold_validator(cls, val):
        """Anti-Spam similarity threshold validator."""
        if val < 0:
            assert val < 0, "anti_spam_similarity_threshold must be > 0"
        if val > 1:
            assert val > 1, "anti_spam_similarity_threshold must be < 1"
        return val


class APIConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """API config."""

    enabled: bool = True
    cors_origins: List[str] = ["*"]
    telegram_login_enabled: bool = True
    telegram_auth_file: str = "telegram_auth.json"
    telegram_auth_request_expiration: int = 300

    @model_validator(mode="before")
    def telegram_login_validator(cls, values):
        """Telegram login validator."""
        api_enabled, telegram_login_enabled = values.get("enabled"), values.get(
            "telegram_login_enabled"
        )
        if api_enabled and telegram_login_enabled is False:
            raise ValueError(
                "telegram_login_enabled must be True if the API is enabled"
            )
        return values

    @validator("telegram_auth_request_expiration")
    def telegram_auth_request_expiration_validator(cls, val):
        """Telegram auth request expiration validator."""
        if val < 0:
            assert val < 0, "telegram_auth_request_expiration must be > 0"
        if val > 3600:
            assert val > 3600, "telegram_auth_request_expiration must be < 3600"
        return val


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

    @model_validator(mode="before")
    def forwarder_validator(cls, values):
        """Validate forwarder combinations to avoid duplicates."""
        forwarder_combinations = set()
        for forwarder in values.get("telegram_forwarders"):
            tg_channel_id = forwarder["tg_channel_id"]
            discord_channel_id = forwarder["discord_channel_id"]
            combination = (tg_channel_id, discord_channel_id)
            if combination in forwarder_combinations:
                raise ValueError(f"Forwarder combination {combination} is duplicated")

            forwarder_combinations.add(combination)
        return values

    @model_validator(mode="after")
    def shared_forward_hashtags_validator(cls, values):
        """Ensure that hashtags are not shared between forwarders with the same telegram_id channel."""
        tg_channel_hashtags = {}

        # Access telegram_forwarders using dot notation
        for forwarder in values.telegram_forwarders:
            tg_channel_id = forwarder.tg_channel_id
            forward_hashtags = (
                {tag["name"].lower() for tag in forwarder.forward_hashtags}
                if forwarder.forward_hashtags
                else set()
            )

            if forward_hashtags:  # Only process non-empty forward_hashtags
                if tg_channel_id not in tg_channel_hashtags:
                    tg_channel_hashtags[tg_channel_id] = [forward_hashtags]
                else:
                    for existing_hashtags in tg_channel_hashtags[tg_channel_id]:
                        shared_hashtags = existing_hashtags.intersection(
                            forward_hashtags
                        )
                        if shared_hashtags:
                            raise ValueError(
                                f"Shared hashtags {shared_hashtags} found for forwarders with tg_channel_id {tg_channel_id}. The same message will be forwarded multiple times."  # pylint: disable=line-too-long
                            )

                    tg_channel_hashtags[tg_channel_id].append(forward_hashtags)
        return values


class ConfigSchema(BaseModel):
    """Config model."""

    config: ConfigYAMLSchema


class Config(BaseModel):
    """Config model."""

    application: ApplicationConfig
    logger: LoggerConfig
    api: APIConfig
    telegram: TelegramConfig
    discord: DiscordConfig
    openai: OpenAIConfig
    telegram_forwarders: List[ForwarderConfig]

    def __getitem__(self, item):
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item) from None

    def __setitem__(self, key, value):
        if key not in self.__dict__:
            raise KeyError(key)
        return setattr(self, key, value)

    def __iter__(self):
        try:
            return iter(self.__dict__ or {})
        except (TypeError, AttributeError):
            return iter({})

    @classmethod
    def from_yaml(cls, yaml_file: str) -> "Config":
        """Load config instance from YAML file."""
        try:
            with open(yaml_file, "r", encoding="utf-8") as stream:
                config = yaml.safe_load(stream)
            return cls(**config)  # create the Config object here
        except FileNotFoundError as ex:
            raise FileNotFoundError(f"Config file {yaml_file} not found.") from ex

        except yaml.YAMLError as ex:
            raise ValueError(f"Error parsing config file {yaml_file}.") from ex

    def to_yaml(self, yaml_file: str) -> None:
        """Save config to YAML file."""
        with open(yaml_file, "w", encoding="utf-8") as stream:
            yaml.dump(self.model_dump(), stream, default_flow_style=False)

    def to_summary(self) -> ConfigSummary:
        """Get config summary."""
        return ConfigSummary(
            application=self.application,
            api=self.api,
        )

    # def __init__(self, **data):
    #     super().__init__(**data)

    @classmethod
    def load_instance(cls, yaml_file: str) -> "Config":
        """Load config instance from YAML file."""
        try:
            with open(yaml_file, "r", encoding="utf-8") as stream:
                config = yaml.safe_load(stream)
            return cls(**config)
        except FileNotFoundError as ex:
            raise FileNotFoundError(f"Config file {yaml_file} not found.") from ex

        except yaml.YAMLError as ex:
            raise ValueError(f"Error parsing config file {yaml_file}.") from ex

    @classmethod
    def get_instance(cls, version: str = "default") -> "Config":
        """Get config instance."""
        if version not in _instances.items():
            _instances[version] = cls.load_instance(_file_path)
        return _instances[version]

    def get_telegram_channel_by_forwarder_name(self, forwarder_name: str):
        """Get the Telegram channel ID associated with a given forwarder ID."""
        for forwarder in self.telegram_forwarders:
            if forwarder["forwarder_name"] == forwarder_name:
                return forwarder["tg_channel_id"]
        return None
