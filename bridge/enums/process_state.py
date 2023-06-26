"""Prcess State Enum"""

from enum import Enum


class ProcessStateEnum(str, Enum):
    """Process State Enum."""
    RUNNING = "running"
    STARTING = "starting"
    STOPPED = "stopped"
    STOPPING = "stopping"
    PAUSED = "paused"
    ORPHANED = "orphaned"
    FAILED = "failed"
    UNKNOWN = "unknown"
