"""Create a logger for the application."""""
import logging


def app_logger() -> logging.Logger:
    """Create a logger for the application."""
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logging.getLogger('telethon').setLevel(level=logging.WARNING)
    logger = logging.getLogger(__name__)
    return logger
