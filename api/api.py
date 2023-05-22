"""API for the bridge."""
import json
import os
from datetime import datetime
from multiprocessing import Process

import magic
import yaml
from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError  # pylint: disable=import-error

from api.models import ConfigSchema, MFACodePayload
from api.rate_limiter import RateLimitMiddleware
from bridge.config import Config
from bridge.logger import Logger
from forwarder import controller, determine_process_state

config = Config()
logger = Logger.init_logger(config.app.name, config.logger)

origins = [
    "https://develop.d3b2ymfde2iupy.amplifyapp.com",
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:8000",
    "http://localhost:5000",
    "http:s//hyperd.io",
]


class BridgeAPI:
    """Bridge API."""

    # This is the main function that starts the application
    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process = None
        # The app variable is the main FastAPI instance
        self.app = FastAPI(
            # The RateLimitMiddleware is used to limit the number of requests to 20 per minute
            middleware=[
                Middleware(RateLimitMiddleware, limit=20, interval=60),
                # The CORSMiddleware is used to allow requests from the web interface
                Middleware(CORSMiddleware,
                           allow_origins=origins,
                           allow_credentials=True,
                           allow_methods=["*"],
                           allow_headers=["*"])
            ]
        )
        # The index function is used to return the index page
        self.app.get("/")(self.index)
        # The health function is used to return the health check page
        self.app.get("/health")(self.health)
        # The receive_code function is used to receive the code sent by the user
        self.app.post("/mfa")(self.receive_code)
        # The start function is used to start the bridge
        self.app.post("/start")(self.start)
        # The stop function is used to stop the bridge
        self.app.post("/stop")(self.stop)
        # The upload_config function is used to upload the configuration file to the bridge
        self.app.post("/upload")(self.upload_config)

    def index(self):
        """index."""

        return {
            "name": config.app.name,
            "version": config.app.version,
            "description": config.app.description,
            "healthcheck_interval": config.app.healthcheck_interval,
            "recoverer_delay": config.app.recoverer_delay,
            "debug": config.app.debug,
            "api_login_enabled": config.app.api_login_enabled,
        }

    def health(self):
        """health."""
        if self.bridge_process and self.bridge_process.is_alive():
            pid_file = f'{config.app.name}.pid'
            process_state, pid = determine_process_state(pid_file)

            return {
                "process_status": f"{process_state} (PID: {pid})",
                "status": config.get_status(key=None),
            }
        return {"process_status": "not running", "status": config.get_status(key=None)}

    async def receive_code(self, payload: MFACodePayload = Body(...)):
        """Receive the MFA code."""
        # Write the code to a file.
        with open('mfa.json', 'w', encoding="utf-8") as mfa_file:
            json.dump({'code': payload.code}, mfa_file)
        # Return a response.
        return {"operation_status": "code received successfully"}

    async def start(self):
        """start the bridge."""
        pid_file = f'{config.app.name}.pid'
        process_state, pid = determine_process_state(pid_file)
        if pid == 0 and self.bridge_process is None or not self.bridge_process.is_alive():
            self.bridge_process = Process(
                target=controller, args=(True, True, False,))
            self.bridge_process.start()
            return {"operation_status": f"starting the bridge {config.app.name}, version {config.app.version}"}
        if pid == 0 and self.bridge_process is not None and self.bridge_process.is_alive():
            return {"operation_status": f"the bridge {config.app.name}, version {config.app.version} is starting"}
        return {"operation_status": f"the bridge {config.app.name}, version {config.app.version} is {process_state} (PID: {pid})"}

    async def stop(self):
        """stop the bridge."""
        if self.bridge_process and self.bridge_process.is_alive():
            controller(boot=False, background=False, stop=True)
            self.bridge_process.join()
            self.bridge_process = None
            return {"operation_status": f"stopping the bridge {config.app.name}"}

        return {"operation_status": f"the bridge {config.app.name} is not running"}

    async def upload_config(self, file: UploadFile = File(...)):
        """upload the config file."""
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

        if os.path.exists("config.yml"):
            backup_filename = f"config_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.yml"
            os.rename("config.yml", backup_filename)

        with open("config.yml", "w", encoding="utf-8") as new_config_file:
            yaml.dump(new_config_file_content, new_config_file)

        return {"operation_status": "Configuration file uploaded successfully"}


app = BridgeAPI().app
