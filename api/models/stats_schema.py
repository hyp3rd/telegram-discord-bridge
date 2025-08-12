"""Schema for bridge statistics."""
from typing import Dict

from pydantic import BaseModel


class StatsResponse(BaseModel):
    """Per-forwarder statistics response."""

    stats: Dict[str, int]
