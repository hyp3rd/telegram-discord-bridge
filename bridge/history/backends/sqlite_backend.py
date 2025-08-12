"""SQLite based history backend."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import aiosqlite

from bridge.config import Config

from .base import HistoryStorageBackend

config = Config.get_instance()


class SQLiteHistoryBackend(HistoryStorageBackend):
    """Store history information in a SQLite database."""

    def __init__(self):
        self.db_url = config.history.db_url or "messages_history.db"

    async def _ensure_tables(self) -> None:
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS message_mapping (
                    forwarder TEXT,
                    tg_message_id INTEGER,
                    discord_message_id INTEGER,
                    PRIMARY KEY(forwarder, tg_message_id)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS missed_messages (
                    forwarder TEXT,
                    tg_message_id INTEGER,
                    discord_channel_id INTEGER,
                    exception TEXT
                )
                """
            )
            await db.commit()

    async def load_mapping_data(self) -> Dict[str, Dict[int, int]]:
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(
                "SELECT forwarder, tg_message_id, discord_message_id FROM message_mapping"
            ) as cursor:
                rows = await cursor.fetchall()
        data: Dict[str, Dict[int, int]] = {}
        for forwarder, tg_id, discord_id in rows:
            data.setdefault(forwarder, {})[tg_id] = discord_id
        return data

    async def save_mapping_data(
        self, forwarder_name: str, tg_message_id: int, discord_message_id: int
    ) -> None:
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute(
                "INSERT OR REPLACE INTO message_mapping (forwarder, tg_message_id, discord_message_id) VALUES (?, ?, ?)",
                (forwarder_name, tg_message_id, discord_message_id),
            )
            await db.commit()

    async def save_missed_message(
        self,
        forwarder_name: str,
        tg_message_id: int,
        discord_channel_id: int,
        exception: Any,
    ) -> None:
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_url) as db:
            await db.execute(
                "INSERT INTO missed_messages (forwarder, tg_message_id, discord_channel_id, exception) VALUES (?, ?, ?, ?)",
                (forwarder_name, tg_message_id, discord_channel_id, repr(exception)),
            )
            await db.commit()

    async def get_discord_message_id(
        self, forwarder_name: str, tg_message_id: int
    ) -> Optional[int]:
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(
                "SELECT discord_message_id FROM message_mapping WHERE forwarder=? AND tg_message_id=?",
                (forwarder_name, tg_message_id),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else None

    async def get_last_messages_for_all_forwarders(self) -> List[dict]:
        await self._ensure_tables()
        async with aiosqlite.connect(self.db_url) as db:
            async with db.execute(
                """
                SELECT forwarder, MAX(tg_message_id) AS last_id
                FROM message_mapping
                GROUP BY forwarder
                """
            ) as cursor:
                rows = await cursor.fetchall()
        results = []
        for forwarder, last_id in rows:
            async with aiosqlite.connect(self.db_url) as db:
                async with db.execute(
                    "SELECT discord_message_id FROM message_mapping WHERE forwarder=? AND tg_message_id=?",
                    (forwarder, last_id),
                ) as cursor:
                    row = await cursor.fetchone()
            discord_id = row[0] if row else None
            results.append(
                {
                    "forwarder_name": forwarder,
                    "telegram_id": int(last_id),
                    "discord_id": discord_id,
                }
            )
        return results
