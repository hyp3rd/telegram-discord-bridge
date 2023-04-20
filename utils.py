"""Utility functions."""
import json
from typing import List

from telethon.tl.types import (MessageEntityBold, MessageEntityCode,
                               MessageEntityItalic, MessageEntityPre,
                               MessageEntityStrike, MessageEntityTextUrl)

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


def apply_markdown(markdown_text, start, end, markdown_delimiters):
    """Apply Markdown delimiters to a text range."""
    delimiter_length = len(
        markdown_delimiters[0]) + len(markdown_delimiters[1])
    return (
        markdown_text[:start]
        + markdown_delimiters[0]
        + markdown_text[start:end]
        + markdown_delimiters[1]
        + markdown_text[end:],
        delimiter_length,
    )


def telegram_entities_to_markdown(message_text: str, message_entities: list) -> str:
    """Convert Telegram entities to Markdown."""
    if not message_entities:
        return message_text

    markdown_text = message_text
    offset_correction = 0

    markdown_map = {
        MessageEntityBold: ("**", "**"),
        MessageEntityItalic: ("*", "*"),
        MessageEntityStrike: ("~~", "~~"),
        MessageEntityCode: ("`", "`"),
        MessageEntityPre: ("```", "```"),
    }

    for entity in message_entities:
        start = entity.offset + offset_correction
        end = start + entity.length
        markdown_delimiters = markdown_map.get(type(entity))

        if markdown_delimiters:
            markdown_text, correction = apply_markdown(
                markdown_text, start, end, markdown_delimiters
            )
            offset_correction += correction
        elif isinstance(entity, MessageEntityTextUrl):
            markdown_text = (
                markdown_text[:start]
                + "["
                + markdown_text[start:end]
                + "]("
                + entity.url
                + ")"
                + markdown_text[end:]
            )
            offset_correction += len(entity.url) + 4

    return markdown_text
