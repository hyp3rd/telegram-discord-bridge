"""Messages history handler"""

import asyncio
import time
from typing import Any, List, Optional

import Levenshtein
from telethon import TelegramClient
from telethon.tl.types import Message

from bridge.config import Config
from bridge.history.contextual_analysis import ContextualAnalysis
from bridge.history.backends import get_backend
from bridge.logger import Logger
from bridge.openai.handler import OpenAIHandler

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class MessageHistoryHandler:
    """Messages history handler."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._mapping_data_cache = None
            cls._lock = asyncio.Lock()
            cls._backend = get_backend(config.history)
        return cls._instance

    async def load_mapping_data(self) -> dict:
        """Load the mapping data from the storage backend."""
        async with self._lock:
            logger.debug("Loading mapping data...")
            if self._mapping_data_cache is None:
                self._mapping_data_cache = await self._backend.load_mapping_data()
            return self._mapping_data_cache

    async def save_mapping_data(
        self, forwarder_name: str, tg_message_id: int, discord_message_id: int
    ) -> None:
        """Save the mapping data to the storage backend."""
        logger.debug(
            "Saving mapping data: %s, %s, %s",
            forwarder_name,
            tg_message_id,
            discord_message_id,
        )
        try:
            await self._backend.save_mapping_data(
                forwarder_name, tg_message_id, discord_message_id
            )
            if self._mapping_data_cache is not None:
                self._mapping_data_cache.setdefault(forwarder_name, {})[
                    tg_message_id
                ] = discord_message_id
            logger.debug("Mapping data saved successfully.")
            if config.application.debug:
                logger.debug("Current mapping data: %s", self._mapping_data_cache)
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
        logger.debug(
            "Saving missed message: %s, %s, %s, %s",
            forwarder_name,
            tg_message_id,
            discord_channel_id,
            exception,
        )
        try:
            await self._backend.save_missed_message(
                forwarder_name, tg_message_id, discord_channel_id, exception
            )
            logger.debug("Missed message saved successfully.")
            if config.application.debug:
                logger.debug(
                    "Current missed messages data: %s", self._mapping_data_cache
                )
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
        return await self._backend.get_last_messages_for_all_forwarders()

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
                if not message.text or not telegram_message.text:
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

        if config.application.anti_spam_strategy == "ml":
            if not config.openai.enabled:
                logger.warning("ML anti-spam strategy selected but OpenAI is disabled")
                return False
            return await OpenAIHandler().is_spam(telegram_message.text or "")

        return False
