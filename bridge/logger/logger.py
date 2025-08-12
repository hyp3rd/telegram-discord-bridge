"""Create a logger for the application.""" ""
import gzip
import logging
import os
import shutil
from logging import StreamHandler
from logging.handlers import RotatingFileHandler

from bridge.config import LoggerConfig

import bridge.logger.formatter as log_formatter


class GZipRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that optionally gzips old logs."""

    def __init__(self, *args, compress: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.compress = compress

    def doRollover(self) -> None:
        super().doRollover()
        if not self.compress:
            return
        for i in range(1, self.backupCount + 1):
            filename = f"{self.baseFilename}.{i}"
            if os.path.exists(filename) and not filename.endswith(".gz"):
                with open(filename, "rb") as f_in, gzip.open(
                    filename + ".gz", "wb"
                ) as f_out:
                    shutil.copyfileobj(f_in, f_out)
                os.remove(filename)


class Logger(logging.Logger):
    """Singleton logger class. It allows to create only one instance of the logger."""

    _instance = None

    def __new__(cls, *args):  # pylint: disable=unused-argument
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str):
        if not self.__dict__:
            super().__init__(name)

    def configure(self, logger_config: LoggerConfig):
        """Apply the logger's configuration."""
        level = getattr(logging, logger_config.level.upper(), None)

        if level is None:
            level = logging.INFO

        # Remove all handlers associated with the logger object.
        for logger_handler in self.handlers:
            self.removeHandler(logger_handler)

        handler = Logger.generate_handler(self.name, logger_config)

        self.addHandler(handler)

        # Clear handlers from the root logger
        logging.root.handlers = []

    @staticmethod
    def generate_handler(
        file_name: str, logger_config: LoggerConfig
    ) -> RotatingFileHandler | StreamHandler:
        """generate the handler for any external logger"""
        level = getattr(logging, logger_config.level.upper(), None)

        if level is None:
            level = logging.INFO

        formatter = log_formatter.ColourizedFormatter(
            use_colors=logger_config.console, fmt=logger_config.format
        )

        if not logger_config.console:
            handler = GZipRotatingFileHandler(
                f"{file_name}.log",
                maxBytes=logger_config.file_max_bytes,
                backupCount=logger_config.file_backup_count,
                compress=logger_config.compress,
            )
        else:
            handler = logging.StreamHandler()

        handler.setLevel(level)  # Set log level for the handler
        handler.setFormatter(formatter)
        return handler

    @staticmethod
    def get_logger(name: str) -> "Logger":
        """Get a logger for the application."""
        logger = Logger(name)
        return logger

    @staticmethod
    def get_telethon_logger() -> logging.Logger:
        """Get the Telethon logger"""
        logger = logging.getLogger("telethon")
        return logger

    @staticmethod
    def init_logger(name: str, logger_config: LoggerConfig) -> "Logger":
        """Initialize a logger for the application."""
        logger = Logger(name)
        logger.configure(logger_config)
        return logger
