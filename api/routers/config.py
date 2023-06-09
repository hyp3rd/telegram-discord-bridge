"""Config router for the API"""

from fastapi import APIRouter, File, UploadFile

from api.models import (APIConfig, ApplicationConfig, ConfigSchema,
                        DiscordConfig, ForwarderConfig, LoggerConfig,
                        OpenAIConfig, TelegramConfig)
from bridge.config import Config
from bridge.logger import Logger

logger = Logger.get_logger(Config.get_config_instance().app.name)

class ConfigRouter:
    """Config router class."""

    def __init__(self) -> None:
        """Initialize the config router."""
        self.config = Config.get_config_instance()
        self.router = APIRouter(
            prefix="/config",
            tags=["config"],
            responses={404: {"description": "Not found"}},
            )
    
        self.router.get("/", response_model=ConfigSchema)(self.get_config)


    async def get_config(self) -> ConfigSchema:
        """Get the current config."""
        application_config = ApplicationConfig(
            name=self.config.app.name,
            version=self.config.app.version,
            description=self.config.app.description,
            debug=self.config.app.debug,
            healthcheck_interval=self.config.app.healthcheck_interval,
            recoverer_delay=self.config.app.recoverer_delay,
        )

        api_config = APIConfig(
            enabled=self.config.api.enabled,
            cors_origins=self.config.api.cors_origins,
            telegram_login_enabled=self.config.api.telegram_login_enabled,
            telegram_auth_file=self.config.api.telegram_auth_file,
            telegram_auth_request_expiration=self.config.api.telegram_auth_request_expiration,
        )

        logger_config = LoggerConfig(
            level=self.config.logger.level,
            file_max_bytes=self.config.logger.file_max_bytes,
            file_backup_count=self.config.logger.file_backup_count,
            format=self.config.logger.format,
            date_format=self.config.logger.date_format,
            console=self.config.logger.console,
        )

        telegram_config = TelegramConfig(
            phone=self.config.telegram.phone,
            password=self.config.telegram.password,
            api_id=self.config.telegram.api_id,
            api_hash=self.config.telegram.api_hash,
            log_unhandled_conversations=self.config.telegram.log_unhandled_conversations,
        )

        discord_config = DiscordConfig(
            bot_token=self.config.discord.bot_token,
            built_in_roles=self.config.discord.built_in_roles,
            max_latency=self.config.discord.max_latency,
        )

        openai_config = OpenAIConfig(
            api_key=self.config.openai.api_key,
            enabled=self.config.openai.enabled,
            organization=self.config.openai.organization,
            sentiment_analysis_prompt=self.config.openai.sentiment_analysis_prompt,
        )

        telegram_forwarders = []
        for forwarder in self.config.telegram_forwarders:
            telegram_forwarders.append(
                ForwarderConfig(
                    forwarder_name=forwarder["forwarder_name"],
                    tg_channel_id=forwarder["tg_channel_id"],
                    discord_channel_id=forwarder["discord_channel_id"],
                    mention_everyone=forwarder["mention_everyone"],
                    forward_everything=forwarder["forward_everything"],
                    strip_off_links=forwarder["strip_off_links"],
                    forward_hashtags=forwarder["forward_hashtags"] if "forward_hashtags" in forwarder else [],
                    excluded_hashtags=forwarder["excluded_hashtags"] if "excluded_hashtags" in forwarder else [],
                    mention_override=forwarder["mention_override"] if "mention_override" in forwarder else None,
                )
            )

        """Get the config."""
        return ConfigSchema(
            application=application_config,
            logger=logger_config,
            api=api_config,
            telegram=telegram_config,
            discord=discord_config,
            openai=openai_config,
            telegram_forwarders=telegram_forwarders,
        )
    
router = ConfigRouter().router