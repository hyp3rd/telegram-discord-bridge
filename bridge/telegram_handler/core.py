"""Telegram handler."""
import os
from typing import Any, List

from discord import Message
from telethon import TelegramClient
from telethon.tl.types import (MessageEntityHashtag, MessageEntityTextUrl,
                               MessageEntityUrl)

from bridge.config import Config
from bridge.discord_handler import forward_to_discord
from bridge.logger import Logger
from bridge.openai_handler import analyze_message_sentiment
from bridge.utils import telegram_entities_to_markdown

logger = Logger.get_logger(Config().app.name)

tg_to_discord_message_ids = {}


def get_telegram_password(config: Config) -> str:
    """Get the Telegram password from the environment variable or from the config file."""
    telegram_password = os.getenv("TELEGRAM_PASSWORD", None)
    if telegram_password is None:
        telegram_password = config.telegram.password

    return telegram_password


async def start_telegram_client(config: Config) -> TelegramClient:
    """Start the Telegram client."""
    logger.info("Starting Telegram client...")

    telethon_logger = Logger.get_telethon_logger()
    telethon_logger_handler = Logger.generate_handler(
        f"{config.app.name}_telegram", config.logger)
    telethon_logger.addHandler(telethon_logger_handler)

    telegram_client = TelegramClient(
        session=config.app.name,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        connection_retries=15,
        retry_delay=4,
        base_logger=telethon_logger,
        lang_code="en",
        system_lang_code="en")

    await telegram_client.start(
        phone=config.telegram.phone,
        password=lambda: get_telegram_password(config))  # type: ignore
    # password=config.telegram.password)

    bot_identity = await telegram_client.get_me(input_peer=False)
    logger.info("Telegram client started the session: %s, with identity: %s",
                config.app.name, bot_identity.id)  # type: ignore

    return telegram_client


def get_message_forward_hashtags(message):
    """Get forward_hashtags from a message."""
    entities = message.entities or []
    forward_hashtags = [entity for entity in entities if isinstance(
        entity, MessageEntityHashtag)]

    return [message.text[hashtag.offset:hashtag.offset + hashtag.length] for hashtag in forward_hashtags]   # pylint: disable=line-too-long


async def process_message_text(event, forwarder_config: dict[str, Any],
                               mention_everyone: bool,
                               mention_roles: List[str],
                               openai_enabled: bool) -> str:  # pylint: disable=too-many-arguments
    """Process the message text and return the processed text."""
    message_text = event.message.message

    if openai_enabled:
        suggestions = await analyze_message_sentiment(message_text)
        message_text = f'{message_text}\n{suggestions}'

    if mention_everyone:
        message_text += '\n' + '@everyone'

    if mention_roles:
        mention_text = ", ".join(role for role in mention_roles)
        message_text = f"{mention_text}\n{message_text}"

    return telegram_entities_to_markdown(message_text, event.message.entities, forwarder_config["strip_off_links"])


async def process_media_message(telegram_client: TelegramClient,
                                event, discord_channel,
                                message_text, discord_reference):
    """Process a message that contains media."""
    file_path = await telegram_client.download_media(event.message)
    try:
        with open(file_path, "rb") as image_file:  # type: ignore
            sent_discord_messages = await forward_to_discord(discord_channel,
                                                             message_text,
                                                             image_file=image_file,
                                                             reference=discord_reference)
    except OSError as ex:
        logger.error(
            "An error occurred while opening the file %s: %s",  file_path, ex)
        return
    finally:
        os.remove(file_path)  # type: ignore

    return sent_discord_messages


async def handle_message_media(telegram_client: TelegramClient, event, discord_channel, message_text, discord_reference) -> List[Message] | None:
    """Handle a message that contains media."""
    contains_url = any(isinstance(entity, (MessageEntityTextUrl, MessageEntityUrl))
                       for entity in event.message.entities or [])

    if contains_url:
        sent_discord_messages = await process_url_message(discord_channel,
                                                          message_text,
                                                          discord_reference)
    else:
        sent_discord_messages = await process_media_message(telegram_client, event, discord_channel,
                                                            message_text,
                                                            discord_reference)

    return sent_discord_messages


async def process_url_message(discord_channel, message_text, discord_reference):
    """Process a message that contains a URL."""
    sent_discord_messages = await forward_to_discord(discord_channel,
                                                     message_text,
                                                     reference=discord_reference)
    return sent_discord_messages
