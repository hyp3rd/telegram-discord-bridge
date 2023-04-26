"""A `Bot` to forward messages from Telegram to a Discord server."""

import asyncio
import signal
import sys
from typing import Tuple

import discord
from telethon import TelegramClient, events
from telethon.tl.types import Channel, InputChannel

from config import Config
from discord_handler import (fetch_discord_reference, forward_to_discord,
                             get_mention_roles, start_discord)
from logger import app_logger
from telegram_handler import (get_message_forward_hashtags,
                              handle_message_media, process_message_text,
                              start_telegram_client)
from utils import save_mapping_data

tg_to_discord_message_ids = {}

logger = app_logger()


async def start(telegram_client: TelegramClient, discord_client: discord.Client, config: Config):   # pylint: disable=too-many-statements
    """Start the bot."""
    logger.info("Starting the bot...")

    input_channels_entities = []
    discord_channel_mappings = {}

    async for dialog in telegram_client.iter_dialogs():
        if not isinstance(dialog.entity, Channel) and not isinstance(dialog.entity, InputChannel):
            continue

        for channel_mapping in config.telegram_forwarders:
            forwarder_name = channel_mapping["forwarder_name"]
            tg_channel_id = channel_mapping["tg_channel_id"]
            mention_override = channel_mapping.get("mention_override", [])
            mention_override = {override["tag"].lower(
            ): override["roles"] for override in mention_override}

            discord_channel_config = {
                "discord_channel_id": channel_mapping["discord_channel_id"],
                "mention_everyone": channel_mapping["mention_everyone"],
                "forward_everything": channel_mapping.get("forward_everything", False),
                "forward_hashtags": channel_mapping.get("forward_hashtags", []),
                "mention_override": mention_override,
                "roles": channel_mapping.get("roles", []),
            }

            if tg_channel_id in {dialog.name, dialog.entity.id}:
                input_channels_entities.append(
                    InputChannel(dialog.entity.id, dialog.entity.access_hash))
                discord_channel_mappings[forwarder_name] = discord_channel_config
                logger.info("Registered TG channel '%s' with ID %s with Discord channel config %s",
                            dialog.name, dialog.entity.id, discord_channel_config)

    if not input_channels_entities:
        logger.error("No input channels found, exiting")
        sys.exit(1)

    @telegram_client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):  # pylint: disable=too-many-locals
        """Handle new messages in the specified Telegram channels."""
        logger.debug(event)

        tg_channel_id = event.message.peer_id.channel_id

        matching_forwarders = get_matching_forwarders(tg_channel_id, config)

        if len(matching_forwarders) < 1:
            logger.error(
                "No forwarders found for Telegram channel %s", tg_channel_id)
            return

        for discord_channel_config in matching_forwarders:
            forwarder_name = discord_channel_config["forwarder_name"]
            discord_channel_config = discord_channel_mappings.get(
                forwarder_name)

            if not discord_channel_config:
                logger.error(
                    "Discord channel not found for Telegram channel %s", tg_channel_id)
                continue

            discord_channel_id = discord_channel_config["discord_channel_id"]

            config_data = {
                "mention_everyone": discord_channel_config["mention_everyone"],
                "forward_everything": discord_channel_config["forward_everything"],
                "allowed_forward_hashtags": discord_channel_config["forward_hashtags"],
                "mention_override": discord_channel_config["mention_override"],
                "roles": discord_channel_config["roles"],
            }

            should_forward_message = config_data["forward_everything"]
            mention_everyone = config_data["mention_everyone"]
            mention_roles = []

            if config_data["allowed_forward_hashtags"]:
                message_forward_hashtags = get_message_forward_hashtags(
                    event.message)

                matching_forward_hashtags = [
                    tag for tag in config_data["allowed_forward_hashtags"] if tag["name"].lower() in message_forward_hashtags]

                if len(matching_forward_hashtags) > 0:
                    should_forward_message = True
                    mention_everyone = any(tag.get("override_mention_everyone", False)
                                           for tag in matching_forward_hashtags)

            if not should_forward_message:
                continue

            discord_channel = discord_client.get_channel(discord_channel_id)
            server_roles = discord_channel.guild.roles

            mention_roles = get_mention_roles(message_forward_hashtags,
                                              discord_channel_config["mention_override"],
                                              config.discord.built_in_roles,
                                              server_roles)

            message_text = await process_message_text(
                event, mention_everyone, False, mention_roles, config=config)

            discord_reference = await fetch_discord_reference(event,
                                                              discord_channel) if event.message.reply_to_msg_id else None

            if event.message.media:
                sent_discord_messages = await handle_message_media(telegram_client, event,
                                                                   discord_channel,
                                                                   message_text,
                                                                   discord_reference)
            else:
                sent_discord_messages = await forward_to_discord(discord_channel,
                                                                 message_text,
                                                                 reference=discord_reference)

            if sent_discord_messages:
                main_sent_discord_message = sent_discord_messages[0]
                save_mapping_data(event.message.id,
                                  main_sent_discord_message.id)
                logger.info("Forwarded TG message %s to Discord message %s",
                            event.message.id, main_sent_discord_message.id)


def get_matching_forwarders(tg_channel_id, config: Config):
    """Get the forwarders that match the given Telegram channel ID."""
    return [forwarder_config for forwarder_config in config.telegram_forwarders if tg_channel_id == forwarder_config["tg_channel_id"]]  # pylint: disable=line-too-long


async def on_shutdown(telegram_client, discord_client):
    """Shutdown the bot."""
    logger.info("Starting shutdown process...")
    task = asyncio.current_task()
    all_tasks = asyncio.all_tasks()

    try:
        logger.info("Disconnecting Telegram client...")
        await telegram_client.disconnect()
        logger.info("Telegram client disconnected.")
    except (Exception, asyncio.CancelledError) as ex:  # pylint: disable=broad-except
        logger.error("Error disconnecting Telegram client: %s", {ex})

    try:
        logger.info("Disconnecting Discord client...")
        await discord_client.close()
        logger.info("Discord client disconnected.")
    except (Exception, asyncio.CancelledError) as ex:  # pylint: disable=broad-except
        logger.error("Error disconnecting Discord client: %s", {ex})

    for running_task in all_tasks:
        if running_task is not task:
            task.cancel()

    logger.info("Shutdown process completed.")


async def shutdown(sig, tasks_loop: None):
    """Shutdown the application gracefully."""
    logger.warning("shutdown received signal %s, shutting down...", {sig})
    tasks = [task for task in asyncio.all_tasks(
    ) if task is not asyncio.current_task()]

    for task in tasks:
        task.cancel()

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for result in results:
        if isinstance(result, asyncio.CancelledError):
            continue
        if isinstance(result, Exception):
            logger.error("Error during shutdown: %s", result)

    if tasks_loop is not None:
        tasks_loop.stop()


async def handle_signal(sig, tgc: TelegramClient, dcl: discord.Client, tasks):
    """Handle graceful shutdown on received signal."""
    logger.warning("Received signal %s, shutting down...", {sig})

    # Disconnect clients
    if tgc.is_connected():
        await tgc.disconnect()
    if dcl.is_ready():
        await dcl.close()

    # Cancel all tasks
    await asyncio.gather(*tasks, return_exceptions=True)


async def run_bot(config: Config) -> Tuple[TelegramClient, discord.Client]:
    """Run the bot."""
    telegram_client_instance = await start_telegram_client(config)
    discord_client_instance = await start_discord(config)

    event_loop = asyncio.get_event_loop()

    # Set signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        event_loop.add_signal_handler(
            sig, lambda sig=sig: asyncio.create_task(shutdown(sig, tasks_loop=event_loop)))

    try:
        # Create tasks for starting the main logic and waiting for clients to disconnect
        start_task = asyncio.create_task(
            start(telegram_client_instance, discord_client_instance, config)
        )
        telegram_wait_task = asyncio.create_task(
            telegram_client_instance.run_until_disconnected()
        )
        discord_wait_task = asyncio.create_task(
            discord_client_instance.wait_until_ready()
        )

        await asyncio.gather(start_task, telegram_wait_task, discord_wait_task)
    except asyncio.CancelledError:
        logger.warning("CancelledError caught, shutting down...")
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error while running the bot: %s", ex)
    finally:
        await on_shutdown(telegram_client_instance, discord_client_instance)

    return telegram_client_instance, discord_client_instance


async def main(config: Config):
    """Run the bot."""
    client = ()
    try:
        client = await run_bot(config)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user, shutting down...")
    except asyncio.CancelledError:
        logger.warning("CancelledError caught, shutting down...")
    finally:
        if client:
            telegram_client, discord_client = client[0], client[1]
            if not telegram_client.is_connected() and not discord_client.is_ready():
                client = ()
            else:
                await on_shutdown(telegram_client, discord_client)
                client = ()


def event_loop_exception_handler(context):
    """Asyncio Event loop exception handler."""
    exception = context.get("exception")
    if not isinstance(exception, asyncio.CancelledError):
        loop.default_exception_handler(context)
    else:
        loop.warning("CancelledError caught during shutdown")


if __name__ == "__main__":
    app_config = Config()
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(event_loop_exception_handler)
    try:
        loop.run_until_complete(main(app_config))
    except asyncio.CancelledError:
        pass
