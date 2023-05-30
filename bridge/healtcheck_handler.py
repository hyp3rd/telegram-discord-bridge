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

config = Config.get_config_instance()
logger = Logger.get_logger(config.app.name)

discord__client_health = DiscordClientHealth()

executor = ThreadPoolExecutor()


async def internet_connectivity_check() -> bool:
    """Check if the bridge has internet connectivity."""
    loop = asyncio.get_running_loop()
    try:
        host = await loop.run_in_executor(executor, socket.gethostbyname, ("one.one.one.one"))
        await loop.run_in_executor(executor, socket.create_connection, (host, 443), 5)
        return True
    except OSError:
        return False


async def healthcheck(dispatcher: EventDispatcher, tgc: TelegramClient, dcl: discord.Client, interval: int = 30):
    """Check the health of the Discord and Telegram APIs periodically."""
    # Check for internet connectivity
    while True:
        try:
            has_connectivity = await internet_connectivity_check()
            if has_connectivity:
                logger.debug("The bridge is online.")
                # set the internet connectivity status to True
                config.app.internet_connected = True
            else:
                logger.warning("Unable to reach the internet.")
                # set the internet connectivity status to False
                config.app.internet_connected = False
                # wait for the specified interval
                await asyncio.sleep(interval)
                await healthcheck(dispatcher, tgc, dcl, interval)

        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while checking internet connectivity: %s", ex, exc_info=config.app.debug)

        # Check Telegram API status
        try:
            if tgc.is_connected():
                await tgc.get_me()
                logger.debug("Telegram API is healthy.")
                # set the Telegram availability status to True
                config.telegram.is_healthy = True
        except ConnectionError as ex:
            logger.error("Unable to reach the Telegram API: %s", ex)
            # set the Telegram availability status to False
            config.telegram.is_healthy = False
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while connecting to the Telegram API: %s", ex, exc_info=config.app.debug)
            # set the Telegram availability status to False
            config.telegram.is_healthy = False

        # Check Discord API status
        try:
            discord_status, is_healthy = discord__client_health.report_status(
                dcl,  config.discord.max_latency)
            if is_healthy:
                logger.debug("Discord API is healthy.")
                # set the Discord availability status to True
                config.discord.is_healthy = True
            else:
                logger.warning(discord_status)
                # set the Discord availability status to False
                config.discord.is_healthy = False
        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while connecting to the Discord API: %s", ex, exc_info=config.app.debug)
            # set the Discord availability status to False
            config.discord.is_healthy = False
        
        dispatcher.notify("healthcheck", config)
        # Sleep for the given interval and retry
        await asyncio.sleep(interval)
