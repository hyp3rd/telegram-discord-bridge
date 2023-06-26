"""API for the bridge."""

from enum import Enum

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from api.models import APIConfig, ApplicationConfig, ConfigSummary
from api.rate_limiter import RateLimitMiddleware
from api.routers import auth, bridge, config
from bridge.config import Config
from bridge.logger import Logger

logger = Logger.init_logger(Config.get_instance().application.name, Config.get_instance().logger)


class APIVersion(str, Enum):
    """Process State Enum."""
    V1 = "/api/v1"
    V2 = "/api/v2"


class BridgeAPI: # pylint: disable=too-few-public-methods
    """Bridge API."""

    # This is the main function that starts the application
    def __init__(self):
        # The bridge_process variable is used to store the bridge process
        self.bridge_process = None
        config_instance = Config.get_instance()
        # The app variable is the main FastAPI instance
        self.app = FastAPI(
            title=config_instance.application.name,
            description=config_instance.application.description,
            version=config_instance.application.version,
            debug=config_instance.application.debug,
            # The RateLimitMiddleware is used to limit the number of requests to 20 per minute
            middleware=[
                Middleware(RateLimitMiddleware, limit=20, interval=60),
                # The CORSMiddleware is used to allow requests from the web interface
                Middleware(CORSMiddleware,
                           allow_origins=config_instance.api.cors_origins,
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

        # auth router `api/v1/auth` is used to authenticate the user
        self.app.include_router(router=auth.router,
                                prefix=APIVersion.V1.value)

        # The bridge router is used to control the bridge: `api/v1/bridge`
        # It contains the start, stop, and health endpoints
        self.app.include_router(router=bridge.router,
                                prefix=APIVersion.V1.value)

        # The config router is used to control the bridge configuration: `api/v1/config`
        self.app.include_router(router=config.router,
                                prefix=APIVersion.V1.value)


    def index(self):
        """index."""
        config_instance = Config.get_instance()
        return ConfigSummary(
            application=ApplicationConfig(
                name=config_instance.application.name,
                version=config_instance.application.version,
                description=config_instance.application.description,
                healthcheck_interval=config_instance.application.healthcheck_interval,
                recoverer_delay=config_instance.application.recoverer_delay,
                debug=config_instance.application.debug,
            ),
            api=APIConfig(
                enabled=config_instance.api.enabled,
                cors_origins=config_instance.api.cors_origins,
                telegram_login_enabled=config_instance.api.telegram_login_enabled,
                telegram_auth_file=config_instance.api.telegram_auth_file,
                telegram_auth_request_expiration=config_instance.api.telegram_auth_request_expiration,
            ))


app = BridgeAPI().app
