"""Config router for the API"""

import asyncio
import os
from datetime import datetime

import magic
import yaml
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError  # pylint: disable=import-error # SecretStr

from api.models import BaseResponse
from bridge.config import (
    APIConfig,
    ApplicationConfig,
    Config,
    ConfigSchema,
    ConfigYAMLSchema,
    DiscordConfig,
    ForwarderConfig,
    LoggerConfig,
    OpenAIConfig,
    TelegramConfig,
)
from bridge.enums import RequestTypeEnum
from bridge.logger import Logger
from forwarder import Forwarder

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class ConfigRouter:
    """Config router class."""

    def __init__(self) -> None:
        """Initialize the config router."""
        self.forwarder = Forwarder(event_loop=asyncio.get_running_loop())
        self.router = APIRouter(
            prefix="/config",
            tags=["config"],
            responses={404: {"description": "Not found"}},
        )

        self.router.get(
            "/",
            response_model=ConfigSchema,
            summary="Get the current config",
            description="The endpoint reports the current loaded config in full, including secrets.",
        )(self.get_config)

        self.router.put(
            "/",
            response_model=BaseResponse,
            summary="Upload a new config file",
            description="Upload a config file in YAML format and will be versioned `version` field.",
        )(self.upload_config)

        self.router.post(
            "/",
            response_model=BaseResponse,
            summary="Post a new config",
            description="POST a new config in JSON payload. The file will be versioned `version` field.",
        )(self.post_config)

    async def get_config(self) -> ConfigSchema:
        """Get the current config."""

        application_config = ApplicationConfig(
            name=config.application.name,
            version=config.application.version,
            description=config.application.description,
            debug=config.application.debug,
            healthcheck_interval=config.application.healthcheck_interval,
            recoverer_delay=config.application.recoverer_delay,
        )

        api_config = APIConfig(
            enabled=config.api.enabled,
            cors_origins=config.api.cors_origins,
            telegram_login_enabled=config.api.telegram_login_enabled,
            telegram_auth_file=config.api.telegram_auth_file,
            telegram_auth_request_expiration=config.api.telegram_auth_request_expiration,
        )

        logger_config = LoggerConfig(
            level=config.logger.level,
            file_max_bytes=config.logger.file_max_bytes,
            file_backup_count=config.logger.file_backup_count,
            format=config.logger.format,
            date_format=config.logger.date_format,
            console=config.logger.console,
        )

        telegram_config = TelegramConfig(
            phone=config.telegram.phone,
            password=config.telegram.password,
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash,
            log_unhandled_dialogs=config.telegram.log_unhandled_dialogs,
        )

        discord_config = DiscordConfig(
            bot_token=config.discord.bot_token,
            built_in_roles=config.discord.built_in_roles,
            max_latency=config.discord.max_latency,
        )

        openai_config = OpenAIConfig(
            api_key=config.openai.api_key,
            enabled=config.openai.enabled,
            organization=config.openai.organization,
            sentiment_analysis_prompt=config.openai.sentiment_analysis_prompt,
        )

        telegram_forwarders = []
        for forwarder in config.telegram_forwarders:
            telegram_forwarders.append(
                ForwarderConfig(
                    forwarder_name=forwarder["forwarder_name"],
                    tg_channel_id=forwarder["tg_channel_id"],
                    discord_channel_id=forwarder["discord_channel_id"],
                    mention_everyone=forwarder["mention_everyone"],
                    forward_everything=forwarder["forward_everything"],
                    strip_off_links=forwarder["strip_off_links"],
                    forward_hashtags=forwarder["forward_hashtags"]
                    if forwarder["forward_hashtags"]
                    else [],
                    excluded_hashtags=forwarder["excluded_hashtags"]
                    if forwarder["excluded_hashtags"] in forwarder
                    else [],
                    mention_override=forwarder["mention_override"]
                    if forwarder["mention_override"] in forwarder
                    else None,
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

    async def upload_config(
        self, file: UploadFile = File(...)
    ) -> BaseResponse:  # pylint: disable=too-many-locals
        """Upload a new config file."""

        process_state, pid = self.forwarder.determine_process_state()

        response = BaseResponse(
            resource="config",
            config_version=config.application.version,
            request_type=RequestTypeEnum.UPLOAD_CONFIG,
            bridge_status=process_state,
            bridge_pid=pid,
        )

        content = await file.read()

        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(content)

        response.operation_status["mime_type"] = mime_type
        response.operation_status["file_name"] = (
            file.filename if file.filename else "unknown"
        )

        if not file.filename:
            raise HTTPException(status_code=400, detail="Invalid file name.")

        if (
            file.filename.startswith(".")
            or not file.filename.endswith(".yaml")
            and not file.filename.endswith(".yml")
        ):
            raise HTTPException(status_code=400, detail="Invalid file name.")

        if file.size is None or file.size > 1024 * 1024 * 1:
            raise HTTPException(
                status_code=400,
                detail="Invalid file size. Only file size less than 1MB is accepted.",
            )

        logger.debug("Uploaded file type: %s", mime_type)
        if mime_type != "text/plain":
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only YAML file is accepted."
            )

        try:
            new_config_file_content = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid YAML structure in the config file."
            ) from exc

        try:
            _ = ConfigYAMLSchema(**new_config_file_content)
        except ValidationError as exc:
            for error in exc.errors():
                logger.error(error)
            raise HTTPException(
                status_code=400, detail=f"Invalid configuration: {exc.errors}"
            ) from exc

        new_config_file_name = (
            f'config-{new_config_file_content["application"]["version"]}.yml'
        )

        response.operation_status["new_config_file_name"] = new_config_file_name

        if os.path.exists(new_config_file_name):
            backup_filename = f"{new_config_file_name}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename(new_config_file_name, backup_filename)
            response.operation_status["config_backup_filename"] = backup_filename

        with open(new_config_file_name, "w", encoding="utf-8") as new_config_file:
            yaml.dump(new_config_file_content, new_config_file)

        response.success = True

        return response

    async def post_config(self, config_schema: ConfigSchema) -> BaseResponse:
        """Post a new config file."""

        process_state, pid = self.forwarder.determine_process_state()

        response = BaseResponse(
            resource="config",
            config_version=config_schema.config.application.version,
            request_type=RequestTypeEnum.POST_CONFIG,
            bridge_status=process_state,
            bridge_pid=pid,
        )

        config_file_name = f"config-{config_schema.config.application.version}.yml"

        response.operation_status["new_config_file_name"] = config_file_name

        # validate the config with pydantic
        try:
            _ = ConfigYAMLSchema(**config_schema.config.dict())
        except ValidationError as exc:
            for error in exc.errors():
                logger.error(error)
            raise HTTPException(
                status_code=400, detail=f"Invalid configuration: {exc.errors}"
            ) from exc

        if os.path.exists(config_file_name):
            backup_filename = f"{config_file_name}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename(config_file_name, backup_filename)
            response.operation_status["config_backup_filename"] = backup_filename

        with open(config_file_name, "w", encoding="utf-8") as new_config_file:
            yaml.dump(
                config_schema.config.dict(),
                new_config_file,
                allow_unicode=False,
                encoding="utf-8",
                explicit_start=True,
                sort_keys=False,
                indent=2,
                default_flow_style=False,
            )

        response.success = True

        return response


router = ConfigRouter().router
