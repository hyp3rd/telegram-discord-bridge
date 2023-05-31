"""Bridge Health API Router."""

import asyncio
from datetime import datetime
from typing import Any, List

from fastapi import WebSocket

from api.models import Health, HealthHistory, HealthSchema
from bridge.config import Config
from bridge.enums import ProcessStateEnum
from bridge.events import EventSubscriber
from bridge.logger import Logger
from forwarder import determine_process_state

logger = Logger.get_logger(Config.get_config_instance().app.name)
# Initialize a global Config object
config = Config()

class WSConnectionManager:
    """WS Connection Manager."""

    def __init__(self, health_history: HealthHistory):
        self.active_connections: List[WebSocket] = []
        self.health_history: HealthHistory = health_history

    async def connect(self, websocket: WebSocket):
        """Connect, handles the WS connections."""
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Disconnect, handles the WS connections."""
        self.active_connections.remove(websocket)

    async def send_health_data(self, websocket: WebSocket):
        """Send health data to the WS client."""
        current_config = config.get_config_instance()
        pid_file = f'{current_config.app.name}.pid'
        process_state, pid = determine_process_state(pid_file)

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
            await asyncio.sleep(config.app.healthcheck_interval)  # send health data every second


class HealthcheckSubscriber(EventSubscriber): # pylint: disable=too-few-public-methods
    """Event subscriber class."""

    def __init__(self, name, health_history: HealthHistory):
        super().__init__(name)
        self.health_history: HealthHistory = health_history

    def update(self, event:str, data:Any | None = None):
        """
        Update the event subscriber with a new event.

        Args:
            event (str): The event string.
            data (Any): The config object.

        Returns:
            None
        """
        logger.debug("Subscriber %s received event: %s", self.name, event)

        if data and isinstance(data, Config):
            logger.debug("Subscriber %s received config: %s", self.name, data)
            health_data = Health(
                timestamp=datetime.timestamp(datetime.now()),
                process_state=ProcessStateEnum.RUNNING,
                process_id=0,
                status={
                    "telegram": data.telegram.is_healthy,
                    "discord": data.discord.is_healthy,
                    "openai": data.openai.is_healthy,
                    "internet": data.app.internet_connected,
                })

            self.health_history.add_health_data(health_data)
