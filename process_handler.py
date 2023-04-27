"""handles the process of the program"""

import argparse
import os
import signal
import sys
from typing import Tuple

from config import Config
from logger import app_logger

logger = app_logger()
config = Config()


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


def main():
    """Process handler for the bot."""
    parser = argparse.ArgumentParser(
        description=f'Process handler for the {config.app_name}.')
    parser.add_argument("--start", action="store_true",
                        help=f'Start {config.app_name}.')
    parser.add_argument("--stop", action="store_true",
                        help=f'Stop {config.app_name}.')

    args = parser.parse_args()

    if args.start:
        logger.warning("start not implemented yet")
        sys.exit(1)
    elif args.stop:
        stop_bot()
    else:
        print(
            f'Please use --start or --stop flags to start or stop the {config.app_name}.')


if __name__ == "__main__":
    main()
