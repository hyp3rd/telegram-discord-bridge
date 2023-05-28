"""PrcessState Enum"""

from enum import Enum


class ProcessStateEnum(str, Enum):
    """Process State Enum."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ORPHANED = "orphaned"
