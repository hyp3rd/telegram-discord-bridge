"""Initialize the config module."""

try:
    from .config import Config, ForwarderConfig, LoggerConfig
except ImportError as ex:
    raise ex
