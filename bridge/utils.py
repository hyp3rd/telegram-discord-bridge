"""Utility functions."""
from typing import List, Tuple

from telethon.tl.types import (Message, MessageEntityBold, MessageEntityCode,
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


def telegram_entities_to_markdown(message: Message, strip_off_links: bool) -> str:
    """Convert Telegram entities to Markdown.

    Args:
        message: A Telethon Message object.
        strip_off_links: Whether to strip off links.

    Returns:
        The message text in Markdown format.
    """
    message_text = message.message

    if not message.entities:
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
        for entity in message.entities
    ]

    # Sort entities by start offset in descending order.
    sorted_entities = sorted(entities, key=lambda e: e[0], reverse=True)

    links = []  # To hold link text and URLs
    link_count = 0  # To count the links and assign reference numbers

    for start, end, entity_type, url in sorted_entities:
        markdown_delimiters = markdown_map.get(entity_type)  # type: ignore

        if markdown_delimiters:
            message_text, _ = apply_markdown(
                message_text, start, end, markdown_delimiters
            )
        elif url:  # This is a MessageEntityTextUrl.
            link_count += 1
            links.append((link_count, message_text[start:end], url))
            # Replace the link text with plain text followed by the reference number
            message_text = message_text[:start] + message_text[start:end] + f" [{link_count}]" + message_text[end:]

    # Append the links at the end of the message
    if links and not strip_off_links:
        message_text += "\n\nLinks:"
        for link_number, link_text, link in links:
            message_text += f"\n[{link_number}] {link_text}: {link}"  # Each link on a new line for Discord to parse as embeds

    return message_text

def apply_markdown(text: str, start: int, end: int, delimiters: Tuple[str, str]) -> Tuple[str, int]:
    """Applies markdown delimiters to a portion of the text.

    Args:
        text: The text to modify.
        start: The start index where to apply the markdown.
        end: The end index where to apply the markdown.
        delimiters: A tuple with the opening and closing delimiters.

    Returns:
        A tuple with the modified text and the offset correction.
    """
    opening_delimiter, closing_delimiter = delimiters
    return (
        text[:start] + opening_delimiter + text[start:end] + closing_delimiter + text[end:],
        len(opening_delimiter) + len(closing_delimiter)
    )
