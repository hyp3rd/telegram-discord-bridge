"""PID file utilities for the forwarder."""

from __future__ import annotations

import os
from typing import Tuple

import psutil  # pylint: disable=import-error

from bridge.config import Config
from bridge.enums import ProcessStateEnum
from bridge.logger import Logger
from core import SingletonMeta


class PidFileError(Exception):
    """Custom error for PID file operations."""


class PidManager(metaclass=SingletonMeta):
    """Manage creation and removal of PID files."""

    def __init__(self, logger: Logger | None = None) -> None:
        self.config = Config.get_instance()
        self.logger = logger or Logger.get_logger(self.config.application.name)

    def create_pid_file(self) -> str:
        """Create a PID file for the running process."""
        pid = os.getpid()
        pid_file = f"{self.config.application.name}.pid"
        state, _ = self.determine_process_state(pid_file)
        if state == ProcessStateEnum.RUNNING:
            raise PidFileError(f"{self.config.application.name} is already running")
        try:
            with open(pid_file, "w", encoding="utf-8") as handle:
                handle.write(str(pid))
        except OSError as err:
            self.logger.error("Unable to create PID file: %s", err)
            raise PidFileError(err.strerror) from err
        return pid_file

    def remove_pid_file(self, pid_file: str | None = None) -> None:
        """Remove the PID file if it exists."""
        pid_file = pid_file or f"{self.config.application.name}.pid"
        try:
            os.remove(pid_file)
        except FileNotFoundError:
            self.logger.debug("PID file '%s' not found.", pid_file)
        except OSError as err:
            self.logger.error("Failed to remove PID file '%s': %s", pid_file, err)
            raise PidFileError(err.strerror) from err

    def determine_process_state(
        self, pid_file: str | None = None
    ) -> Tuple[ProcessStateEnum, int]:
        """Determine process state using the PID file."""
        pid_file = pid_file or f"{self.config.application.name}.pid"
        if not os.path.isfile(pid_file):
            return ProcessStateEnum.STOPPED, 0
        try:
            with open(pid_file, "r", encoding="utf-8") as handle:
                pid = int(handle.read().strip())
            if not psutil.pid_exists(pid):
                return ProcessStateEnum.STOPPED, 0
            return ProcessStateEnum.RUNNING, pid
        except FileNotFoundError:
            return ProcessStateEnum.STOPPED, 0
        except ProcessLookupError:
            return ProcessStateEnum.ORPHANED, 0
        except PermissionError:
            return ProcessStateEnum.RUNNING, 0
        except OSError as err:
            self.logger.error("Failed to determine process state: %s", err)
            raise PidFileError(err.strerror) from err
