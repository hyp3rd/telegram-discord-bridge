"""A script to forward messages from Telegram channels to a Discord channel."""

import os
import sys
import asyncio
from typing import Any
import logging
import yaml
from telethon import TelegramClient, events
from telethon.tl.types import InputChannel, Channel, MessageEntityHashtag
import discord

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(level=logging.WARNING)
logger = logging.getLogger(__name__)

discord_client = discord.Client(intents=discord.Intents.default())

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
            logger.error("Error: Key '%s' not found in the configuration file.", key)
            sys.exit(1)

    return config_data


async def start_telegram(config):
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
        if not isinstance(dialog.entity, Channel):
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


    @telegram_client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):
        """Handle new messages in the specified Telegram channels."""
        logger.debug(event)

        # Get the corresponding Discord channel ID
        tg_channel_id = event.message.peer_id.channel_id
        discord_channel_config = discord_channel_mappings.get(tg_channel_id)

        if not discord_channel_config:
            logger.error("Discord channel not found for Telegram channel %s", tg_channel_id)
            return

        discord_channel_id = discord_channel_config["discord_channel_id"]
        mention_everyone = discord_channel_config["mention_everyone"]
        forward_everything = discord_channel_config["forward_everything"]
        allowed_hashtags = discord_channel_config["hashtags"]
        override_mention_everyone = False

        # Check if the message contains any of the allowed hashtags
        if allowed_hashtags:
            if event.message.entities:
                message_hashtags = {event.message.text[tag.offset:tag.offset + tag.length] for tag in event.message.entities if isinstance(tag, MessageEntityHashtag)}  # pylint: disable=line-too-long
            else:
                message_hashtags = set()

            matching_hashtags = [tag for tag in allowed_hashtags if tag["name"] in message_hashtags]
            if len(matching_hashtags) == 0 and not forward_everything:
                return

            override_mention_everyone = any(tag.get("override_mention_everyone", False) for tag in matching_hashtags)   # pylint: disable=line-too-long

        # Get the Discord channel
        discord_channel = discord_client.get_channel(discord_channel_id)

        # Check if the message contains media
        if event.message.media:
            # Download the media (image) from Telegram
            file_path = await telegram_client.download_media(event.message)

            # If the message also contains text
            if event.message.message:
                # If our entities contain URL, we want to parse and send Message + URL
                try:
                    parsed_response = event.message.message + '\n' + event.message.entities[0].url
                    parsed_response = ''.join(parsed_response)
                # Or else we only send Message
                except Exception:   # pylint: disable=broad-except
                    parsed_response = event.message.message

                message_text = parsed_response
                contains_url = True
            else:
                message_text = ""
                contains_url = False

            if mention_everyone or override_mention_everyone:
                message_text += '\n' + '@everyone'

            # Send the image as an attachment to Discord along with the text
            # if it doesn't contain a URL
            if not contains_url:
                with open(file_path, "rb") as image_file:
                    discord_file = discord.File(image_file)
                    await discord_channel.send(message_text, file=discord_file)
            else:
                await discord_channel.send(message_text)

            # Remove the downloaded file to clean up
            os.remove(file_path)

        else:
            # If our entities contain URL, we want to parse and send Message + URL
            try:
                parsed_response = event.message.message + '\n' + event.message.entities[0].url
                parsed_response = ''.join(parsed_response)
            # Or else we only send Message
            except Exception:   # pylint: disable=broad-except
                parsed_response = event.message.message

            if mention_everyone or override_mention_everyone:
                parsed_response += '\n' + '@everyone'

            await discord_channel.send(parsed_response)



    try:
        await asyncio.wait_for(telegram_client.run_until_disconnected(),
                               timeout=3600) # 1 hour
    except asyncio.TimeoutError:
        logger.warning("Telegram client timeout reached. Disconnecting...")
        await telegram_client.disconnect()


async def start_discord(config):
    """Start the Discord client."""
    await discord_client.start(config["discord_bot_token"])


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
