"""Event dispatcher for the bridge."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List

from bridge.config import Config
from bridge.logger import Logger

logger = Logger.get_logger(Config.get_instance().application.name)

class SingletonMeta(type):
    """Singleton metaclass."""
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

class EventDispatcher(metaclass=SingletonMeta):
    """Event dispatcher class."""

    def __init__(self, subscribers=None):
        # a list of subscribers
        self.subscribers: Dict[str, List[EventSubscriber]] = subscribers or {}

    def add_subscriber(self, event: str, subscriber):
        """Add a subscriber to the event dispatcher.
        
        Args:
            event: The event to subscribe to.
            subscriber: The subscriber to add.
        """
        logger.debug("Adding subscriber: %s", subscriber)
        if self.subscribers.get(event) is None:
            self.subscribers[event] = []

        if subscriber not in self.subscribers[event]:
            try:
                self.subscribers[event].append(subscriber)
                logger.info("Subscriber added: %s", subscriber)
            except KeyError:
                self.subscribers[event] = [subscriber]
                logger.info("Subscriber added: %s", subscriber)
        else:
            logger.info("Subscriber already exists: %s", subscriber)

    def remove_subscriber(self, event, subscriber):
        """Remove a subscriber from the event dispatcher."""
        if event in self.subscribers and subscriber in self.subscribers[event]:
            self.subscribers[event].remove(subscriber)
            logger.info("Subscriber removed: %s", subscriber)
        else:
            logger.info("Subscriber not found: %s", subscriber)

    def notify(self, event, data=None):
        """Notify subscribers of an event."""
        if event in self.subscribers:
            for subscriber in self.subscribers[event]:
                logger.debug("Event dispatcher notifying subscriber: %s", subscriber)

                try:
                    if hasattr(subscriber, "update"):
                        # asyncio.create_task(subscriber.update(event, data))
                        subscriber.update(event, data)
                except EventDispatcherException as ex:
                    message = "The event dispatcher failed to notify its subscribers"
                    logger.error("%s - event: %s - error: %s",  message, event, ex, exc_info=Config.get_instance().application.debug)
                    # raise EventDispatcherException(message=message) from ex
                except Exception as ex: # pylint: disable=broad-except
                    message = "The event dispatcher failed to notify its subscribers"
                    logger.error("%s - event: %s - error: %s",  message, event, ex, exc_info=Config.get_instance().application.debug)
                    # raise EventDispatcherException(message=message) from ex
                else:
                    logger.debug("Event dispatcher successfully notified subscriber: %s", subscriber)
                finally:
                    logger.debug("Event dispatcher finished notifying subscriber: %s", subscriber)
        else:
            logger.debug("Event dispatcher has no subscribers for event: %s", event)

    def stop(self):
        """Stop the event dispatcher."""
        logger.warning("Stopping event dispatcher")
        self.subscribers.clear()
        logger.info("Event dispatcher stopped")

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

    def __init__(self, name, dispatcher: EventDispatcher, subscribers=None):
        self.name = name
        self.dispatcher: EventDispatcher = dispatcher
        # self.subscribers: Dict[str, List[EventSubscriber]] = subscribers or {}
        self.subscribers: Dict[str, Dict[str, List[Callable]]] = subscribers or {}

    @abstractmethod
    def update(self, event:str, data:Any | None = None):
        """
        Update the event subscriber with a new event.

        Args:
            event (str): The event string.
            data: The data object.
        """
        if event in self.subscribers:
            for func in self.subscribers[event]:
                try:
                    if asyncio.iscoroutinefunction(func) and hasattr(func, "update"):
                        logger.debug("Event subscriber %s updating with coroutine function %s", self.name, func)
                        # asyncio.ensure_future(func(data))
                        func(data) # type: ignore
                except EventDispatcherException as ex:
                    message = "The event subscriber failed to update"
                    logger.error("%s - event: %s",  message, event)
                    raise EventDispatcherException(message=message) from ex

    # Create an on_update decorator for the event subscriber.
    def create_on_update_decorator(self):
        """Create an on_update decorator for the event subscriber."""

        def on_update(event: str):
            def decorator(func):
                def wrapper(*args, **kwargs):
                    logger.debug(
                        "Decorator %s called with args %s and kwargs %s", event, args, kwargs
                    )
                    result = func(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = asyncio.ensure_future(result)
                    return result

                # add the original function as a subscriber, not the wrapper
                self.dispatcher.add_subscriber(event, wrapper)

                return wrapper

            return decorator

        return on_update
