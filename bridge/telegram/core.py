"""Telegram handler."""

import asyncio
import os
from asyncio.events import AbstractEventLoop

from telethon import TelegramClient
from telethon.errors.rpcerrorlist import (
    FloodWaitError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
    SessionRevokedError,
)

from bridge.config import Config
from bridge.events import EventDispatcher
from bridge.logger import Logger
from bridge.security.secret_manager import SecretManager
from core import SingletonMeta

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class TelegramHandler(metaclass=SingletonMeta):
    """Telegram handler class."""

    dispatcher: EventDispatcher

    def __init__(self, dispatcher: EventDispatcher):
        """Initialize the handler."""

        self.dispatcher = dispatcher

    # Check if the session file exist
    def has_session_file(self) -> bool:
        """Check if the Telegram session file exists."""
        return os.path.isfile(f"{config.application.name}.session")

    async def _get_creds_from_store(self, key: str) -> str | int:
        """Wait for credentials to be provided through the secret manager."""
        manager = SecretManager.get_instance()
        return await manager.get(key, config.api.telegram_auth_request_expiration)

    async def get_password(self) -> str:
        """Get the Telegram password from the API payload,
        the `TELEGRAM_PASSWORD` environment variable, or the config file."""
        telegram_password = os.getenv("TELEGRAM_PASSWORD", None)
        logger.debug("Attempting to get the Telegram password")
        if telegram_password is not None:
            return telegram_password
        if not config.api.telegram_login_enabled:
            return config.telegram.password

        telegram_password = await self._get_creds_from_store("password")
        return str(telegram_password)

    async def get_auth_code(self) -> str | int:
        """Get the Telegram auth code from the API payload, or the user's input."""
        logger.debug("Attempting to get the Telegram auth code")
        if config.api.enabled and config.api.telegram_login_enabled:
            return await self._get_creds_from_store("code")

        code = input("Enter the Telegram 2FA code: ")
        if not code:
            raise ValueError("No code was entered.")

        return code

    async def init_client(  # pylint: disable=too-many-statements
        self, event_loop: AbstractEventLoop | None = None
    ) -> TelegramClient:  # pylint: disable=too-many-statements
        """Init the Telegram client."""
        logger.info("Initializing Telegram client...")

        if event_loop is None:
            logger.warning("Inferring the current event loop into the Telegram client")
            event_loop = asyncio.get_event_loop()

        telethon_logger = Logger.get_telethon_logger()
        telethon_logger_handler = Logger.generate_handler(
            f"{config.application.name}_telegram", config.logger
        )
        telethon_logger.addHandler(telethon_logger_handler)

        telegram_client = TelegramClient(
            session=config.application.name,
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash,
            connection_retries=15,
            retry_delay=4,
            base_logger=telethon_logger,
            lang_code="en",
            system_lang_code="en",
            loop=event_loop,
        )

        telegram_client.parse_mode = "markdown"
        await telegram_client.connect()

        logger.info("Signing in to Telegram...")

        def code_callback():
            return self.get_auth_code()

        def password_callback():
            return self.get_password()

        try:
            await telegram_client.start(
                phone=config.telegram.phone,  # type: ignore
                code_callback=code_callback,  # type: ignore
                password=password_callback,
            )  # type: ignore
        except FloodWaitError as ex:
            logger.error(
                "Telegram client failed to start: %s",
                ex,
                exc_info=config.application.debug,
            )

            logger.warning("Retrying Telegram client start in %s seconds", ex.seconds)
            await asyncio.sleep(ex.seconds)
            await telegram_client.start(
                phone=config.telegram.phone,  # type: ignore
                code_callback=code_callback,  # type: ignore
                password=password_callback,
            )  # type: ignore

        except SessionPasswordNeededError:
            logger.error(
                "Telegram client failed to start: %s",
                "2FA is enabled but no password was provided",
                exc_info=config.application.debug,
            )
            if config.api.telegram_login_enabled:
                manager = SecretManager.get_instance()
                await manager.set(
                    "error",
                    "2FA is enabled but no password was provided",
                )
                await manager.set("mfa_required", True)
            raise

        except SessionRevokedError:
            logger.error(
                "Telegram client failed to start: %s",
                "The current session was revoked",
                exc_info=config.application.debug,
            )
            if config.api.telegram_login_enabled:
                manager = SecretManager.get_instance()
                await manager.set(
                    "error", "The current session was revoked"
                )
                await manager.set("session_revoked", True)
            raise
        except PhoneCodeInvalidError:
            logger.error(
                "Telegram client failed to start: %s",
                "The phone code is invalid",
                exc_info=config.application.debug,
            )
            if config.api.telegram_login_enabled:
                manager = SecretManager.get_instance()
                await manager.set(
                    "error", "The phone code is invalid"
                )
                await manager.set("phone_code_invalid", True)
            raise
        manager = SecretManager.get_instance()
        manager.clear("code")
        manager.clear("password")
        manager.clear("error")
        manager.clear("mfa_required")
        manager.clear("session_revoked")
        manager.clear("phone_code_invalid")

        bot_identity = await telegram_client.get_me(input_peer=False)
        logger.info(
            "Telegram client started the session: %s, with identity: %s",
            config.application.name,
            bot_identity.id,
        )  # type: ignore

        return telegram_client
