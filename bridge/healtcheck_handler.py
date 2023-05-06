"""Handler for healthchecks"""

import asyncio
import socket
from concurrent.futures import ThreadPoolExecutor

import discord
from telethon import TelegramClient

from bridge.config import Config
from bridge.logger import Logger

config = Config()
logger = Logger.get_logger(config.app.name)

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


async def healthcheck(tgc: TelegramClient, dcl: discord.Client, interval: int = 30):
    """Check the health of the Discord and Telegram APIs periodically."""
    # Check for internet connectivity
    try:
        has_connectivity = await internet_connectivity_check()
        if has_connectivity:
            logger.debug("The bridge is online.")
            # set the internet connectivity status to True
            config.status["internet_connected"] = True
        else:
            logger.error("Unable to reach the internet.")
            # set the internet connectivity status to False
            config.status["internet_connected"] = False
            await asyncio.sleep(interval)
            await healthcheck(tgc, dcl, interval)

    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            "An error occurred while checking internet connectivity: %s", ex)

    # Check Telegram API status
    try:
        if tgc.is_connected():
            await tgc.get_me()
            logger.debug("Telegram API is healthy.")
            # set the Telegram availability status to True
            config.status["telegram_available"] = True
    except ConnectionError as ex:
        logger.error("Unable to reach the Telegram API: %s", ex)
        # set the Telegram availability status to False
        config.status["telegram_available"] = False
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            "An error occurred while connecting to the Telegram API: %s", ex)
        # set the Telegram availability status to False
        config.status["telegram_available"] = False

    # Check Discord API status
    try:
        if dcl.is_ready():
            await dcl.fetch_user(dcl.user.id)
            logger.debug("Discord API is healthy.")
            # set the Discord availability status to True
            config.status["discord_available"] = True
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            "An error occurred while connecting to the Discord API: %s", ex)
        # set the Discord availability status to False
        config.status["discord_available"] = False

    # Sleep for the given interval and retry
    await asyncio.sleep(interval)
    await healthcheck(tgc, dcl, interval)
