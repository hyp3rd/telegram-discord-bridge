"""handles the process of the bridge between telegram and discord"""

import argparse
import asyncio
import os
import signal
import sys
from asyncio import AbstractEventLoop
from typing import Tuple

import discord
from telethon import TelegramClient

from bridge.config import Config
from bridge.core import on_restored_connectivity, start
from bridge.discord_handler import start_discord
from bridge.healtcheck_handler import healthcheck
from bridge.logger import Logger
from bridge.telegram_handler import start_telegram_client

config = Config()
logger = Logger.init_logger(config.app.name, config.logger)


def create_pid_file() -> str:
    """Create a PID file."""
    pid = os.getpid()
    bot_pid_file = f'{config.app.name}.pid'

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

    pid = 0
    try:
        with open(pid_file, "r", encoding="utf-8") as bot_pid_file:
            pid = int(bot_pid_file.read().strip())
            logger.warning(
                "%s is already be running with PID %s. PID file: %s", config.app.name, pid, pid_file)
            return "running", pid
    except ProcessLookupError:
        return "stopped", 0
    except PermissionError:
        return "running", pid
    except FileNotFoundError:
        return "stopped", 0


def stop_bridge():
    """Stop the bridge."""
    pid_file = f'{config.app.name}.pid'

    process_state, pid = determine_process_state(pid_file)
    if process_state == "stopped":
        logger.warning(
            "PID file '%s' not found. The %s may not be running.", pid_file, config.app.name)
        return

    try:
        os.kill(pid, signal.SIGINT)
        logger.warning("Sent SIGINT to the %s process with PID %s.",
                       config.app.name, pid)
    except ProcessLookupError:
        logger.error(
            "The %s process with PID %s is not running.", config.app.name, pid)


async def on_shutdown(telegram_client, discord_client):
    """Shutdown the bridge."""
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
            if task is not None:
                logger.debug("Cancelling task %s...", {running_task})
                task.cancel()

    logger.debug("Stopping event loop...")
    asyncio.get_event_loop().stop()
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
        # await tgc.disconnect()
        tgc.disconnect()
    if dcl.is_ready():
        await dcl.close()

    # Cancel all tasks
    await asyncio.gather(*tasks, return_exceptions=True)


async def init_clients() -> Tuple[TelegramClient, discord.Client]:
    """Handle the initialization of the bridge's clients."""
    telegram_client_instance = await start_telegram_client(config)
    discord_client_instance = await start_discord(config)

    event_loop = asyncio.get_event_loop()

    # Set signal handlers for graceful shutdown on received signal (except on Windows)
    # NOTE: This is not supported on Windows
    if os.name != 'nt':
        for sig in (signal.SIGINT, signal.SIGTERM):
            event_loop.add_signal_handler(
                sig, lambda sig=sig: asyncio.create_task(shutdown(sig, tasks_loop=event_loop)))  # type: ignore

    try:
        # Create tasks for starting the main logic and waiting for clients to disconnect
        start_task = asyncio.create_task(
            start(telegram_client_instance, discord_client_instance, config)
        )
        telegram_wait_task = asyncio.create_task(
            telegram_client_instance.run_until_disconnected()  # type: ignore
        )
        discord_wait_task = asyncio.create_task(
            discord_client_instance.wait_until_ready()
        )
        api_healthcheck_task = asyncio.create_task(
            healthcheck(telegram_client_instance,
                        discord_client_instance, config.app.healthcheck_interval)
        )
        on_restored_connectivity_task = asyncio.create_task(
            on_restored_connectivity(
                config=config,
                telegram_client=telegram_client_instance,
                discord_client=discord_client_instance)
        )

        await asyncio.gather(start_task,
                             telegram_wait_task,
                             discord_wait_task,
                             api_healthcheck_task,
                             on_restored_connectivity_task)

    except asyncio.CancelledError:
        logger.warning("CancelledError caught, shutting down...")
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error while running the bridge: %s", ex)
    finally:
        await on_shutdown(telegram_client_instance, discord_client_instance)

    return telegram_client_instance, discord_client_instance


def start_bridge(event_loop: AbstractEventLoop):
    """Start the bridge."""

    # Set the exception handler.
    event_loop.set_exception_handler(event_loop_exception_handler)

    # Create a PID file.
    pid_file = create_pid_file()

    try:
        # Start the bridge.
        event_loop.run_until_complete(main())
        # event_loop.run_forever()
    except asyncio.CancelledError:
        pass
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error while running the bridge: %s", ex)
    finally:
        # Remove the PID file.
        remove_pid_file(pid_file)


def event_loop_exception_handler(event_loop: AbstractEventLoop, context):
    """Asyncio Event loop exception handler."""
    exception = context.get("exception")
    if not isinstance(exception, asyncio.CancelledError):
        event_loop.default_exception_handler(context)
    else:
        logger.warning("CancelledError caught during shutdown")


def daemonize_process():
    """Daemonize the process by forking and redirecting standard file descriptors."""
    pid = os.fork()
    if pid > 0:
        sys.exit()

    os.setsid()

    # Fork again to avoid re-acquiring a controlling terminal
    pid = os.fork()
    if pid > 0:
        sys.exit()

    # Redirect standard file descriptors to /dev/null
    with open(os.devnull, "r", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


async def main():
    """Run the bridge."""
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


def controller(boot: bool, stop: bool, background: bool):
    """Init the bridge."""
    if boot:
        logger.info("%s is starting", config.app.name)
        logger.info("Version: %s", config.app.version)
        logger.info("Description: %s", config.app.description)
        logger.info("Log level: %s", config.logger.level)
        logger.info("Debug enabled: %s", config.app.debug)

        if background:
            logger.info("Running %s in the background", config.app.name)
            if os.name != "posix":
                logger.error(
                    "Background mode is only supported on POSIX systems")
                sys.exit(1)

            if config.logger.console is True:
                logger.error(
                    "Background mode requires console logging to be disabled")
                sys.exit(1)

            logger.info("Starting %s in the background...", config.app.name)
            daemonize_process()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start_bridge(loop)
    elif stop:
        stop_bridge()
    else:
        print("Please use --start or --stop flags to start or stop the bridge.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process handler for the bridge.")
    parser.add_argument("--start", action="store_true",
                        help="Start the bridge.")

    parser.add_argument("--stop", action="store_true", help="Stop the bridge.")

    parser.add_argument("--background", action="store_true",
                        help="Run the bridge in the background (forked).")

    parser.add_argument("--version", action="store_true",
                        help="Get the Bridge version.")

    cmd_args = parser.parse_args()

    if cmd_args.version:
        print(f'The Bridge\nv{config.app.version}')
        sys.exit(0)

    __start: bool = cmd_args.start
    __stop: bool = cmd_args.stop
    __background: bool = cmd_args.background

    controller(__start, __stop, __background)
