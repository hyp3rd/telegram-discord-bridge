"""A script to forward messages from Telegram channels to a Discord channel."""

import os
import sys
import asyncio
from typing import Any
import logging
import yaml
from telethon import TelegramClient, events
from telethon.tl.types import InputChannel
import discord

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logging.getLogger('telethon').setLevel(level=logging.WARNING)
logger = logging.getLogger(__name__)

messages = []
discord_client = discord.Client(intents=discord.Intents.default())

def load_config() -> Any:
    """Load configuration from the 'config.yml' file."""
    try:
        with open('config.yml', 'rb') as config_file:
            config_data = yaml.safe_load(config_file)
    except FileNotFoundError:
        logger.error("Error: Configuration file 'config.yml' not found.")
        sys.exit(-1)
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
        "discord_channel"
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
        api_hash=config["telegram_api_hash"],
        use_ipv6=False)

    await telegram_client.start(
        phone=config["telegram_phone"],
        password=config["telegram_password"])

    input_channels_entities = []

    async for dialog in telegram_client.iter_dialogs():
        if dialog.name in config["telegram_input_channels"] or dialog.entity.id in config["telegram_input_channels"]:
            input_channels_entities.append(InputChannel(dialog.entity.id, dialog.entity.access_hash))

    if not input_channels_entities:
        logger.error("No input channels found, exiting")
        sys.exit(1)


    @telegram_client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):
        """Handle new messages in the specified Telegram channels."""
        logger.debug(event)

        # Get the Discord channel
        discord_channel = discord_client.get_channel(config["discord_channel"])

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

                message_text = parsed_response + '\n' + '@everyone'
                contains_url = True
            else:
                message_text = "@everyone"
                contains_url = False

            # Send the image as an attachment to Discord along with the text if it doesn't contain a URL
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

            messages.append(parsed_response + '\n' + '@everyone')
            await discord_channel.send(messages.pop())


    async def background_task():
        """Send messages from the Telegram channels to the Discord channel."""
        await discord_client.wait_until_ready()
        discord_channel = discord_client.get_channel(config["discord_channel"])
        while True:
            if messages:
                logger.debug(messages)
                await discord_channel.send(messages.pop())
            await asyncio.sleep(1)  # Updated sleep time


    @discord_client.event
    async def on_ready():
        """Create a task for the background_task() function."""
        discord_client.loop.create_task(background_task())


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
    await asyncio.gather(start_telegram(config=conf), start_discord(config=conf))


if __name__ == "__main__":
    asyncio.run(main())
