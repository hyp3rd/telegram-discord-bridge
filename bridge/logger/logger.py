"""Create a logger for the application."""""
import logging
from logging.handlers import RotatingFileHandler
from logging import StreamHandler
from typing import Any
from bridge.config import LoggerConfig


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

        handler = Logger.generate_handler(self.name, logger_config)

        # Remove all handlers associated with the logger object.
        for logger_handler in self.handlers:
            self.removeHandler(logger_handler)

        self.addHandler(handler)

        # Clear handlers from the root logger
        logging.root.handlers = []

    @staticmethod
    def generate_handler(file_name: str, logger_config: LoggerConfig) -> RotatingFileHandler | StreamHandler:
        """generate the handler for any external logger"""
        level = getattr(logging, logger_config.level.upper(), None)

        if level is None:
            level = logging.INFO

        formatter = logging.Formatter(
            f'{logger_config.format}')

        if not logger_config.console:
            # The log files will rotate when they reach 10 MB in size.
            # The backupCount parameter is set to 5,
            # which means that up to 5 backup files will be kept.
            handler = RotatingFileHandler(
                f'{file_name}.log',
                maxBytes=logger_config.file_max_bytes,
                backupCount=logger_config.file_backup_count)
        else:
            handler = logging.StreamHandler()

        handler.setLevel(level)  # Set log level for the handler
        handler.setFormatter(formatter)
        return handler

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get a logger for the application."""
        logger = Logger(name)
        return logger

    @staticmethod
    def get_telethon_logger() -> logging.Logger:
        """Get the Telethon logger"""
        logger = logging.getLogger('telethon')
        return logger

    @staticmethod
    def init_logger(name: str, logger_config: LoggerConfig) -> logging.Logger:
        """Initialize a logger for the application."""
        logger = Logger(name)
        logger.configure(logger_config)
        return logger
