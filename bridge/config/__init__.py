"""Initialize the config module."""

try:
    from .config import Config, LoggerConfig
except ImportError as ex:
    raise ex
