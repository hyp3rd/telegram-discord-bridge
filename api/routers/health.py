"""Bridge Health API Router."""

import asyncio
import functools
from datetime import datetime
from typing import Any, List

from fastapi import WebSocket

from api.models import Health, HealthHistory, HealthSchema
from bridge.config import Config
from bridge.enums import ProcessStateEnum
from bridge.events import EventSubscriber
from bridge.logger import Logger
from forwarder import Forwarder

# Initialize a global Config object
config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class WSConnectionManager:
    """WS Connection Manager."""

    def __init__(self, health_history: HealthHistory):
        self.active_connections: List[WebSocket] = []
        self.health_history: HealthHistory = health_history
        # self.websocket_subscribers: multiprocessing.Queue = multiprocessing.Queue()

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        pass

    async def connect(self, websocket: WebSocket):
        """Connect, handles the WS connections."""
        logger.debug("Connecting to %s", websocket)
        if isinstance(websocket, WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Disconnect, handles the WS connections."""
        self.active_connections.remove(websocket)

    async def broadcast_health_data(self):
        """Broadcast health data to all WS clients."""
        logger.debug("Broadcasting health data to %s", self.active_connections)
        for websocket in self.active_connections:
            await self.send_health_data(websocket)

    async def send_health_data(self, websocket: WebSocket):
        """Send health data to the WS client."""
        logger.debug("Sending health data to %s", websocket)

        process_state, pid = Forwarder().get_instance().determine_process_state()

        health_status = None

        try:
            health_status = self.health_history.get_health_data()
        except ValueError:
            logger.error("Unable to retrieve the last health status.")
            health_data = HealthSchema(
                health=Health(
                process_id=pid,
            )
        )

        health_data = HealthSchema(
            health=Health(
                timestamp=health_status.timestamp if health_status else 0,
                process_state=process_state,
                process_id=pid,
                status=health_status.status if health_status else {},
            )
        )

        if websocket in self.active_connections:
            await websocket.send_json(health_data.dict())


def websocket_broadcast_when_healthcheck(func):
    """Decorator to broadcast health data when a healthcheck event is received."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        asyncio.create_task(self.ws_manager.broadcast_health_data())
        return result
    return wrapper


class HealthcheckSubscriber(EventSubscriber): # pylint: disable=too-few-public-methods
    """Healthcheck subscriber class."""

    def __init__(self, name, dispatcher, health_history: HealthHistory, ws_manager: WSConnectionManager):
        super().__init__(name, dispatcher=dispatcher)
        self.health_history: HealthHistory = health_history
        self.ws_manager = ws_manager

    @websocket_broadcast_when_healthcheck
    def update(self, event:str, data: Any | None = None):
        """
        Update the event subscriber with a new event.

        Args:
            event (str): The event name.
            data (Any): The config object.

        Returns:
            None
        """

        logger.debug("The healthcheck subscriber %s received event: %s", self.name, event)

        if data and isinstance(data, Config):
            if config.application.debug:
                logger.debug("The healthcheck subscriber %s received config: %s", self.name, data)

            health_data = Health(
                timestamp=datetime.timestamp(datetime.now()),
                process_state=ProcessStateEnum.RUNNING,
                process_id=0,
                status={
                    "telegram": data.telegram.is_healthy,
                    "discord": data.discord.is_healthy,
                    "openai": data.openai.is_healthy,
                    "internet": data.application.internet_connected,
                },)

            self.health_history.add_health_data(health_data)
        else:
            logger.warning("The healthcheck subscriber %s received data: %s", self.name, data)
