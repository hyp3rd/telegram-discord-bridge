"""Handler for healthchecks"""

import asyncio
import socket
from concurrent.futures import ThreadPoolExecutor

import discord
from telethon import TelegramClient

from bridge.config import Config
from bridge.discord_handler import DiscordClientHealth
from bridge.events import EventDispatcher
from bridge.logger import Logger


class SingletonMeta(type):
    """Singleton metaclass."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class HealthHandler(metaclass=SingletonMeta):
    """Handler class for healthchecks."""

    config: Config
    logger: Logger
    telegram_client: TelegramClient
    discord_client: discord.Client

    discord_client_health: DiscordClientHealth
    dispatcher: EventDispatcher

    def __init__(self, dispatcher: EventDispatcher, telegram_client: TelegramClient, discord_client: discord.Client):
        """Initialize the handler."""
        self.config = Config.get_instance()
        self.logger = Logger.init_logger(self.config.application.name, self.config.logger)

        self.dispatcher = dispatcher

        self.telegram_client = telegram_client
        self.discord_client = discord_client

        self.discord_client_health = DiscordClientHealth()

        self.executor = ThreadPoolExecutor()


    async def internet_connectivity_check(self) -> bool:
        """Check if the bridge has internet connectivity."""
        loop = asyncio.get_running_loop()
        try:
            # host = await loop.run_in_executor(executor, socket.gethostbyname, ("one.one.one.one"))
            host = await loop.run_in_executor(self.executor, socket.gethostbyname, ("google.com"))
            await loop.run_in_executor(self.executor, socket.create_connection, (host, 443), 5)
            return True
        except socket.gaierror as ex:
            self.logger.error("Unable to resolve hostname: %s", ex, exc_info=self.config.application.debug)
            return False
        except OSError as ex:
            self.logger.error("Unable to reach the internetL %s", ex, exc_info=self.config.application.debug)
            return False


    async def check(self, interval: int = 30):
        """Check the health of the Discord and Telegram APIs periodically."""
        # Check for internet connectivity
        while True:
            try:
                has_connectivity = await self.internet_connectivity_check()
                if has_connectivity:
                    self.logger.debug("The bridge is online.")
                    # set the internet connectivity status to True
                    self.config.application.internet_connected = True
                else:
                    self.logger.warning("Unable to reach the internet.")
                    # set the internet connectivity status to False
                    self.config.application.internet_connected = False
                    # wait for the specified interval
                    await asyncio.sleep(interval)
                    await self.check(interval)

            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error(
                    "An error occurred while checking internet connectivity: %s", ex, exc_info=self.config.application.debug)

            # Check Telegram API status
            try:
                if self.telegram_client.is_connected():
                    await self.telegram_client.get_me()
                    self.logger.debug("Telegram API is healthy.")
                    # set the Telegram availability status to True
                    self.config.telegram.is_healthy = True
            except ConnectionError as ex:
                self.logger.error("Unable to reach the Telegram API: %s", ex)
                # set the Telegram availability status to False
                self.config.telegram.is_healthy = False
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error(
                    "An error occurred while connecting to the Telegram API: %s", ex, exc_info=self.config.application.debug)
                # set the Telegram availability status to False
                self.config.telegram.is_healthy = False

            # Check Discord API status
            try:
                discord_status, is_healthy = self.discord_client_health.report_status(
                    self.discord_client,  self.config.discord.max_latency)
                if is_healthy:
                    self.logger.debug("Discord API is healthy.")
                    # set the Discord availability status to True
                    self.config.discord.is_healthy = True
                else:
                    self.logger.warning(discord_status)
                    # set the Discord availability status to False
                    self.config.discord.is_healthy = False
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.error(
                    "An error occurred while connecting to the Discord API: %s", ex, exc_info=self.config.application.debug)
                # set the Discord availability status to False
                self.config.discord.is_healthy = False

            self.dispatcher.notify("healthcheck", self.config)
            # Sleep for the given interval and retry
            await asyncio.sleep(interval)
