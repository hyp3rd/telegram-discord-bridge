"""Simple statistics tracker for forwarded messages."""

from collections import defaultdict
from typing import Dict

from core import SingletonMeta


class StatsTracker(metaclass=SingletonMeta):
    """Track per-forwarder statistics."""

    def __init__(self) -> None:
        self._per_forwarder: Dict[str, int] = defaultdict(int)

    def increment(self, forwarder_name: str) -> None:
        """Increment message count for a forwarder."""
        self._per_forwarder[forwarder_name] += 1

    def get_stats(self) -> Dict[str, int]:
        """Return current statistics."""
        return dict(self._per_forwarder)

    def reset(self) -> None:
        """Reset collected statistics."""
        self._per_forwarder.clear()
