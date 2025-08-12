"""Base classes for history storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class HistoryStorageBackend(ABC):
    """Abstract history storage backend."""

    @abstractmethod
    async def load_mapping_data(self) -> Dict[str, Dict[int, int]]:
        """Load mapping data for all forwarders."""

    @abstractmethod
    async def save_mapping_data(
        self, forwarder_name: str, tg_message_id: int, discord_message_id: int
    ) -> None:
        """Persist a mapping between Telegram and Discord messages."""

    @abstractmethod
    async def save_missed_message(
        self,
        forwarder_name: str,
        tg_message_id: int,
        discord_channel_id: int,
        exception: Any,
    ) -> None:
        """Store information about a failed forwarding."""

    @abstractmethod
    async def get_discord_message_id(
        self, forwarder_name: str, tg_message_id: int
    ) -> Optional[int]:
        """Return the Discord ID associated with a Telegram message if available."""

    @abstractmethod
    async def get_last_messages_for_all_forwarders(self) -> List[dict]:
        """Return the last known mapping for each forwarder."""
