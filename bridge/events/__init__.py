"""The Brigde event dispatcher."""

try:
    from .events import (EventDispatcher, EventDispatcherException,
                         EventSubscriber)
except ImportError:
    raise ImportError("Unable to import the event dispatcher.") from None
