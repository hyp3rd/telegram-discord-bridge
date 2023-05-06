"""Messages history handler"""

import json
from typing import List, Optional

import aiofiles
from telethon import TelegramClient

from bridge.config import Config
from bridge.logger import Logger

logger = Logger.get_logger(Config().app.name)

MESSAGES_MAPPING_HISTORY_FILE = "messages_mapping_history.json"


class MessageHistoryHandler:
    """Messages history handler."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._mapping_data_cache = None
        return cls._instance

    async def load_mapping_data(self) -> dict:
        """Load the mapping data from the mapping file."""
        if self._mapping_data_cache is None:
            try:
                async with aiofiles.open(MESSAGES_MAPPING_HISTORY_FILE, "r", encoding="utf-8") as messages_mapping:
                    data = json.loads(await messages_mapping.read())
                    logger.debug("Loaded mapping data: %s", data)
                    self._mapping_data_cache = data
            except FileNotFoundError:
                self._mapping_data_cache = {}

        return self._mapping_data_cache

    async def save_mapping_data(self, forwarder_name: str, tg_message_id: int, discord_message_id: int) -> None:
        """Save the mapping data to the mapping file."""
        mapping_data = await self.load_mapping_data()

        if forwarder_name not in mapping_data:
            mapping_data[forwarder_name] = {}

        # tg_message_id = str(tg_message_id)
        mapping_data[forwarder_name][tg_message_id] = discord_message_id

        async with aiofiles.open(MESSAGES_MAPPING_HISTORY_FILE, "w", encoding="utf-8") as messages_mapping:
            await messages_mapping.write(json.dumps(mapping_data, indent=4))

        self._mapping_data_cache = mapping_data

    async def get_discord_message_id(self, forwarder_name: str, tg_message_id: int) -> Optional[int]:
        """Get the Discord message ID associated with the given TG message ID for the specified forwarder."""
        mapping_data = await self.load_mapping_data()
        forwarder_data = mapping_data.get(forwarder_name, None)

        if forwarder_data is not None:
            # tg_message_id = str(tg_message_id)
            return forwarder_data.get(tg_message_id, None)

        return None

    async def get_last_messages_for_all_forwarders(self) -> List[dict]:
        """Get the last messages for each forwarder."""
        mapping_data = await self.load_mapping_data()
        last_messages = []
        for forwarder_name, forwarder_data in mapping_data.items():
            last_tg_message_id = max(forwarder_data, key=int)
            discord_message_id = forwarder_data[last_tg_message_id]
            last_messages.append({
                "forwarder_name": forwarder_name,
                "telegram_id": int(last_tg_message_id),
                "discord_id": discord_message_id
            })
        return last_messages

    async def fetch_messages_after(self, last_tg_message_id: int, channel_id: int, tgc: TelegramClient) -> List:
        """Fetch messages after the last TG message ID."""
        logger.debug("Fetching messages after %s", last_tg_message_id)
        messages = []
        async for message in tgc.iter_messages(channel_id, offset_id=last_tg_message_id, reverse=True):
            logger.debug("Fetched message: %s", message.id)
            messages.append(message)
        return messages
