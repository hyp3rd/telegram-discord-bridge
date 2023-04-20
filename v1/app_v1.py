"""A `Bot` to forward messages from Telegram to a Discord server."""

import asyncio
import os
import sys
from typing import Any

import discord
import yaml
from discord import MessageReference
from telethon import TelegramClient, events
from telethon.tl.types import (Channel, InputChannel, MessageEntityBold,
                               MessageEntityCode, MessageEntityHashtag,
                               MessageEntityItalic, MessageEntityPre,
                               MessageEntityStrike, MessageEntityTextUrl,
                               MessageEntityUrl)

from logger import app_logger
from utils import get_discord_message_id, save_mapping_data, split_message

discord_client = discord.Client(intents=discord.Intents.default())

tg_to_discord_message_ids = {}

logger = app_logger()


def load_config() -> Any:
    """Load configuration from the 'config.yml' file."""
    try:
        with open('config.yml', 'rb') as config_file:
            config_data = yaml.safe_load(config_file)
    except FileNotFoundError:
        logger.error("Error: Configuration file 'config.yml' not found.")
        sys.exit(1)
    except yaml.YAMLError as ex:
        logger.error("Error parsing configuration file: %s", ex)
        sys.exit(1)

    required_keys = [
        "app_name",
        "telegram_phone",
        "telegram_password",
        "telegram_api_id",
        "telegram_api_hash",
        "telegram_input_channels",
        "discord_bot_token",
    ]

    for key in required_keys:
        if key not in config_data:
            logger.error(
                "Error: Key '%s' not found in the configuration file.", key)
            sys.exit(1)

    return config_data


async def start_telegram(config):   # pylint: disable=too-many-statements,too-many-locals
    """Start the Telegram client."""
    telegram_client = TelegramClient(
        session=config["app_name"],
        api_id=config["telegram_api_id"],
        api_hash=config["telegram_api_hash"])

    await telegram_client.start(
        phone=config["telegram_phone"],
        password=config["telegram_password"])

    input_channels_entities = []
    discord_channel_mappings = {}

    async for dialog in telegram_client.iter_dialogs():
        if not isinstance(dialog.entity, Channel) and not isinstance(dialog.entity, InputChannel):
            continue

        for channel_mapping in config["telegram_input_channels"]:
            tg_channel_id = channel_mapping["tg_channel_id"]
            discord_channel_config = {
                "discord_channel_id": channel_mapping["discord_channel_id"],
                "mention_everyone": channel_mapping["mention_everyone"],
                "forward_everything": channel_mapping.get("forward_everything", False),
                "hashtags": channel_mapping.get("hashtags", []),
            }

            if tg_channel_id in {dialog.name, dialog.entity.id}:
                input_channels_entities.append(
                    InputChannel(dialog.entity.id, dialog.entity.access_hash))
                discord_channel_mappings[dialog.entity.id] = discord_channel_config
                logger.info("Registered TG channel '%s' with ID %s with Discord channel config %s",
                            dialog.name, dialog.entity.id, discord_channel_config)

    if not input_channels_entities:
        logger.error("No input channels found, exiting")
        sys.exit(1)

    def process_message_text(event, mention_everyone: bool, override_mention_everyone: bool) -> str:
        """Process the message text and return the processed text."""
        message_text = event.message.message

        if mention_everyone or override_mention_everyone:
            message_text += '\n' + '@everyone'

        return telegram_entities_to_markdown(message_text, event.message.entities)

    async def forward_to_discord(discord_channel, message_text: str,
                                 image_file=None, reference=None):
        """Send a message to Discord."""
        sent_messages = []
        message_parts = split_message(message_text)
        if image_file:
            discord_file = discord.File(image_file)
            sent_message = await discord_channel.send(message_parts[0],
                                                      file=discord_file,
                                                      reference=reference)
            sent_messages.append(sent_message)
            message_parts.pop(0)

        for part in message_parts:
            sent_message = await discord_channel.send(part, reference=reference)
            sent_messages.append(sent_message)

        return sent_messages

    async def process_url_message(discord_channel, message_text, discord_reference):
        """Process a message that contains a URL."""
        sent_discord_messages = await forward_to_discord(discord_channel,
                                                         message_text,
                                                         reference=discord_reference)
        return sent_discord_messages

    async def process_media_message(event, discord_channel, message_text, discord_reference):
        """Process a message that contains media."""
        file_path = await telegram_client.download_media(event.message)
        with open(file_path, "rb") as image_file:
            sent_discord_messages = await forward_to_discord(discord_channel,
                                                             message_text,
                                                             image_file=image_file,
                                                             reference=discord_reference)
        os.remove(file_path)
        return sent_discord_messages

    async def handle_message_media(event, discord_channel, message_text, discord_reference):
        """Handle a message that contains media."""
        contains_url = any(isinstance(entity, (MessageEntityTextUrl, MessageEntityUrl))
                           for entity in event.message.entities or [])

        if contains_url:
            sent_discord_messages = await process_url_message(discord_channel,
                                                              message_text,
                                                              discord_reference)
        else:
            sent_discord_messages = await process_media_message(event, discord_channel,
                                                                message_text,
                                                                discord_reference)

        return sent_discord_messages

    async def fetch_discord_reference(event, discord_channel):
        """Fetch the Discord message reference."""
        discord_message_id = get_discord_message_id(
            event.message.reply_to_msg_id)
        if not discord_message_id:
            logger.debug("No mapping found for TG message %s",
                         event.message.reply_to_msg_id)
            return None

        try:
            messages = []
            async for message in discord_channel.history(around=discord.Object(id=discord_message_id),   # pylint: disable=line-too-long
                                                         limit=10):
                messages.append(message)

            discord_message = next(
                (msg for msg in messages if msg.id == discord_message_id), None)
            if not discord_message:
                logger.debug(
                    "Reference Discord message not found for TG message %s",
                    event.message.reply_to_msg_id)
                return None

            return MessageReference.from_message(discord_message)
        except discord.NotFound:
            logger.debug("Reference Discord message not found for TG message %s",
                         event.message.reply_to_msg_id)
            return None

    def get_message_hashtags(message):
        """Get hashtags from a message."""
        entities = message.entities or []
        hashtags = [entity for entity in entities if isinstance(
            entity, MessageEntityHashtag)]

        return [message.text[hashtag.offset:hashtag.offset + hashtag.length] for hashtag in hashtags]   # pylint: disable=line-too-long

    @telegram_client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):
        """Handle new messages in the specified Telegram channels."""
        logger.debug(event)

        tg_channel_id = event.message.peer_id.channel_id
        discord_channel_config = discord_channel_mappings.get(tg_channel_id)

        if not discord_channel_config:
            logger.error(
                "Discord channel not found for Telegram channel %s", tg_channel_id)
            return

        discord_channel_id = discord_channel_config["discord_channel_id"]
        mention_everyone = discord_channel_config["mention_everyone"]
        forward_everything = discord_channel_config["forward_everything"]
        allowed_hashtags = discord_channel_config["hashtags"]

        should_override_mention_everyone = False
        should_forward_message = forward_everything

        if allowed_hashtags:
            message_hashtags = get_message_hashtags(event.message)

            matching_hashtags = [
                tag for tag in allowed_hashtags if tag["name"] in message_hashtags]

            if len(matching_hashtags) > 0:
                should_forward_message = True
                should_override_mention_everyone = any(tag.get("override_mention_everyone", False)
                                                       for tag in matching_hashtags)

        if not should_forward_message:
            return

        discord_channel = discord_client.get_channel(discord_channel_id)
        message_text = process_message_text(
            event, mention_everyone, should_override_mention_everyone)

        discord_reference = await fetch_discord_reference(event,
                                                          discord_channel) if event.message.reply_to_msg_id else None   # pylint: disable=line-too-long

        if event.message.media:
            sent_discord_messages = await handle_message_media(event,
                                                               discord_channel,
                                                               message_text,
                                                               discord_reference)
        else:
            sent_discord_messages = await forward_to_discord(discord_channel,
                                                             message_text,
                                                             reference=discord_reference)

        if sent_discord_messages:
            main_sent_discord_message = sent_discord_messages[0]
            save_mapping_data(event.message.id, main_sent_discord_message.id)
            logger.info("Forwarded TG message %s to Discord message %s",
                        event.message.id, main_sent_discord_message.id)

    try:
        await asyncio.wait_for(telegram_client.run_until_disconnected(), timeout=None)
    except asyncio.TimeoutError:
        logger.warning("Telegram client timeout reached. Disconnecting...")
        await telegram_client.disconnect()


async def start_discord(config):
    """Start the Discord client."""
    await discord_client.start(config["discord_bot_token"])


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


async def main():
    """Start the Telegram and Discord clients."""
    conf = load_config()

    coroutines = [start_telegram(config=conf), start_discord(config=conf)]
    coroutine_names = ['start_telegram', 'start_discord']

    for coroutine, coroutine_name in zip(asyncio.as_completed(coroutines), coroutine_names):
        try:
            await coroutine
        except (asyncio.CancelledError, RuntimeError) as ex:
            logger.error("Error occurred in %s: %s", coroutine_name, ex)


if __name__ == "__main__":
    asyncio.run(main())
