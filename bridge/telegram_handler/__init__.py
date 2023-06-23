"""Initialize the telegram_handler module."""

try:
    from .core import check_telegram_session, start_telegram_client
except ImportError as ex:
    raise ex
