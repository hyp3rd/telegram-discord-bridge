"""Handler for healthchecks"""

import asyncio
import json
import socket
from concurrent.futures import ThreadPoolExecutor

import discord
from telethon import TelegramClient

from bridge.config import Config
from bridge.discord import DiscordClientHealth
from bridge.events import EventDispatcher
from bridge.logger import Logger
from bridge.telemetry import update_health_metrics
from core import SingletonMeta

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class HealthHandler(metaclass=SingletonMeta):
    """Handler class for healthchecks."""

    telegram_client: TelegramClient
    discord_client: discord.Client

    discord_client_health: DiscordClientHealth
    dispatcher: EventDispatcher

    def __init__(
        self,
        dispatcher: EventDispatcher,
        telegram_client: TelegramClient,
        discord_client: discord.Client,
    ):
        """Initialize the handler."""

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
            host = await loop.run_in_executor(
                self.executor, socket.gethostbyname, ("google.com")
            )
            await loop.run_in_executor(
                self.executor, socket.create_connection, (host, 443), 5
            )
            return True
        except socket.gaierror as ex:
            logger.error(
                "Unable to resolve hostname: %s", ex, exc_info=config.application.debug
            )
            return False
        except OSError as ex:
            logger.error(
                "Unable to reach the internet: %s",
                ex,
                exc_info=config.application.debug,
            )
            return False

    async def check(self, interval: int = 30):
        """Check the health of the Discord and Telegram APIs periodically."""
        # Check for internet connectivity
        while True:
            try:
                has_connectivity = await self.internet_connectivity_check()
                if has_connectivity:
                    logger.debug("The bridge is online.")
                    config.application.internet_connected = True
                else:
                    logger.warning("Unable to reach the internet.")
                    config.application.internet_connected = False
                    self.dispatcher.notify(
                        "alert", {"component": "internet", "status": False}
                    )
                    await asyncio.sleep(interval)
                    await self.check(interval)

            except Exception as ex:  # pylint: disable=broad-except
                logger.error(
                    "An error occurred while checking internet connectivity: %s",
                    ex,
                    exc_info=config.application.debug,
                )

            # Check Telegram API status
            try:
                if self.telegram_client.is_connected():
                    await self.telegram_client.get_me()
                    logger.debug("Telegram API is healthy.")
                    config.telegram.is_healthy = True
            except ConnectionError as ex:
                logger.error("Unable to reach the Telegram API: %s", ex)
                config.telegram.is_healthy = False
                self.dispatcher.notify(
                    "alert", {"component": "telegram", "status": False}
                )
            except Exception as ex:  # pylint: disable=broad-except
                logger.error(
                    "An error occurred while connecting to the Telegram API: %s",
                    ex,
                    exc_info=config.application.debug,
                )
                config.telegram.is_healthy = False
                self.dispatcher.notify(
                    "alert", {"component": "telegram", "status": False}
                )

            # Check Discord API status
            try:
                discord_status, is_healthy = self.discord_client_health.report_status(
                    self.discord_client, config.discord.max_latency
                )
                if is_healthy:
                    logger.debug("Discord API is healthy.")
                    config.discord.is_healthy = True
                else:
                    logger.warning(discord_status)
                    config.discord.is_healthy = False
                    self.dispatcher.notify(
                        "alert", {"component": "discord", "status": False}
                    )
            except Exception as ex:  # pylint: disable=broad-except
                logger.error(
                    "An error occurred while connecting to the Discord API: %s",
                    ex,
                    exc_info=config.application.debug,
                )
                config.discord.is_healthy = False
                self.dispatcher.notify(
                    "alert", {"component": "discord", "status": False}
                )

            update_health_metrics(config)
            logger.info(
                json.dumps(
                    {
                        "internet": config.application.internet_connected,
                        "telegram": config.telegram.is_healthy,
                        "discord": config.discord.is_healthy,
                    }
                )
            )
            self.dispatcher.notify("healthcheck", config)
            await asyncio.sleep(interval)
