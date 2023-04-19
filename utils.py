"""Utility functions."""
import json
from typing import List

from logger import app_logger

MESSAGES_MAPPING_FILE_HISTORY = "messages_mapping_history.json"

logger = app_logger()


def load_mapping_data() -> dict:
    """Load the mapping data from the mapping file."""
    try:
        with open(MESSAGES_MAPPING_FILE_HISTORY, "r", encoding="utf-8") as messages_mapping:
            data = json.load(messages_mapping)
            logger.debug("Loaded mapping data: %s", data)
            return data
    except FileNotFoundError:
        return {}


def save_mapping_data(tg_message_id, discord_message_id) -> None:
    """Save the mapping data to the mapping file."""
    mapping_data = load_mapping_data()
    tg_message_id = str(tg_message_id)  # Convert the key to a string
    mapping_data[tg_message_id] = discord_message_id
    with open(MESSAGES_MAPPING_FILE_HISTORY, "w", encoding="utf-8") as messages_mapping:
        json.dump(mapping_data, messages_mapping)


def get_discord_message_id(tg_message_id) -> int:
    """Get the Discord message ID from the mapping file."""
    mapping_data = load_mapping_data()
    tg_message_id = str(tg_message_id)  # Convert the key to a string
    return mapping_data.get(tg_message_id, None)


def split_message(message: str, max_length: int = 2000) -> List[str]:
    """Split a message into multiple messages if it exceeds the max length."""
    if len(message) <= max_length:
        return [message]

    message_parts = []
    while len(message) > max_length:
        split_index = message[:max_length].rfind("\n")
        if split_index == -1:
            split_index = max_length

        message_parts.append(message[:split_index])
        message = message[split_index:].lstrip()

    if message:
        message_parts.append(message)

    return message_parts
