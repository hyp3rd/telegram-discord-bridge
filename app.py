"""handles the process of the bridge between telegram and discord"""

import argparse
import asyncio
import os
import signal
import sys
from typing import Tuple

import discord
from telethon import TelegramClient

from bridge import start
from config import Config
from discord_handler import start_discord
from healtcheck_handler import healthcheck
from logger import app_logger
from telegram_handler import start_telegram_client

logger = app_logger()


def create_pid_file() -> str:
    """Create a PID file."""
    pid = os.getpid()
    bot_pid_file = f'{config.app_name}.pid'

    process_state, _ = determine_process_state(bot_pid_file)

    if process_state == "running":
        sys.exit(1)

    with open(bot_pid_file, "w", encoding="utf-8") as pid_file:
        pid_file.write(str(pid))

    return bot_pid_file


def remove_pid_file(pid_file: str):
    """Remove a PID file."""
    if os.path.isfile(pid_file):
        os.remove(pid_file)
    else:
        logger.error("PID file '%s' not found.", pid_file)


def determine_process_state(pid_file: str) -> Tuple[str, int]:
    """Determine the state of the process."""

    if not os.path.isfile(pid_file):
        return "stopped", 0

    try:
        with open(pid_file, "r", encoding="utf-8") as bot_pid_file:
            pid = int(bot_pid_file.read().strip())
            logger.warning(
                "%s is already be running with PID %s. PID file: %s", config.app_name, pid, pid_file)
            return "running", pid
    except ProcessLookupError:
        return "stopped", 0
    except PermissionError:
        return "running", pid
    except FileNotFoundError:
        return "stopped", 0


def stop_bot():
    """Stop the bot."""
    pid_file = f'{config.app_name}.pid'

    process_state, pid = determine_process_state(pid_file)
    if process_state == "stopped":
        logger.warning(
            "PID file '%s' not found. The %s may not be running.", pid_file, config.app_name)
        return

    try:
        os.kill(pid, signal.SIGINT)
        logger.warning("Sent SIGINT to the %s process with PID %s.",
                       config.app_name, pid)
    except ProcessLookupError:
        logger.error(
            "The %s process with PID %s is not running.", config.app_name, pid)


async def on_shutdown(telegram_client, discord_client):
    """Shutdown the bot."""
    logger.info("Starting shutdown process...")
    task = asyncio.current_task()
    all_tasks = asyncio.all_tasks()

    try:
        logger.info("Disconnecting Telegram client...")
        await telegram_client.disconnect()
        logger.info("Telegram client disconnected.")
    except (Exception, asyncio.CancelledError) as ex:  # pylint: disable=broad-except
        logger.error("Error disconnecting Telegram client: %s", {ex})

    try:
        logger.info("Disconnecting Discord client...")
        await discord_client.close()
        logger.info("Discord client disconnected.")
    except (Exception, asyncio.CancelledError) as ex:  # pylint: disable=broad-except
        logger.error("Error disconnecting Discord client: %s", {ex})

    for running_task in all_tasks:
        if running_task is not task:
            task.cancel()

    logger.info("Shutdown process completed.")


async def shutdown(sig, tasks_loop: None):
    """Shutdown the application gracefully."""
    logger.warning("shutdown received signal %s, shutting down...", {sig})

    tasks = [task for task in asyncio.all_tasks(
    ) if task is not asyncio.current_task()]

    for task in tasks:
        task.cancel()

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, asyncio.CancelledError):
            continue
        if isinstance(result, Exception):
            logger.error("Error during shutdown: %s", result)

    if tasks_loop is not None:
        tasks_loop.stop()


async def handle_signal(sig, tgc: TelegramClient, dcl: discord.Client, tasks):
    """Handle graceful shutdown on received signal."""
    logger.warning("Received signal %s, shutting down...", {sig})

    # Disconnect clients
    if tgc.is_connected():
        await tgc.disconnect()
    if dcl.is_ready():
        await dcl.close()

    # Cancel all tasks
    await asyncio.gather(*tasks, return_exceptions=True)


async def init_clients() -> Tuple[TelegramClient, discord.Client]:
    """Handle the initialization of the bot's clients."""
    telegram_client_instance = await start_telegram_client(config)
    discord_client_instance = await start_discord(config)

    event_loop = asyncio.get_event_loop()

    # Set signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        event_loop.add_signal_handler(
            sig, lambda sig=sig: asyncio.create_task(shutdown(sig, tasks_loop=event_loop)))

    try:
        # Create tasks for starting the main logic and waiting for clients to disconnect
        start_task = asyncio.create_task(
            start(telegram_client_instance, discord_client_instance, config)
        )
        telegram_wait_task = asyncio.create_task(
            telegram_client_instance.run_until_disconnected()
        )
        discord_wait_task = asyncio.create_task(
            discord_client_instance.wait_until_ready()
        )
        api_healthcheck_task = asyncio.create_task(
            healthcheck(telegram_client_instance, discord_client_instance)
        )

        await asyncio.gather(start_task, telegram_wait_task, discord_wait_task, api_healthcheck_task)
    except asyncio.CancelledError:
        logger.warning("CancelledError caught, shutting down...")
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error while running the bot: %s", ex)
    finally:
        await on_shutdown(telegram_client_instance, discord_client_instance)

    return telegram_client_instance, discord_client_instance


def start_bot():
    """Start the bot."""
    loop.set_exception_handler(event_loop_exception_handler)

    pid_file = create_pid_file()

    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
    finally:
        remove_pid_file(pid_file)


def event_loop_exception_handler(context):
    """Asyncio Event loop exception handler."""
    exception = context.get("exception")
    if not isinstance(exception, asyncio.CancelledError):
        loop.default_exception_handler(context)
    else:
        loop.warning("CancelledError caught during shutdown")


async def main():
    """Run the bot."""
    clients = ()
    try:
        clients = await init_clients()
    except KeyboardInterrupt:
        logger.warning("Interrupted by user, shutting down...")
    except asyncio.CancelledError:
        logger.warning("CancelledError caught, shutting down...")
    finally:
        if clients:
            telegram_client, discord_client = clients[0], clients[1]
            if not telegram_client.is_connected() and not discord_client.is_ready():
                clients = ()
            else:
                await on_shutdown(telegram_client, discord_client)
                clients = ()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process handler for the bot.")
    parser.add_argument("--start", action="store_true", help="Start the bot.")
    parser.add_argument("--stop", action="store_true", help="Stop the bot.")

    args = parser.parse_args()

    config = Config()

    if args.start:
        loop = asyncio.get_event_loop()
        start_bot()
    elif args.stop:
        stop_bot()
    else:
        print("Please use --start or --stop flags to start or stop the bot.")
