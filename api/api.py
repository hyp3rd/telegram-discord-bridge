"""API for the bridge."""
import os
from datetime import datetime
from multiprocessing import Process

import magic
import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware import Middleware
from pydantic import ValidationError

from api.models import ConfigSchema
from api.rate_limiter import RateLimitMiddleware
from bridge.config import Config
from bridge.logger import Logger
from forwarder import controller, determine_process_state

config = Config()
logger = Logger.init_logger(config.app.name, config.logger)


class BridgeAPI:
    """Bridge API."""

    def __init__(self):
        self.bridge_process = None
        self.app = FastAPI(middleware=[Middleware(
            RateLimitMiddleware, limit=20, interval=60)])
        self.app.get("/")(self.index)
        self.app.get("/health")(self.health)
        self.app.post("/start")(self.start)
        self.app.post("/stop")(self.stop)
        self.app.post("/upload")(self.upload_config)

    async def index(self):
        """index."""

        return {
            "name": config.app.name,
            "version": config.app.version,
            "description": config.app.description,
            "healthcheck_interval": config.app.healthcheck_interval,
            "recoverer_delay": config.app.recoverer_delay,
            "debug": config.app.debug is True,
        }

    async def health(self):
        """health."""
        if self.bridge_process and self.bridge_process.is_alive():
            pid_file = f'{config.app.name}.pid'
            process_state, pid = determine_process_state(pid_file)

            return {
                "process_status": f"{process_state} (PID: {pid})",
                "status": config.status,
            }

        return {"process_status": "not running"}

    async def start(self):
        """start the bridge."""
        if self.bridge_process is None or not self.bridge_process.is_alive():
            self.bridge_process = Process(
                target=controller, args=(True, True, False,))
            self.bridge_process.start()
            return {"message": "Bridge started"}

        return {"message": "Bridge already running"}

    async def stop(self):
        """stop the bridge."""
        if self.bridge_process and self.bridge_process.is_alive():
            controller(boot=False, background=False, stop=True)
            self.bridge_process.join()
            self.bridge_process = None
            return {"message": "Bridge stopped"}

        return {"message": "Bridge not running"}

    async def upload_config(self, file: UploadFile = File(...)):
        """upload the config file."""
        content = await file.read()
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(content)

        logger.debug("Uploaded file type: %s", mime_type)
        # if mime_type != 'application/x-yaml' or mime_type != 'text/yaml' or mime_type != 'text/plain':
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
                status_code=400, detail=f'Invalid configuration: {exc}') from exc

        # validate here
        config.validate_config(new_config_file_content)

        if os.path.exists("config.yml"):
            backup_filename = f"config_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename("config.yml", backup_filename)

        with open("config.yml", "w", encoding="utf-8") as new_config_file:
            yaml.dump(new_config_file_content, new_config_file)

        return {"message": "Configuration file uploaded successfully"}


app = BridgeAPI().app
