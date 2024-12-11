"""Messages history handler"""

import os
import asyncio
import json
import time
from typing import Any, List, Optional

import aiofiles
import Levenshtein
from telethon import TelegramClient
from telethon.tl.types import Message

from bridge.config import Config
from bridge.history.contextual_analysis import ContextualAnalysis
from bridge.logger import Logger

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)

MESSAGES_HISTORY_FILE = "messages_history.json"
MISSED_MESSAGES_HISTORY_FILE = "missed_messages_history.json"


class MessageHistoryHandler:
    """Messages history handler."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._mapping_data_cache = None
            cls._lock = asyncio.Lock()
        return cls._instance

    async def load_mapping_data(self) -> dict:
        """Load the mapping data from the mapping file."""
        async with self._lock:
            logger.debug("Loading mapping data...")
            if self._mapping_data_cache is None:
                try:
                    async with aiofiles.open(
                        MESSAGES_HISTORY_FILE, "r", encoding="utf-8"
                    ) as messages_mapping:
                        data = json.loads(await messages_mapping.read())
                        logger.debug("Loaded mapping data: %s", data)
                        self._mapping_data_cache = data
                except FileNotFoundError:
                    self._mapping_data_cache = {}

            return self._mapping_data_cache

    async def save_mapping_data(
        self, forwarder_name: str, tg_message_id: int, discord_message_id: int
    ) -> None:
        """Save the mapping data to the mapping file."""
        # async with self._lock:
        mapping_data = await self.load_mapping_data()

        logger.debug(
            "Saving mapping data: %s, %s, %s",
            forwarder_name,
            tg_message_id,
            discord_message_id,
        )

        if forwarder_name not in mapping_data:
            mapping_data[forwarder_name] = {}

        mapping_data[forwarder_name][tg_message_id] = discord_message_id

        # Rotate oldest entries if file is too large
        if os.stat(MESSAGES_HISTORY_FILE).st_size >= config.logger.file_max_bytes:
            mapping_data[forwarder_name].pop(next(iter(mapping_data[forwarder_name])))
            logger.debug("Reached max size on %s, starting to rotate entries", MESSAGES_HISTORY_FILE)
        try:
            async with aiofiles.open(
                MESSAGES_HISTORY_FILE, "w", encoding="utf-8"
            ) as messages_mapping:
                await messages_mapping.write(json.dumps(mapping_data, indent=4))

            self._mapping_data_cache = mapping_data

            logger.debug("Mapping data saved successfully.")

            if config.application.debug:
                logger.debug("Current mapping data: %s", mapping_data)

        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while saving mapping data: %s",
                ex,
                exc_info=config.application.debug,
            )

    async def save_missed_message(
        self,
        forwarder_name: str,
        tg_message_id: int,
        discord_channel_id: int,
        exception: Any,
    ) -> None:
        """Save the missed message to the missed messages file."""
        mapping_data = await self.load_mapping_data()

        logger.debug(
            "Saving missed message: %s, %s, %s, %s",
            forwarder_name,
            tg_message_id,
            discord_channel_id,
            exception,
        )

        if forwarder_name not in mapping_data:
            mapping_data[forwarder_name] = {}

        mapping_data[forwarder_name][tg_message_id] = discord_channel_id, exception
        try:
            async with aiofiles.open(
                MISSED_MESSAGES_HISTORY_FILE, "w", encoding="utf-8"
            ) as missed_messages_mapping:
                await missed_messages_mapping.write(json.dumps(mapping_data, indent=4))

            logger.debug("Missed message saved successfully.")

            if config.application.debug:
                logger.debug("Current missed messages data: %s", mapping_data)

        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while saving missed message: %s",
                ex,
                exc_info=config.application.debug,
            )

    async def get_discord_message_id(
        self, forwarder_name: str, tg_message_id: int
    ) -> Optional[int]:
        """Get the Discord message ID associated with the given TG message ID for the specified forwarder."""
        mapping_data = await self.load_mapping_data()
        forwarder_data = mapping_data.get(forwarder_name, None)

        if forwarder_data is not None:
            return forwarder_data.get(tg_message_id, None)

        return None

    async def get_last_messages_for_all_forwarders(self) -> List[dict]:
        """Get the last messages for each forwarder."""
        mapping_data = await self.load_mapping_data()
        last_messages = []
        if mapping_data.items():
            for forwarder_name, forwarder_data in mapping_data.items():
                if not forwarder_data:
                    logger.debug(
                        "No messages found in the history for forwarder %s",
                        forwarder_name,
                    )
                    continue
                last_tg_message_id = max(forwarder_data, key=int)
                logger.debug(
                    "Last TG message ID for forwarder %s: %s",
                    forwarder_name,
                    last_tg_message_id,
                )
                discord_message_id = forwarder_data[last_tg_message_id]
                last_messages.append(
                    {
                        "forwarder_name": forwarder_name,
                        "telegram_id": int(last_tg_message_id),
                        "discord_id": discord_message_id,
                    }
                )
        return last_messages

    async def fetch_messages_after(
        self, last_tg_message_id: int, channel_id: int, tgc: TelegramClient
    ) -> List:
        """Fetch messages after the last TG message ID."""
        logger.debug("Fetching messages after %s", last_tg_message_id)
        messages = []
        async for message in tgc.iter_messages(
            channel_id, offset_id=last_tg_message_id, reverse=True
        ):
            logger.debug("Fetched message: %s", message.id)
            messages.append(message)
        return messages

    async def spam_filter(
        self, telegram_message: Message, channel_id: int, tgc: TelegramClient
    ) -> bool:
        """Detect if a message is similar to another message sent in the past 30 seconds."""
        logger.info("Checking if message is similar to a previous message")
        threshold = (
            config.application.anti_spam_similarity_threshold  # Set a threshold for similarity (0 to 1, with 1 being identical)
        )

        current_unix_timestamp = time.time()

        async for message in tgc.iter_messages(channel_id, limit=10, reverse=False):
            logger.debug("Checking message: %s", message.id)
            logger.debug("Message text: %s", message.text)
            logger.debug("Current message text: %s", telegram_message.text)

            if message.id != telegram_message.id:
                # New channels can have previous messages that are None or when a meta message appears like a photo change for a channel
                if message.text is None or (message.text == "" and telegram_message.text == "") :
                    continue
                similarity = 1 - Levenshtein.distance(
                    message.text, telegram_message.text
                ) / max(len(message.text), len(telegram_message.text))
                logger.debug("Similarity: %f", similarity)

                if (
                    similarity > threshold
                    and current_unix_timestamp - message.date.timestamp()
                    <= config.application.anti_spam_similarity_timeframe
                ):
                    logger.warning(
                        "Message with ID %s is similar to a message previously sent with ID %s",
                        telegram_message.id,
                        message.id,
                    )

                    return True

        if config.application.anti_spam_contextual_analysis:
            # If no duplicate found, optionally check for contextual relevance
            contextual_analysis = ContextualAnalysis()
            is_relevant = await contextual_analysis.is_relevant_message(
                telegram_message, channel_id, tgc
            )
            if is_relevant:
                logger.debug(
                    "Message with ID %s is not a duplicate and is contextually relevant",
                    telegram_message.id,
                )
                return False

            logger.warning(
                "Message with ID %s is neither a duplicate nor contextually relevant",
                telegram_message.id,
            )
            return True

        logger.debug(
            "Message is not similar or contextually relevant to previous messages"
        )

        return False
