"""Create a logger for the application."""""
import logging


class SingletonLogger(logging.Logger):
    """Singleton logger class. It allows to create only one instance of the logger."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, name: str, level: int = logging.INFO):
        if not self.__dict__:
            super().__init__(name, level)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.addHandler(handler)
            logging.getLogger('telethon').setLevel(level=logging.WARNING)


def app_logger() -> SingletonLogger:
    """Create a logger for the application."""
    logger = SingletonLogger("hyp3rbridg3")
    return logger
