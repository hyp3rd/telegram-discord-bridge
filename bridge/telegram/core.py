"""Telegram handler."""
import asyncio
import json
import os
from asyncio.events import AbstractEventLoop

from telethon import TelegramClient
from telethon.errors.rpcerrorlist import (FloodWaitError,
                                          PhoneCodeInvalidError,
                                          SessionPasswordNeededError,
                                          SessionRevokedError)

from bridge.config import Config
from bridge.events import EventDispatcher
from bridge.logger import Logger

# logger = Logger.get_logger(Config.get_instance().application.name)

class SingletonMeta(type):
    """Singleton metaclass."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class TelegramHandler(metaclass=SingletonMeta):
    """Telegram handler class."""

    config: Config
    logger: Logger
    dispatcher: EventDispatcher

    def __init__(self, dispatcher: EventDispatcher):
        """Initialize the handler."""
        self.config = Config.get_instance()
        self.logger = Logger.init_logger(self.config.application.name, self.config.logger)

        self.dispatcher = dispatcher

    # Check if the session file and the auth file exist
    # to estabils the user has an active session
    def has_session_file(self) -> bool:
        """Check if the Telegram session file exists."""
        if os.path.isfile(f"{self.config.application.name}.session") and os.path.isfile(self.config.api.telegram_auth_file):
            return True
        return False


    async def _get_creds_from_file(self, key: str) -> str | int:
        """Wait for the auth file to be created and then read a value from it."""
        # Wait for the auth file to be created with a timeout of 120 seconds
        for _ in range(self.config.api.telegram_auth_request_expiration):
            if os.path.isfile(self.config.api.telegram_auth_file):
                with open(self.config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                    value = json.load(auth_file).get(key)
                if value:
                    self.logger.debug("Got the Telegram %s", key)
                    return value
            await asyncio.sleep(1)
        raise TimeoutError(f"Timeout waiting for {key}")


    async def get_password(self) -> str:
        """Get the Telegram password from the API payload,
        the `TELEGRAM_PASSWORD` environment variable, or the config file."""
        telegram_password = os.getenv("TELEGRAM_PASSWORD", None)
        self.logger.debug("Attempting to get the Telegram password")
        if telegram_password is not None:
            return telegram_password
        if not self.config.api.telegram_login_enabled:
            return self.config.telegram.password.get_secret_value()

        telegram_password = await self._get_creds_from_file('password')
        return str(telegram_password)


    async def get_auth_code(self) -> str | int:
        """Get the Telegram auth code from the API payload, or the user's input."""
        self.logger.debug("Attempting to get the Telegram auth code")
        if self.config.api.telegram_login_enabled:
            return await self._get_creds_from_file('code')

        code = input("Enter the Telegram 2FA code: ")
        if not code:
            raise ValueError("No code was entered.")

        return code


    async def init_client(self, event_loop: AbstractEventLoop | None = None) -> TelegramClient: # pylint: disable=too-many-statements
        """Init the Telegram client."""
        self.logger.info("Initializing Telegram client...")

        if event_loop is None:
            self.logger.warning("Inferring the current event loop into the Telegram client")
            event_loop = asyncio.get_event_loop()

        telethon_logger = Logger.get_telethon_logger()
        telethon_logger_handler = Logger.generate_handler(
            f"{self.config.application.name}_telegram", self.config.logger)
        telethon_logger.addHandler(telethon_logger_handler)

        telegram_client = TelegramClient(
            session=self.config.application.name,
            api_id=self.config.telegram.api_id,
            api_hash=self.config.telegram.api_hash,
            connection_retries=15,
            retry_delay=4,
            base_logger=telethon_logger,
            lang_code="en",
            system_lang_code="en",
            loop=event_loop,)

        telegram_client.parse_mode = "markdown"
        await telegram_client.connect()

        self.logger.info("Signing in to Telegram...")

        def code_callback():
            return self.get_auth_code()

        try:
            await telegram_client.start(
                phone=self.config.telegram.phone, # type: ignore
                code_callback=code_callback,  # type: ignore
                password=lambda: self.get_password())  # type: ignore
        except FloodWaitError as ex:
            self.logger.error("Telegram client failed to start: %s",
                        ex, exc_info=self.config.application.debug)

            self.logger.warning(
                "Retrying Telegram client start in %s seconds", ex.seconds)
            await asyncio.sleep(ex.seconds)
            await telegram_client.start(
                phone=self.config.telegram.phone, # type: ignore
                code_callback=code_callback,  # type: ignore
                password=lambda: self.get_telegram_password())  # type: ignore

        except SessionPasswordNeededError:
            self.logger.error("Telegram client failed to start: %s",
                        "2FA is enabled but no password was provided",
                        exc_info=self.config.application.debug)
            # append to the json file that 2FA is enabled
            if os.path.isfile(self.config.api.telegram_auth_file) and self.config.api.telegram_login_enabled:
                with open(self.config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                    auth_data = json.load(auth_file)
                auth_data["mfa_required"] = True
                auth_data["error"] = "2FA is enabled but no password was provided"
                with open(self.config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
                    json.dump(auth_data, auth_file)
            raise

        except SessionRevokedError:
            self.logger.error("Telegram client failed to start: %s",
                        "The current session was revoked",
                        exc_info=self.config.application.debug)
            if os.path.isfile(self.config.api.telegram_auth_file) and self.config.api.telegram_login_enabled:
                # append to the json file that the session was revoked
                with open(self.config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                    auth_data = json.load(auth_file)
                auth_data["session_revoked"] = True
                auth_data["error"] = "The current session was revoked"
                with open(self.config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
                    json.dump(auth_data, auth_file)
            raise
        except PhoneCodeInvalidError:
            self.logger.error("Telegram client failed to start: %s",
                        "The phone code is invalid",
                        exc_info=self.config.application.debug)
            if os.path.isfile(self.config.api.telegram_auth_file) and self.config.api.telegram_login_enabled:
                # append to the json file that the phone code is invalid
                with open(self.config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                    auth_data = json.load(auth_file)
                auth_data["phone_code_invalid"] = True
                auth_data["error"] = "The phone code is invalid"
                with open(self.config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
                    json.dump(auth_data, auth_file)
            raise

        # os.remove(config.telegram.auth_file)

        bot_identity = await telegram_client.get_me(input_peer=False)
        self.logger.info("Telegram client started the session: %s, with identity: %s",
                    self.config.application.name, bot_identity.id)  # type: ignore

        return telegram_client
