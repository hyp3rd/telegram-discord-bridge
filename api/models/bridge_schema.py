"""The Bridge Schema."""

from pydantic import BaseModel

from bridge.enums import ProcessStateEnum


class BridgeResponse(BaseModel):
    """Bridge Response."""
    name: str = "Telegram to Discord Bridge"
    status: ProcessStateEnum = ProcessStateEnum.STOPPED
    bridge_process_id: int | None = 0
    config_version: str = "0.0.0"
    telegram_authenticated: bool = False
    error: str = ""


class BridgeResponseSchema(BaseModel):
    """Bridge Response Schema."""
    bridge: BridgeResponse
