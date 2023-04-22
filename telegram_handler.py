"""Telegram handler."""
import os

from telethon import TelegramClient
from telethon.tl.types import (MessageEntityHashtag, MessageEntityTextUrl,
                               MessageEntityUrl)

from discord_handler import forward_to_discord
from logger import app_logger
from utils import telegram_entities_to_markdown

tg_to_discord_message_ids = {}

logger = app_logger()


async def start_telegram_client(config) -> TelegramClient:
    """Start the Telegram client."""
    logger.info("Starting Telegram client...")

    telegram_client = TelegramClient(
        session=config["app_name"],
        api_id=config["telegram_api_id"],
        api_hash=config["telegram_api_hash"])

    await telegram_client.start(
        phone=config["telegram_phone"],
        password=config["telegram_password"])

    bot_identity = await telegram_client.get_me()
    logger.info("Telegram client started the session: %s, with identity: %s",
                config["app_name"], bot_identity.id)

    return telegram_client


async def process_media_message(telegram_client: TelegramClient, event, discord_channel, message_text, discord_reference):
    """Process a message that contains media."""
    file_path = await telegram_client.download_media(event.message)
    with open(file_path, "rb") as image_file:
        sent_discord_messages = await forward_to_discord(discord_channel,
                                                         message_text,
                                                         image_file=image_file,
                                                         reference=discord_reference)
    os.remove(file_path)
    return sent_discord_messages


async def handle_message_media(telegram_client: TelegramClient, event, discord_channel, message_text, discord_reference):
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


def process_message_text(event, mention_everyone: bool, override_mention_everyone: bool) -> str:
    """Process the message text and return the processed text."""
    message_text = event.message.message

    if mention_everyone or override_mention_everyone:
        message_text += '\n' + '@everyone'

    return telegram_entities_to_markdown(message_text, event.message.entities)


async def process_url_message(discord_channel, message_text, discord_reference):
    """Process a message that contains a URL."""
    sent_discord_messages = await forward_to_discord(discord_channel,
                                                     message_text,
                                                     reference=discord_reference)
    return sent_discord_messages


def get_message_forward_hashtags(message):
    """Get forward_hashtags from a message."""
    entities = message.entities or []
    forward_hashtags = [entity for entity in entities if isinstance(
        entity, MessageEntityHashtag)]

    return [message.text[hashtag.offset:hashtag.offset + hashtag.length] for hashtag in forward_hashtags]   # pylint: disable=line-too-long
