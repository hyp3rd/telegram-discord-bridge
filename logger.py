"""Create a logger for the application."""""
import logging
from logging.handlers import RotatingFileHandler


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
            logging.getLogger('telethon').setLevel(level=logging.WARNING)

    def configure(self, log_level: str, log_to_file: bool):
        """Apply the logger's configuration."""
        level = getattr(logging, log_level.upper(), logging.INFO)
        self.setLevel(level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        if log_to_file:
            # The log files will rotate when they reach 10 MB in size.
            # The backupCount parameter is set to 5, which means that up to 5 backup files will be kept.
            handler = RotatingFileHandler(
                "hyp3rbridg3.log", maxBytes=10 * 1024 * 1024, backupCount=5)
        else:
            handler = logging.StreamHandler()

        handler.setFormatter(formatter)
        self.addHandler(handler)


def init_logger(log_level: str, log_to_file: bool):
    """Initialize the logger for the application."""
    logger = Logger("hyp3rbridg3")
    logger.configure(log_level, log_to_file)


def app_logger() -> Logger:
    """Create a logger for the application."""
    logger = Logger("hyp3rbridg3")
    return logger
