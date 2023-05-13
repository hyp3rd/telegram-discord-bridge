"""Utility functions."""
from typing import List

from discord import Embed, utils
from telethon.tl.types import (MessageEntityBold, MessageEntityCode,
                               MessageEntityItalic, MessageEntityPre,
                               MessageEntityStrike, MessageEntityTextUrl)

from bridge.config import Config
from bridge.logger import Logger

config = Config()
logger = Logger.get_logger(config.app.name)


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
    return (
        markdown_text[:start]
        + markdown_delimiters[0]
        + markdown_text[start:end]
        + markdown_delimiters[1]
        + markdown_text[end:],
        # return added length
        len(markdown_delimiters[0]) + len(markdown_delimiters[1]),
    )


def telegram_entities_to_markdown(message_text: str, message_entities: list) -> str:
    """Convert Telegram entities to Markdown."""
    if not message_entities:
        return message_text

    logger.debug("message_text: %s", message_text)
    logger.debug("message_entities: %s", message_entities)

    markdown_map = {
        MessageEntityBold: ("**", "**"),
        MessageEntityItalic: ("*", "*"),
        MessageEntityStrike: ("~~", "~~"),
        MessageEntityCode: ("`", "`"),
        MessageEntityPre: ("```", "```"),
    }

    # Create a list of tuples with start offset, end offset, entity type, and associated data.
    entities = [
        (entity.offset, entity.offset + entity.length, type(entity),
         entity.url if isinstance(entity, MessageEntityTextUrl) else None)
        for entity in message_entities
    ]

    # Sort entities by start offset in ascending order, and by end offset in descending order.
    sorted_entities = sorted(entities, key=lambda e: (e[0], -e[1]))

    markdown_text = message_text
    # markdown_text = utils.remove_markdown(message_text, ignore_links=True)
    offset_correction = 0

    # Convert Telegram UTF-16 offset and length to Python string index
    for start, end, entity_type, url in sorted_entities:
        start = len(message_text.encode('utf-16-le')
                    [:start * 2].decode('utf-16-le'))
        end = len(message_text.encode('utf-16-le')
                  [:end * 2].decode('utf-16-le'))

        start += offset_correction
        end += offset_correction
        markdown_delimiters = markdown_map.get(entity_type)

        if markdown_delimiters:
            markdown_text, correction = apply_markdown(
                markdown_text, start, end, markdown_delimiters
            )
            offset_correction += correction
        elif url:  # This is a MessageEntityTextUrl.

            logger.debug("url: %s", url)

            markdown_text = (
                markdown_text[:start]
                + " ["
                + markdown_text[start:end]
                + "]("
                + url
                + ") "
                + markdown_text[end:]
            )

            offset_correction += len(url) + 4

    return markdown_text
