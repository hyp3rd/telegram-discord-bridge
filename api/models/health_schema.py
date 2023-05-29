"""Health Schema."""""

from pydantic import BaseModel
from bridge.enums import ProcessStateEnum


class Health(BaseModel):
    """Health."""
    process_state: ProcessStateEnum
    process_id: int
    status: bool | dict[str, bool]


class HealthSchema(BaseModel):
    """Health Schema."""
    health: Health
