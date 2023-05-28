"""Health Schema."""""

from pydantic import BaseModel
from bridge.enums import ProcessStateEnum


class Status(BaseModel):
    """Status."""
    internet_connected: bool
    telegram_available: bool
    discord_available: bool
    openai_available: bool


class Health(BaseModel):
    """Health."""
    process_state: ProcessStateEnum
    process_id: int
    status: Status


class HealthSchema(BaseModel):
    """Health Schema."""
    health: Health
