"""Initialize the telegram_handler module."""

try:
    from .core import TelegramHandler
except ImportError as ex:
    raise ex
