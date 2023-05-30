"""Event dispatcher for the bridge."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List

from bridge.config import Config
from bridge.logger import Logger

logger = Logger.get_logger(Config.get_config_instance().app.name)


class EventDispatcher:
    """Event dispatcher class."""

    def __init__(self, subscribers=None):
        # a list of subscribers
        self.subscribers: List[EventSubscriber] = subscribers or []

    def add_subscriber(self, subscriber):
        """Add a subscriber to the event dispatcher."""
        if subscriber not in self.subscribers:
            self.subscribers.append(subscriber)
        logger.info("Subscriber added: %s", subscriber)

    def remove_subscriber(self, subscriber):
        """Remove a subscriber from the event dispatcher."""
        if subscriber in self.subscribers:
            self.subscribers.remove(subscriber)
        logger.info("Subscriber removed: %s", subscriber)

    def notify(self, event, data=None):
        """Notify subscribers of an event."""
        logger.debug("Event dispatcher notified of event: %s - data: %s", event, data)
        for subscriber in self.subscribers:
            logger.debug("Event dispatcher notifying subscriber: %s", subscriber)
            try:
                subscriber.update(event, data)
            except EventDispatcherException as ex:
                message = "The event dispatcher failed to notify its subscribers"
                logger.error("%s - event: %s",  message, event)
                raise EventDispatcherException(message=message) from ex

class EventDispatcherException(Exception):
    """Event dispatcher exception class."""

    def __init__(self, message):
        """Initialize the event dispatcher exception.
        
        Args:
            message: The message of the event dispatcher exception.
        """
        super().__init__(message)
        self.message = message

    def __str__(self):
        """Return the string representation of the event dispatcher exception."""
        return self.message

    def __iter__(self):
        """Return the iterator for the event dispatcher exception."""
        return iter(self.message)

    def __eq__(self, other):
        """Return whether this event dispatcher exception is equal to another object.
        
        Args:
            other: The other object.
        """
        if not isinstance(other, EventDispatcherException):
            return False
        return self.message == other.message

    def __ne__(self, other):
        """Return whether this event dispatcher exception is not equal to another object.
        
        Args:
            other: The other object.
        """
        return not self.__eq__(other)

    def __hash__(self):
        """Return the hash of this event dispatcher exception."""
        return hash(self.message)


class EventSubscriber(ABC): # pylint: disable=too-few-public-methods
    """Event subscriber abstract base class."""

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def update(self, event:str, data:Any | None = None):
        """
        Update the event subscriber with a new event.

        Args:
            event (str): The event string.
            data: The data object.
        """
