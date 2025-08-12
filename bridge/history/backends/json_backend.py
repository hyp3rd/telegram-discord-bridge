"""JSON file based history backend with rotation support."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from typing import Any, Dict, List, Optional

import aiofiles

from bridge.config import Config

from .base import HistoryStorageBackend

config = Config.get_instance()


class JSONHistoryBackend(HistoryStorageBackend):
    """Persist history data into local JSON files."""

    def __init__(self):
        self.messages_file = "messages_history.json"
        self.missed_file = "missed_messages_history.json"
        self.max_bytes = config.history.file_max_bytes
        self.backup_count = config.history.file_backup_count

    async def load_mapping_data(self) -> Dict[str, Dict[int, int]]:
        try:
            async with aiofiles.open(
                self.messages_file, "r", encoding="utf-8"
            ) as handle:
                return json.loads(await handle.read())
        except FileNotFoundError:
            return {}

    async def save_mapping_data(
        self, forwarder_name: str, tg_message_id: int, discord_message_id: int
    ) -> None:
        data = await self.load_mapping_data()
        if forwarder_name not in data:
            data[forwarder_name] = {}
        data[forwarder_name][tg_message_id] = discord_message_id
        await self._rotate_if_needed(self.messages_file)
        async with aiofiles.open(self.messages_file, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(data, indent=4))

    async def load_missed_data(self) -> Dict[str, Dict[int, list]]:
        """Load missed message data from disk."""
        try:
            async with aiofiles.open(self.missed_file, "r", encoding="utf-8") as handle:
                return json.loads(await handle.read())
        except FileNotFoundError:
            return {}

    async def save_missed_message(
        self,
        forwarder_name: str,
        tg_message_id: int,
        discord_channel_id: int,
        exception: Any,
    ) -> None:
        data = await self.load_missed_data()
        if forwarder_name not in data:
            data[forwarder_name] = {}
        data[forwarder_name][tg_message_id] = [discord_channel_id, str(exception)]
        await self._rotate_if_needed(self.missed_file)
        async with aiofiles.open(self.missed_file, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(data, indent=4))

    async def get_discord_message_id(
        self, forwarder_name: str, tg_message_id: int
    ) -> Optional[int]:
        data = await self.load_mapping_data()
        return data.get(forwarder_name, {}).get(tg_message_id)

    async def get_last_messages_for_all_forwarders(self) -> List[dict]:
        data = await self.load_mapping_data()
        last_messages: List[dict] = []
        for forwarder_name, forwarder_data in data.items():
            if not forwarder_data:
                continue
            last_tg_message_id = max(forwarder_data, key=int)
            last_messages.append(
                {
                    "forwarder_name": forwarder_name,
                    "telegram_id": int(last_tg_message_id),
                    "discord_id": forwarder_data[last_tg_message_id],
                }
            )
        return last_messages

    async def _rotate_if_needed(self, path: str) -> None:
        def rotate() -> None:
            if self.max_bytes <= 0 or not os.path.exists(path):
                return
            if os.path.getsize(path) < self.max_bytes:
                return
            for i in range(self.backup_count - 1, 0, -1):
                src = f"{path}.{i}"
                dst = f"{path}.{i + 1}"
                if os.path.exists(src):
                    os.replace(src, dst)
            shutil.copy2(path, f"{path}.1")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{}")

        await asyncio.to_thread(rotate)
