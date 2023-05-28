"""Bridge Health API Router."""

import asyncio
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.models import HealthSchema
from bridge.config import Config
from forwarder import determine_process_state

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("/",
            name="health",
            summary="Get the health status of the Bridge.",
            description="Determines the Bridge process status, the Telegram, Discord, and OpenAI connections health and returns a summary.",
            response_model=HealthSchema)
async def health():
    """Return the health status of the Bridge."""
    config = Config.get_config_instance()

    pid_file = f'{config.app.name}.pid'
    process_state, pid = determine_process_state(pid_file)

    return HealthSchema(
        health={
            "process_state": process_state,
            "process_id": pid,
            "status": config.get_status(key=None),
        }
    )


class ConnectionManager:
    """WS Connection Manager."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Connect, handles the WS connections."""
        await websocket.accept()
        self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Disconnect, handles the WS connections."""
        self.active_connections.remove(websocket)

    async def send_health_data(self, websocket: WebSocket):
        """Send health data to the WS client."""
        config = Config.get_config_instance()
        pid_file = f'{config.app.name}.pid'
        process_state, pid = determine_process_state(pid_file)
        health_data = HealthSchema(
            health={
                "process_state": process_state,
                "process_id": pid,
                "status": config.get_status(key=None),
            }
        )
        if websocket in self.active_connections:
            await websocket.send_json(health_data.dict())
            await asyncio.sleep(1)  # send health data every second


manager = ConnectionManager()


async def health_data_sender(websocket: WebSocket):
    """Send health data to the WS client."""
    while True:
        await manager.send_health_data(websocket)


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """Websocket endpoint."""
    await manager.connect(websocket)
    task = asyncio.create_task(health_data_sender(websocket))
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        task.cancel()
        manager.disconnect(websocket)
