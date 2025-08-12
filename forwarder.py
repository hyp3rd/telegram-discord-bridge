"""Forwarder is holds the bridge between telegram and discord"""

import argparse
import asyncio
import os
import signal
import sys
from asyncio import AbstractEventLoop
from sqlite3 import OperationalError
from typing import Tuple, TypeAlias

import discord
from telethon import TelegramClient

from bridge.config import Config
from bridge.core import Bridge
from bridge.discord import DiscordHandler
from bridge.enums import ProcessStateEnum
from bridge.events import EventDispatcher
from bridge.healthcheck import HealthHandler
from bridge.logger import Logger
from bridge.release import __version__
from bridge.telegram import TelegramHandler
from bridge.pid import PidManager, PidFileError
from core import SingletonMeta

ERR_API_DISABLED = "API mode is disabled, please use the CLI to start the bridge, or enable it in the config file."
ERR_API_ENABLED = "API mode is enabled, please use the API to start the bridge, or disable it in the config file."

# This is the type that the process runs. It returns a tuple containing
# a ProcessStateEnum and a string.
OperationStatus: TypeAlias = Tuple[ProcessStateEnum, str]

config = Config.get_instance()

# A list of tasks that should be cancelled on shutdown fron API
forwarder_tasks = [
    "forwarder_task",
    "shutdown_task",
    "on_shutdown_task",
    "bridge_start_task",
    "telegram_wait_task",
    "discord_wait_task",
    "api_healthcheck_task",
    "on_restored_connectivity_task",
]


class Forwarder(metaclass=SingletonMeta):
    """The forwarder class."""

    dispatcher: EventDispatcher
    event_loop: AbstractEventLoop
    is_background: bool
    telegram_client: TelegramClient
    discord_client: discord.Client
    logger: Logger
    pid_manager: PidManager

    def __init__(
        self, event_loop: AbstractEventLoop | None = None, is_background: bool = False
    ):
        """Initialize the forwarder."""

        self.logger = Logger.init_logger(config.application.name, config.logger)

        self.logger.info("Initializing the forwarder %s", config.application.name)
        self.dispatcher = EventDispatcher()

        self.event_loop = event_loop or asyncio.new_event_loop()
        # configure the event loop
        self.event_loop.set_debug(config.application.debug)
        self.event_loop.set_exception_handler(self.__event_loop_exception_handler)

        self.is_background = is_background

        self.pid_manager = PidManager(self.logger)
        self.logger.debug("Forwarder initialized.")

    def determine_process_state(self) -> Tuple[ProcessStateEnum, int]:
        """Proxy to the PID manager's process state check."""
        return self.pid_manager.determine_process_state()

    async def api_controller(self, start_forwarding: bool = True) -> OperationStatus:
        """Run the forwarder from the API controller."""
        self.logger.debug("API controller invoked.")

        if not config.api.enabled:
            self.logger.error(ERR_API_DISABLED)
            if not config.logger.console:
                print(ERR_API_DISABLED)
            return ProcessStateEnum.FAILED, ERR_API_DISABLED

        self.__controller(start_forwarding)

        status = (
            ProcessStateEnum.STARTING if start_forwarding else ProcessStateEnum.STOPPING
        )
        msg = f"The bridge {config.application.name} with config v{config.application.version}"
        msg = f"{msg} is starting" if start_forwarding else f"{msg} is stopping"

        return status, msg

    def cli_controller(self, start_forwarding: bool = True):
        """Run the forwarder from the CLI controller."""
        self.logger.debug("Starting the CLI controller.")

        if config.api.enabled:
            self.logger.error(ERR_API_ENABLED)
            if not config.logger.console:
                print(ERR_API_ENABLED)
            sys.exit(1)

        self.__controller(start_forwarding)

    def __controller(self, start_forwarding: bool = True):
        if start_forwarding:
            self.logger.info("Booting %s...", config.application.name)
            self.logger.info("Version: %s", config.application.version)
            self.logger.info("Description: %s", config.application.description)
            self.logger.info("Log level: %s", config.logger.level)
            self.logger.info(
                "Anti-Spam enabled: %s", config.application.anti_spam_enabled
            )
            self.logger.info("Debug enabled: %s", config.application.debug)
            self.logger.info("API enabled: %s", config.api.enabled)
            self.logger.info(
                "Login through API enabled: %s", config.api.telegram_login_enabled
            )

            if self.event_loop is None:
                try:
                    self.event_loop = asyncio.get_event_loop()
                except RuntimeError:
                    self.logger.warning("No event loop found, creating a new one.")
                    self.event_loop = asyncio.new_event_loop()

            asyncio.set_event_loop(self.event_loop)

            if self.dispatcher is None:
                self.dispatcher = EventDispatcher()

            self.__start()
            return
        # stop the bridge if start is false
        self.__stop()

    def __event_loop_exception_handler(
        self, event_loop: AbstractEventLoop | None, context: dict
    ):
        """Asyncio Event loop exception handler."""
        if not event_loop:
            event_loop = self.event_loop
        try:
            exception = context.get("exception")
            if not isinstance(exception, asyncio.CancelledError):
                event_loop.default_exception_handler(context)
            else:
                # This error is expected during shutdown.
                self.logger.warning("CancelledError caught during shutdown")
        except Exception as ex:  # pylint: disable=broad-except
            self.logger.error(
                "Event loop exception handler failed: %s",
                ex,
                exc_info=config.application.debug,
            )

    async def __forwarder_task(self):
        clients = ()
        try:
            clients = await self.init_clients()
        except KeyboardInterrupt:
            self.logger.warning("Interrupted by user, shutting down...")
        except asyncio.CancelledError:
            self.logger.warning("CancelledError caught, shutting down...")
        except RuntimeError as ex:
            self.logger.error(
                "RuntimeError caught: %s", ex, exc_info=config.application.debug
            )
        except OperationalError as ex:
            self.logger.error(
                "OperationalError caught: %s", ex, exc_info=config.application.debug
            )
        finally:
            if clients:
                telegram_client, discord_client = clients[0], clients[1]
                if (
                    telegram_client
                    and not telegram_client.is_connected()
                    and not discord_client.is_ready()
                ):
                    clients = ()

    def __start(self):
        """Start the bridge."""
        self.logger.info("Starting the bridge.")

        if self.is_background:
            self.logger.info("Starting %s in the background", config.application.name)

            if os.name == "nt":
                self.logger.warning(
                    "Running %s in the background is not supported on Windows.",
                    config.application.name,
                )
                sys.exit(1)
            if config.logger.console:
                self.logger.error(
                    "Background mode requires console logging to be disabled"
                )
                sys.exit(1)

        # Create a PID file.
        try:
            _ = self.pid_manager.create_pid_file()
        except PidFileError as ex:
            self.logger.error("PID file error: %s", ex)
            sys.exit(1)

        # Create a task for the __forwarder coroutine.
        __forwarder_task = self.event_loop.create_task(
            self.__forwarder_task(), name="forwarder_task"
        )

        try:
            if self.event_loop.is_running():
                self.logger.warning(
                    "Event loop is already running, not starting a new one."
                )
                __forwarder_task.done()
            else:
                # Run the event loop.
                self.event_loop.run_forever()
        except KeyboardInterrupt:
            # Cancel the main task.
            __forwarder_task.cancel()
        except asyncio.CancelledError:
            pass
        except asyncio.LimitOverrunError as ex:
            self.logger.error(
                "The event loop has exceeded the configured limit of pending tasks: %s",
                ex,
                exc_info=config.application.debug,
            )
        except Exception as ex:  # pylint: disable=broad-except
            self.logger.error(
                "Error while running the bridge: %s",
                ex,
                exc_info=config.application.debug,
            )

    def __stop(self):
        """Stop the bridge."""
        self.logger.info("Stopping the %s...", config.application.name)

        process_state, pid = self.pid_manager.determine_process_state()
        if process_state == ProcessStateEnum.STOPPED:
            self.logger.warning(
                "PID file not found. The %s may not be running.",
                config.application.name,
            )
            return

        try:
            self.logger.info("Stopping the %s...", config.application.name)
            os.kill(pid, signal.SIGINT)

            self.logger.warning(
                "Sent SIGINT to the %s process with PID %s.",
                config.application.name,
                pid,
            )

        except ProcessLookupError:
            self.logger.error(
                "The %s process with PID %s is not running.",
                config.application.name,
                pid,
            )

    async def init_clients(self) -> Tuple[TelegramClient, discord.Client]:
        """Handle the initialization of the bridge's clients."""

        event_loop = asyncio.get_event_loop()

        self.telegram_client = await TelegramHandler(self.dispatcher).init_client(
            event_loop
        )
        self.discord_client = await DiscordHandler().init_client()

        # Set signal handlers for graceful shutdown on received signal (except on Windows)
        # NOTE: This is not supported on Windows
        if os.name != "nt" and not config.api.enabled:
            for sig in (signal.SIGINT, signal.SIGTERM):
                event_loop.add_signal_handler(
                    sig,
                    lambda sig=sig: asyncio.create_task(
                        self.shutdown(sig), name="shutdown_task"
                    ),
                )  # type: ignore
        if config.api.enabled:
            for sig in (signal.SIGINT, signal.SIGTERM):
                event_loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(
                        self.api_shutdown(), name="on_shutdown_task"
                    ),
                )

        try:
            lock = asyncio.Lock()
            await lock.acquire()
            bridge = Bridge(self.telegram_client, self.discord_client)
            # Create tasks for starting the main logic and waiting for clients to disconnect
            start_task = event_loop.create_task(
                bridge.start(), name="bridge_start_task"
            )
            telegram_wait_task = event_loop.create_task(
                self.telegram_client.run_until_disconnected(), name="telegram_wait_task"  # type: ignore
            )
            discord_wait_task = event_loop.create_task(
                self.discord_client.wait_until_ready(), name="discord_wait_task"
            )
            api_healthcheck_task = event_loop.create_task(
                HealthHandler(
                    self.dispatcher, self.telegram_client, self.discord_client
                ).check(config.application.healthcheck_interval),
                name="api_healthcheck_task",
            )
            on_restored_connectivity_task = event_loop.create_task(
                bridge.on_restored_connectivity(), name="on_restored_connectivity_task"
            )
            lock.release()

            await asyncio.gather(
                start_task,
                telegram_wait_task,
                discord_wait_task,
                api_healthcheck_task,
                on_restored_connectivity_task,
                return_exceptions=config.application.debug,
            )

        except asyncio.CancelledError as ex:
            self.logger.warning("CancelledError caught: %s", ex, exc_info=False)
        except Exception as ex:  # pylint: disable=broad-except
            self.logger.error(
                "Error while running the bridge: %s",
                ex,
                exc_info=config.application.debug,
            )

        return self.telegram_client, self.discord_client

    async def api_shutdown(self):
        """Shutdown the bridge."""
        self.logger.info("Starting shutdown process...")
        task = asyncio.current_task()
        all_tasks = asyncio.all_tasks(self.event_loop)

        try:
            self.logger.info("Disconnecting Telegram client...")
            await self.telegram_client.disconnect()  # type: ignore
            self.logger.info("Telegram client disconnected.")
        except (  # pylint: disable=broad-exception-caught
            Exception,
            asyncio.CancelledError,
        ) as ex:
            self.logger.error("Error disconnecting Telegram client: %s", {ex})

        try:
            self.logger.info("Disconnecting Discord client...")
            await self.discord_client.close()
            self.logger.info("Discord client disconnected.")
        # pylint: disable=broad-except
        except (
            Exception,
            asyncio.CancelledError,
        ) as ex:  # pylint: disable=broad-except
            self.logger.error("Error disconnecting Discord client: %s", {ex})

        # if not config.api.enabled:
        for running_task in all_tasks:
            if (
                running_task is not task
                and not running_task.done()
                and not running_task.cancelled()
            ):
                if (
                    running_task is not None
                    and running_task.get_name() in forwarder_tasks
                ):
                    self.logger.debug(
                        "Cancelling task %s...", {running_task.get_name()}
                    )
                    try:
                        running_task.cancel()
                    except Exception as ex:  # pylint: disable=broad-except
                        self.logger.error(
                            "Error cancelling task %s: %s", {running_task}, {ex}
                        )

        self.pid_manager.remove_pid_file()
        self.logger.info("Shutdown process completed.")

    async def shutdown(self, sig):
        """Shutdown the application gracefully."""
        self.logger.warning("Shutdown received signal %s, shutting down...", {sig})

        # Cancel all tasks
        tasks = [
            task for task in asyncio.all_tasks() if task is not asyncio.current_task()
        ]

        for task in tasks:
            task.cancel()

        # Wait for all tasks to be cancelled
        results = await asyncio.gather(
            *tasks, return_exceptions=config.application.debug
        )

        # Check for errors
        for result in results:
            if isinstance(result, asyncio.CancelledError):
                continue
            if isinstance(result, Exception):
                self.logger.error("Error during shutdown: %s", result)

        # if not config.api.enabled:
        # Stop the loop
        if self.event_loop is not None:
            self.event_loop.stop()

        self.pid_manager.remove_pid_file()


def daemonize_process():
    """Daemonize the process by forking and redirecting standard file descriptors."""
    try:
        # Fork the process and exit if we're the parent
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit()
    except OSError as ex:
        print("fork #1 failed: %s (%s)", ex.errno, ex.strerror)
        sys.exit(1)

    # decouple from parent environment
    os.chdir(os.getcwd())
    os.setsid()

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as ex:
        print("fork #2 failed: %s (%s)", ex.errno, ex.strerror)
        sys.exit(1)

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    sys.stdin.flush()

    # Redirect standard file descriptors to /dev/null
    with open(os.devnull, "r", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open(os.devnull, "a+", encoding="utf-8") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process handler for the bridge.")
    parser.add_argument("--start", action="store_true", help="Start the bridge.")

    parser.add_argument("--stop", action="store_false", help="Stop the bridge.")
    parser.add_argument(
        "--version", action="store_true", help="Output The Bridghe Version."
    )

    parser.add_argument(
        "--background",
        action="store_true",
        help="Run the bridge in the background (forked).",
    )

    cmd_args = parser.parse_args()

    __start: bool = cmd_args.start
    __stop: bool = cmd_args.stop
    __background: bool = cmd_args.background
    __version: bool = cmd_args.version

    if __version:
        print(__version__)
        sys.exit(0)

    if __background:
        daemonize_process()

    shoud_start: bool = __start or __stop

    forwarder = Forwarder(asyncio.new_event_loop(), __background)

    forwarder.cli_controller(start_forwarding=shoud_start)
