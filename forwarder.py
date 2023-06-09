"""handles the process of the bridge between telegram and discord"""

import argparse
import asyncio
import os
import signal
import sys
from asyncio import AbstractEventLoop
from sqlite3 import OperationalError
from typing import Tuple

import discord
import psutil  # pylint: disable=import-error
from telethon import TelegramClient

from bridge.config import Config
from bridge.core import on_restored_connectivity, start
from bridge.discord_handler import start_discord
from bridge.enums import ProcessStateEnum
from bridge.events import EventDispatcher
from bridge.healtcheck_handler import healthcheck
from bridge.logger import Logger
from bridge.telegram_handler import start_telegram_client

config = Config()
logger = Logger.init_logger(config.app.name, config.logger)

# Create a Forwader class with context manager to handle the bridge process
# class Forwarder:
#     """Forwarder class."""

#     def __init__(self, loop: AbstractEventLoop, dispatcher: EventDispatcher, config: Config):
#         """Initialize the Forwarder class."""
#         self.loop = loop
#         self.dispatcher = dispatcher
#         self.config = config
#         self.telegram_client: TelegramClient
#         self.discord_client: discord.Client

#     async def __aenter__(self):
#         """Enter the context manager."""
#         # Start the Telegram client
#         self.telegram_client = await start_telegram_client(config=self.config, event_loop=self.loop)

#         # Start the Discord client
#         self.discord_client = await start_discord(self.config)

#         # Start the healthcheck
#         self.loop.create_task(healthcheck(self.dispatcher, self.telegram_client, self.discord_client))

#         # Start the bridge
#         self.loop.create_task(start(self.telegram_client, self.discord_client, self.dispatcher))

#         return self

#     async def __aexit__(self, exc_type, exc_val, exc_tb):
#         """Exit the context manager."""
#         # Stop the Telegram client
#         if self.telegram_client is not None and self.telegram_client.is_connected():
#             await self.telegram_client.disconnect()

#         # Stop the Discord client
#         await self.discord_client.close()


def create_pid_file() -> str:
    """Create a PID file."""
    logger.debug("Creating PID file.")
    # Get the process ID.
    pid = os.getpid()

    # Create the PID file.
    bot_pid_file = f'{config.app.name}.pid'
    process_state, _ = determine_process_state(bot_pid_file)

    if process_state == ProcessStateEnum.RUNNING:
        sys.exit(1)

    try:
        with open(bot_pid_file, "w", encoding="utf-8") as pid_file:
            pid_file.write(str(pid))
    except OSError as err:
        print(f"Unable to create PID file: {err}", flush=True)
        sys.exit(0)

    return bot_pid_file


def remove_pid_file(pid_file: str):
    """Remove a PID file."""
    logger.debug("Removing PID file.")
    #determine if the pid file exists
    if not os.path.isfile(pid_file):
        logger.debug("PID file '%s' not found.", pid_file)
        return

    try:
        os.remove(pid_file)
    except FileNotFoundError:
        logger.error("PID file '%s' not found.", pid_file)
    except Exception as ex:  # pylint: disable=broad-except
        logger.exception(ex)
        logger.error("Failed to remove PID file '%s'.", pid_file)


def determine_process_state(pid_file: str | None = None) -> Tuple[ProcessStateEnum, int]:
    """
    Determine the state of the process.

    The state of the process is determined by looking for the PID file. If the
    PID file does not exist, the process is considered stopped. If the PID file
    does exist, the process is considered running.

    If the PID file exists and the PID of the process that created it is not
    running, the process is considered stopped. If the PID file exists and the
    PID of the process that created it is running, the process is considered
    running.

    :param pid_file: The path to the PID file.
    :type pid_file: str
    :return: A tuple containing the process state and the PID of the process
    that created the PID file.
    :rtype: Tuple[str, int]
    """

    if pid_file is None:
        pid_file = f'{config.app.name}.pid'

    if not os.path.isfile(pid_file):
        # The PID file does not exist, so the process is considered stopped.
        return ProcessStateEnum.STOPPED, 0

    pid = 0
    try:
        # Read the PID from the PID file.
        with open(pid_file, "r", encoding="utf-8") as bot_pid_file:
            pid = int(bot_pid_file.read().strip())

            # If the PID file exists and the PID of the process that created it
            # is not running, the process is considered stopped.
            if not psutil.pid_exists(pid):
                return ProcessStateEnum.STOPPED, 0

            # If the PID file exists and the PID of the process that created it
            # is running, the process is considered running.
            return ProcessStateEnum.RUNNING, pid
    except ProcessLookupError:
        # If the PID file exists and the PID of the process that created it is
        # not running, the process is considered stopped.
        return ProcessStateEnum.ORPHANED, 0
    except PermissionError:
        # If the PID file exists and the PID of the process that created it is
        # running, the process is considered running.
        return ProcessStateEnum.RUNNING, pid
    except FileNotFoundError:
        # The PID file does not exist, so the process is considered stopped.
        return ProcessStateEnum.STOPPED, 0

def stop_bridge():
    """Stop the bridge."""
    pid_file = f'{config.app.name}.pid'

    process_state, pid = determine_process_state(pid_file)
    if process_state == ProcessStateEnum.STOPPED:
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

    # if not config.api.enabled:
    for running_task in all_tasks:
        if running_task is not task and not running_task.done() and not running_task.cancelled():
            if task is not None:
                logger.debug("Cancelling task %s...", {running_task})
                try:
                    task.cancel()
                except Exception as ex:  # pylint: disable=broad-except
                    logger.error("Error cancelling task %s: %s", {
                                running_task}, {ex})


    if not config.api.enabled:
        logger.debug("Stopping event loop...")
        asyncio.get_running_loop().stop()
    else:
        remove_pid_file(f'{config.app.name}.pid')

    logger.info("Shutdown process completed.")


async def shutdown(sig, tasks_loop: asyncio.AbstractEventLoop):
    """Shutdown the application gracefully."""
    logger.warning("shutdown received signal %s, shutting down...", {sig})

    # Cancel all tasks
    tasks = [task for task in asyncio.all_tasks(
    ) if task is not asyncio.current_task()]

    for task in tasks:
        task.cancel()

    # Wait for all tasks to be cancelled
    results = await asyncio.gather(*tasks, return_exceptions=config.app.debug)

    # Check for errors
    for result in results:
        if isinstance(result, asyncio.CancelledError):
            continue
        if isinstance(result, Exception):
            logger.error("Error during shutdown: %s", result)

    if not config.api.enabled:
        # Stop the loop
        if tasks_loop is not None:
            tasks_loop.stop()

    remove_pid_file(f'{config.app.name}.pid')


async def handle_signal(sig, tgc: TelegramClient, dcl: discord.Client, tasks):
    """Handle graceful shutdown on received signal."""
    logger.warning("Received signal %s, shutting down...", {sig})

    # Disconnect clients
    if tgc.is_connected():
        tgc.disconnect()
    if dcl.is_ready():
        await dcl.close()

    # Cancel all tasks
    await asyncio.gather(*tasks, return_exceptions=config.app.debug)


async def init_clients(dispatcher: EventDispatcher) -> Tuple[TelegramClient, discord.Client]:
    """Handle the initialization of the bridge's clients."""

    lock = asyncio.Lock()
    await lock.acquire()
    event_loop = asyncio.get_event_loop()

    telegram_client_instance = await start_telegram_client(config, event_loop)
    discord_client_instance = await start_discord(config)

    # context = {
    #     'telegram_client': telegram_client_instance,
    #     'discord_client': discord_client_instance,
    #     'dispatcher': dispatcher
    # }

    lock.release()

    # Set signal handlers for graceful shutdown on received signal (except on Windows)
    # NOTE: This is not supported on Windows
    if os.name != 'nt' and not config.api.enabled:
        for sig in (signal.SIGINT, signal.SIGTERM):
            event_loop.add_signal_handler(
                sig, lambda sig=sig: asyncio.create_task(shutdown(sig, tasks_loop=event_loop)))  # type: ignore
    if config.api.enabled:
        for sig in (signal.SIGINT, signal.SIGTERM):
            event_loop.add_signal_handler(
                sig, lambda: asyncio.create_task(on_shutdown(telegram_client_instance, discord_client_instance)))

    try:
        lock = asyncio.Lock()
        await lock.acquire()
        # Create tasks for starting the main logic and waiting for clients to disconnect
        start_task = event_loop.create_task(
            start(telegram_client_instance, discord_client_instance, config)
        )
        telegram_wait_task = event_loop.create_task(
            telegram_client_instance.run_until_disconnected()  # type: ignore
        )
        discord_wait_task = event_loop.create_task(
            discord_client_instance.wait_until_ready()
        )
        api_healthcheck_task = event_loop.create_task(
            healthcheck(dispatcher,
                        telegram_client_instance,
                        discord_client_instance, config.app.healthcheck_interval)
        )
        on_restored_connectivity_task = event_loop.create_task(
            on_restored_connectivity(
                config=config,
                telegram_client=telegram_client_instance,
                discord_client=discord_client_instance)
        )
        lock.release()

        await asyncio.gather(start_task,
                             telegram_wait_task,
                             discord_wait_task,
                             api_healthcheck_task,
                             on_restored_connectivity_task, return_exceptions=config.app.debug)


    except asyncio.CancelledError as ex:
        logger.warning(
            "CancelledError caught: %s", ex, exc_info=False)
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error while running the bridge: %s",
                     ex, exc_info=config.app.debug)
    finally:
        await on_shutdown(telegram_client_instance, discord_client_instance)

    return telegram_client_instance, discord_client_instance


def start_bridge(dispatcher: EventDispatcher):
    """Start the bridge."""

    logger.info("Starting %s...", config.app.name)

    event_loop = asyncio.get_event_loop()

    event_loop.set_debug(config.app.debug)
    # Set the exception handler.
    event_loop.set_exception_handler(event_loop_exception_handler)

    # Create a PID file.
    pid_file = create_pid_file()

    # Create a task for the main coroutine.
    main_task = event_loop.create_task(main(dispatcher=dispatcher))

    try:
        if event_loop.is_running():
            logger.warning("Event loop is already running, not starting a new one.")
            main_task.done()
        else:
            # Run the event loop.
            event_loop.run_forever()
    except KeyboardInterrupt:
        # Cancel the main task.
        main_task.cancel()
    except asyncio.CancelledError:
        pass
    except asyncio.LimitOverrunError as ex:
        logger.error(
            "The event loop has exceeded the configured limit of pending tasks: %s",
            ex, exc_info=config.app.debug)
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error while running the bridge: %s",
                     ex, exc_info=config.app.debug)
    finally:
        # Remove the PID file.
        if not config.api.enabled:
            remove_pid_file(pid_file)


def event_loop_exception_handler(event_loop: AbstractEventLoop | None, context):
    """Asyncio Event loop exception handler."""
    if event_loop is None:
        event_loop = asyncio.get_event_loop()
    try:
        exception = context.get("exception")
        if not isinstance(exception, asyncio.CancelledError):
            event_loop.default_exception_handler(context)
        else:
            # This error is expected during shutdown.
            logger.warning("CancelledError caught during shutdown")
    except Exception as ex:  # pylint: disable=broad-except
        logger.error(
            "Event loop exception handler failed: %s",
            ex,
            exc_info=config.app.debug,
        )


def daemonize_process():
    """Daemonize the process by forking and redirecting standard file descriptors."""
    # Fork the process and exit if we're the parent
    pid = os.fork()
    if pid > 0:
        sys.exit()

    # Start a new session
    os.setsid()

    # Fork again and exit if we're the parent
    pid = os.fork()
    if pid > 0:
        sys.exit()

    # Redirect standard file descriptors to /dev/null
    with open(os.devnull, "r", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


async def main(dispatcher: EventDispatcher):
    """Run the bridge."""
    clients = ()
    try:
        clients = await init_clients(dispatcher=dispatcher)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user, shutting down...")
    except asyncio.CancelledError:
        logger.warning("CancelledError caught, shutting down...")
    except RuntimeError as ex:
        logger.error("RuntimeError caught: %s", ex, exc_info=config.app.debug)
    except OperationalError as ex:
        logger.error("OperationalError caught: %s", ex, exc_info=config.app.debug)
    finally:
        if clients:
            telegram_client, discord_client = clients[0], clients[1]
            if telegram_client and not telegram_client.is_connected() and not discord_client.is_ready():
                clients = ()
            else:
                await on_shutdown(telegram_client, discord_client)
                clients = ()


async def run_controller(dispatcher: EventDispatcher | None,
                     event_loop: AbstractEventLoop | None = None,
                     boot: bool = False,
                     stop: bool = False,
                     background: bool = False):
    """Init the bridge."""
    if not config.api.enabled:
        logger.error("API mode is disabled, please use the CLI to start the bridge, or enable it in the config file.")
        if not config.logger.console:
            print("API mode is disabled, please use the CLI to start the bridge, or enable it in the config file.")
        sys.exit(1)

    if boot:
        logger.info("Booting %s...", config.app.name)
        logger.info("Version: %s", config.app.version)
        logger.info("Description: %s", config.app.description)
        logger.info("Log level: %s", config.logger.level)
        logger.info("Debug enabled: %s", config.app.debug)
        logger.info("Login through API enabled: %s",
                    config.api.telegram_login_enabled)

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

        if event_loop is None:
            try:
                event_loop = asyncio.get_event_loop()
            except RuntimeError:
                logger.warning("No event loop found, creating a new one")
                event_loop = asyncio.new_event_loop()

        asyncio.set_event_loop(event_loop)

        if dispatcher is None:
            dispatcher = EventDispatcher()

        start_bridge(dispatcher=dispatcher)
    elif stop:
        stop_bridge()
    else:
        print("Please use --start or --stop flags to start or stop the bridge.")


def controller(dispatcher: EventDispatcher | None,
                     event_loop: AbstractEventLoop | None = None,
                     boot: bool = False,
                     stop: bool = False,
                     background: bool = False):
    """Init the bridge."""
    if boot:
        logger.info("Booting %s...", config.app.name)
        logger.info("Version: %s", config.app.version)
        logger.info("Description: %s", config.app.description)
        logger.info("Log level: %s", config.logger.level)
        logger.info("Debug enabled: %s", config.app.debug)
        logger.info("Login through API enabled: %s",
                    config.api.telegram_login_enabled)

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

        if event_loop is None:
            try:
                event_loop = asyncio.get_event_loop()
            except RuntimeError:
                logger.warning("No event loop found, creating a new one")
                event_loop = asyncio.new_event_loop()

            asyncio.set_event_loop(event_loop)

        if dispatcher is None:
            dispatcher = EventDispatcher()

        start_bridge(dispatcher=dispatcher)
    elif stop:
        stop_bridge()
    else:
        print("Please use --start or --stop flags to start or stop the bridge.")


if __name__ == "__main__":
    # extra precautions to prevent the bridge from running twice
    if config.api.enabled:
        logger.error("API mode is enabled, please use the API to start the bridge, or disable it to use the CLI.")
        if not config.logger.console:
            print("API mode is enabled, please use the API to start the bridge, or disable it to use the CLI.")
        sys.exit(1)

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

    event_dispatcher = EventDispatcher()

    controller(dispatcher=event_dispatcher, event_loop=asyncio.new_event_loop() ,boot=__start, stop=__stop, background=__background)
