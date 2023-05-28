"""API for the bridge."""
import os
from datetime import datetime
from enum import Enum

import magic
import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError  # pylint: disable=import-error

from api.models import (APIConfig, ApplicationConfig, ConfigSchema,
                        ConfigSummary)
from api.rate_limiter import RateLimitMiddleware
from api.routers import auth, bridge, health
from bridge.config import Config
from bridge.logger import Logger

logger = Logger.init_logger(Config().app.name, Config().logger)


class APIVersion(str, Enum):
    """Process State Enum."""
    V1 = "/api/v1"
    V2 = "/api/v2"


class BridgeAPI:
    """Bridge API."""

    # This is the main function that starts the application
    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process = None
        config = Config.get_config_instance()
        # The app variable is the main FastAPI instance
        self.app = FastAPI(
            title=config.app.name,
            description=config.app.description,
            version=config.app.version,
            debug=config.app.debug,
            # The RateLimitMiddleware is used to limit the number of requests to 20 per minute
            middleware=[
                Middleware(RateLimitMiddleware, limit=20, interval=60),
                # The CORSMiddleware is used to allow requests from the web interface
                Middleware(CORSMiddleware,
                           allow_origins=config.api.cors_origins,
                           allow_credentials=True,
                           allow_methods=["*"],
                           allow_headers=["*"])
            ]
        )

        # The index function is used to return the index page
        self.app.get(path="/",
                     tags=["index"],
                     name="The Telegram to Discord Bridge API",
                     summary="Summary report of the Bridge",
                     description="The Bridge API provides a way to control the telegram-discord-bridge",
                     response_model=ConfigSummary)(self.index)

        # health router `api/v1/health` is used to get the health of the bridge
        self.app.include_router(router=health.router,
                                prefix=APIVersion.V1.value)

        # auth router `api/v1/auth` is used to authenticate the user
        self.app.include_router(router=auth.router,
                                prefix=APIVersion.V1.value)

        # The bridge router is used to control the bridge
        self.app.include_router(router=bridge.router,
                                prefix=APIVersion.V1.value)

        # # The start function is used to start the bridge
        # self.app.post("/start")(self.start)
        # # The stop function is used to stop the bridge
        # self.app.post("/stop")(self.stop)
        # # The upload_config function is used to upload the configuration file to the bridge
        self.app.post("/upload")(self.upload_config)

    def index(self):
        """index."""
        config = Config.get_config_instance()
        return ConfigSummary(
            application=ApplicationConfig(
                name=config.app.name,
                version=config.app.version,
                description=config.app.description,
                healthcheck_interval=config.app.healthcheck_interval,
                recoverer_delay=config.app.recoverer_delay,
                debug=config.app.debug,
            ),
            api=APIConfig(
                cors_origins=config.api.cors_origins,
                telegram_login_enabled=config.api.telegram_login_enabled,
                telegram_auth_file=config.api.telegram_auth_file,
                telegram_auth_request_expiration=config.api.telegram_auth_request_expiration,
            ))

    # def health(self):
    #     """Return the health of this service."""
    #     if self.bridge_process and self.bridge_process.is_alive():
    #         pid_file = f'{config.app.name}.pid'
    #         process_state, pid = determine_process_state(pid_file)

    #         return {
    #             "process_state": process_state,
    #             "process_id": pid,
    #             "status": Config().get_status(key=None),
    #         }
    #     return {"process_state": "not running", "status": config.get_status(key=None)}

    # async def start(self):
    #     """start the bridge."""
    #     config = Config.get_config_instance()
    #     pid_file = f'{config.app.name}.pid'
    #     process_state, pid = determine_process_state(pid_file)
    #     if pid == 0 and self.bridge_process is None or not self.bridge_process.is_alive():
    #         self.bridge_process = Process(
    #             target=controller, args=(True, True, False,))
    #         self.bridge_process.start()
    #         return {"operation_status": f"starting the bridge {config.app.name}, version {config.app.version}"}
    #     if pid == 0 and self.bridge_process is not None and self.bridge_process.is_alive():
    #         return {"operation_status": f"the bridge {config.app.name}, version {config.app.version} is starting"}
    #     return {"operation_status": f"the bridge {config.app.name}, version {config.app.version} is {process_state} (PID: {pid})"}

    # async def stop(self):
    #     """stop the bridge."""
    #     config = Config.get_config_instance()
    #     if self.bridge_process and self.bridge_process.is_alive():
    #         controller(boot=False, background=False, stop=True)
    #         self.bridge_process.join()
    #         self.bridge_process = None
    #         return {"operation_status": f"stopping the bridge {config.app.name}"}

    #     return {"operation_status": f"the bridge {config.app.name} is not running"}

    async def upload_config(self, file: UploadFile = File(...)):
        """upload the config file."""
        config = Config.get_config_instance()

        content = await file.read()
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(content)

        logger.debug("Uploaded file type: %s", mime_type)

        if mime_type != 'text/plain':
            raise HTTPException(
                status_code=400, detail="Invalid file type. Only YAML file is accepted.")

        try:
            new_config_file_content = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise HTTPException(
                status_code=400, detail='Invalid YAML file.') from exc

        try:
            _ = ConfigSchema(**new_config_file_content)
        except ValidationError as exc:
            raise HTTPException(
                status_code=400, detail=f'Invalid configuration: {exc.errors}') from exc

        # validate here
        valid, errors = config.validate_config(new_config_file_content)
        if not valid:
            raise HTTPException(
                status_code=400, detail=f'{errors}')

        new_config_file_name = f'config-{new_config_file_content["application"]["version"]}.yml'

        if os.path.exists(new_config_file_name):
            backup_filename = f"{new_config_file_name}_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename(new_config_file_name, backup_filename)

        with open(new_config_file_name, "w", encoding="utf-8") as new_config_file:
            yaml.dump(new_config_file_content, new_config_file)

        config.set_version(new_config_file_content["application"]["version"])

        return {"operation_status": "Configuration file uploaded successfully"}


app = BridgeAPI().app
