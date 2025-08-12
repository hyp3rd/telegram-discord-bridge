"""Handler for healthchecks"""

import asyncio
import logging
import socket
from concurrent.futures import ThreadPoolExecutor

import discord
from prometheus_client import Counter, Gauge
from telethon import TelegramClient

from bridge.config import Config
from bridge.discord import DiscordClientHealth
from bridge.events import EventDispatcher
from bridge.logger import Logger
from core import SingletonMeta

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)

INTERNET_UP = Gauge("bridge_internet_up", "Internet connectivity status")
TELEGRAM_UP = Gauge("bridge_telegram_up", "Telegram API status")
DISCORD_UP = Gauge("bridge_discord_up", "Discord API status")
HEALTH_FAILURES = Counter(
    "bridge_healthcheck_failures_total", "Total health check failures", ["component"]
)


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
        self.log = logging.LoggerAdapter(logger, {"component": "health"})

    def _alert(self, component: str, error: Exception | str) -> None:
        """Emit an alert for a failed health check."""
        HEALTH_FAILURES.labels(component=component).inc()
        message = str(error)
        self.log.error("%s health check failed: %s", component, message)
        self.dispatcher.notify("alert", {"component": component, "error": message})

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
            INTERNET_UP.set(1)
            return True
        except socket.gaierror as ex:
            self._alert("internet", ex)
            INTERNET_UP.set(0)
            return False
        except OSError as ex:
            self._alert("internet", ex)
            INTERNET_UP.set(0)
            return False

    async def check(self, interval: int = 30):
        """Check the health of the Discord and Telegram APIs periodically."""
        # Check for internet connectivity
        while True:
            try:
                has_connectivity = await self.internet_connectivity_check()
                if has_connectivity:
                    self.log.debug("The bridge is online.")
                    config.application.internet_connected = True
                else:
                    self.log.warning("Unable to reach the internet.")
                    config.application.internet_connected = False
                    # wait for the specified interval
                    await asyncio.sleep(interval)
                    await self.check(interval)

            except Exception as ex:  # pylint: disable=broad-except
                self._alert("internet", ex)

            # Check Telegram API status
            try:
                if self.telegram_client.is_connected():
                    await self.telegram_client.get_me()
                    self.log.debug("Telegram API is healthy.")
                    config.telegram.is_healthy = True
                    TELEGRAM_UP.set(1)
            except ConnectionError as ex:
                self._alert("telegram", ex)
                config.telegram.is_healthy = False
                TELEGRAM_UP.set(0)
            except Exception as ex:  # pylint: disable=broad-except
                self._alert("telegram", ex)
                config.telegram.is_healthy = False
                TELEGRAM_UP.set(0)

            # Check Discord API status
            try:
                discord_status, is_healthy = self.discord_client_health.report_status(
                    self.discord_client, config.discord.max_latency
                )
                if is_healthy:
                    self.log.debug("Discord API is healthy.")
                    config.discord.is_healthy = True
                    DISCORD_UP.set(1)
                else:
                    self.log.warning(discord_status)
                    config.discord.is_healthy = False
                    DISCORD_UP.set(0)
            except Exception as ex:  # pylint: disable=broad-except
                self._alert("discord", ex)
                config.discord.is_healthy = False
                DISCORD_UP.set(0)

            self.dispatcher.notify("healthcheck", config)
            # Sleep for the given interval and retry
            await asyncio.sleep(interval)
