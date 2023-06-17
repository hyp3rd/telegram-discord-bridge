"""Utility functions."""
from typing import List

from discord import utils
from telethon.tl.types import (MessageEntityBold, MessageEntityCode,
                               MessageEntityItalic, MessageEntityPre,
                               MessageEntityStrike, MessageEntityTextUrl)


def split_message(message: str, max_length: int = 2000) -> List[str]:
    """Split a message into multiple messages if it exceeds the max length."""
    if len(message) <= max_length:
        return [message]

    message_parts = []
    while len(message) > max_length:
        # Find the last newline before the max length.
        split_index = message[:max_length].rfind("\n")
        if split_index == -1:
            # If a newline wasn't found, split at the max length.
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


def telegram_entities_to_markdown(message_text: str, message_entities: list, strip_off_links: bool) -> str:
    """Convert Telegram entities to Markdown.

    Args:
        message_text: The text of the message.
        message_entities: The entities of the message.
        strip_off_links: Whether to strip off links.

    Returns:
        The message text in Markdown format.
    """

    if not message_entities:
        return message_text

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

    message_text = utils.remove_markdown(
        message_text, ignore_links=False)

    offset_correction = 0

    links = []  # To hold link text and URLs

    for start, end, entity_type, url in sorted_entities:
        start += offset_correction
        end += offset_correction
        markdown_delimiters = markdown_map.get(entity_type)

        if markdown_delimiters:
            message_text, correction = apply_markdown(
                message_text, start, end, markdown_delimiters
            )
            offset_correction += correction
        elif url:  # This is a MessageEntityTextUrl.
            links.append(f"<{url}>")
            # No need to do anything here as we're only replacing the text with itself.

    # Append the links at the end of the message
    if links and not strip_off_links:
        message_text += "\n\n**Links**\n" + "\n".join(links)

    return message_text
