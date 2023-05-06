"""Initialize the history handler module."""

try:
    from .history import MessageHistoryHandler
except ImportError as ex:
    raise ex
