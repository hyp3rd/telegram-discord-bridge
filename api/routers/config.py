"""Config router for the API"""

import os
from datetime import datetime

import magic
import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError  # pylint: disable=import-error

from api.models import (APIConfig, ApplicationConfig, BaseResponse,
                        ConfigSchema, ConfigYAMLSchema, DiscordConfig,
                        ForwarderConfig, LoggerConfig, OpenAIConfig,
                        TelegramConfig)
from bridge.config import Config
from bridge.enums import RequestTypeEnum
from bridge.logger import Logger
from forwarder import determine_process_state

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

        self.router.put("/", response_model=BaseResponse)(self.upload_config)

        self.router.post("/", response_model=BaseResponse)(self.post_config)


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

        return ConfigSchema(
            config=ConfigYAMLSchema(
                application=application_config,
                logger=logger_config,
                api=api_config,
                telegram=telegram_config,
                discord=discord_config,
                openai=openai_config,
                telegram_forwarders=telegram_forwarders,
            )
        )


    async def upload_config(self, file: UploadFile = File(...)) -> BaseResponse: # pylint: disable=too-many-locals
        """Upload a new config file."""

        process_state, pid = determine_process_state()

        response = BaseResponse(
            resource="config",
            config_version=self.config.app.version,
            request_type=RequestTypeEnum.UPLOAD_CONFIG,
            bridge_status=process_state,
            bridge_pid=pid,
        )

        content = await file.read()

        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(content)

        response.operation_status["mime_type"] = mime_type
        response.operation_status["file_name"] = file.filename if file.filename else "unknown"

        if not file.filename:
            raise HTTPException(
                status_code=400, detail="Invalid file name.")

        if file.filename.startswith(".") or not file.filename.endswith(".yaml") and not file.filename.endswith(".yml"):
            raise HTTPException(
                status_code=400, detail="Invalid file name.")

        if file.size is None or file.size > 1024 * 1024 * 1:
            raise HTTPException(
                status_code=400, detail="Invalid file size. Only file size less than 1MB is accepted.")


        logger.debug("Uploaded file type: %s", mime_type)
        if mime_type != 'text/plain':
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only YAML file is accepted.")

        try:
            new_config_file_content = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=400, detail='Invalid YAML structure in the config file.') from exc

        try:
            _ = ConfigYAMLSchema(**new_config_file_content)
        except ValidationError as exc:
            for error in exc.errors():
                logger.error(error)
            raise HTTPException(
                status_code=400, detail=f'Invalid configuration: {exc.errors}') from exc

        # validate here
        valid, errors = self.config.validate_config(new_config_file_content)
        if not valid:
            raise HTTPException(
                status_code=400, detail=f'{errors}')

        new_config_file_name = f'config-{new_config_file_content["application"]["version"]}.yml'

        response.operation_status["new_config_file_name"] = new_config_file_name

        if os.path.exists(new_config_file_name):
            backup_filename = f"{new_config_file_name}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename(new_config_file_name, backup_filename)
            response.operation_status["config_backup_filename"] = backup_filename

        with open(new_config_file_name, "w", encoding="utf-8") as new_config_file:
            yaml.dump(new_config_file_content, new_config_file)

        response.success = True

        return response
    
    async def post_config(self, config: ConfigSchema) -> BaseResponse:
        """Post a new config file."""

        process_state, pid = determine_process_state()

        response = BaseResponse(
            resource="config",
            config_version=self.config.app.version,
            request_type=RequestTypeEnum.POST_CONFIG,
            bridge_status=process_state,
            bridge_pid=pid,
        )

        valid, errors = self.config.validate_config(config.config.dict())
        if not valid:
            raise HTTPException(
                status_code=400, detail=f'{errors}')
        
        config_file_name = f'config-{config.config.application.version}.yml'

        response.operation_status["new_config_file_name"] = config_file_name

        # validate the config with pydantic
        try:
            _ = ConfigYAMLSchema(**config.config.dict())
        except ValidationError as exc:
            for error in exc.errors():
                logger.error(error)
            raise HTTPException(
                status_code=400, detail=f'Invalid configuration: {exc.errors}') from exc

        if os.path.exists(config_file_name):
            backup_filename = f"{config_file_name}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename(config_file_name, backup_filename)
            response.operation_status["config_backup_filename"] = backup_filename

        with open(config_file_name, "w", encoding="utf-8") as new_config_file:
            yaml.dump(config.config.dict(), new_config_file,
                       allow_unicode=False, encoding="utf-8", 
                       explicit_start=True, sort_keys=False, indent=2, default_flow_style=False)

        response.success = True

        return response


router = ConfigRouter().router
