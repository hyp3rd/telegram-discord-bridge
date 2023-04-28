"""A `Bot` to bridge and forward messages from Telegram to a Discord server."""

import asyncio
import sys

import discord
from telethon import TelegramClient, events
from telethon.tl.types import Channel, InputChannel

from config import Config
from discord_handler import (fetch_discord_reference, forward_to_discord,
                             get_mention_roles)
from history import MessageHistoryManager
from logger import app_logger
from telegram_handler import (get_message_forward_hashtags,
                              handle_message_media, process_message_text)

tg_to_discord_message_ids = {}

logger = app_logger()
history_manager = MessageHistoryManager()

queued_events = asyncio.Queue()


async def start(telegram_client: TelegramClient, discord_client: discord.Client, config: Config):   # pylint: disable=too-many-statements
    """Start the bridge."""
    logger.info("Starting the bridge...")

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

    async def dispatch_queued_events():
        """Dispatch queued events to Discord."""
        while not queued_events.empty():
            event = await queued_events.get()

            logger.info("Dispatching queued TG message")
            await handle_new_message(event)
            queued_events.task_done()

    async def handle_restored_internet_connectivity():
        """Check and restore internet connectivity."""
        while True:  # pylint: disable=too-many-nested-blocks
            await asyncio.sleep(5)
            if config.status["internet_connected"] is True:
                logger.debug(
                    "Internet connection active, checking for missed messages")
                try:
                    last_messages = await history_manager.get_last_messages_for_all_forwarders()

                    for last_message in last_messages:
                        forwarder_name = last_message["forwarder_name"]
                        last_tg_message_id = last_message["telegram_id"]

                        channel_id = config.get_telegram_channel_by_forwarder_name(
                            forwarder_name)

                        if channel_id:
                            fetched_messages = await history_manager.fetch_messages_after(last_tg_message_id, channel_id, telegram_client)
                            for fetched_message in fetched_messages:

                                event = events.NewMessage.Event(
                                    message=fetched_message)
                                event.peer = telegram_client.get_input_entity(
                                    channel_id)

                                if config.status["discord_available"] is False:
                                    await queued_events.put(event)
                                else:
                                    await handle_new_message(event)
                except Exception as exception:  # pylint: disable=broad-except
                    logger.error(
                        "Failed to fetch missed messages: %s", exception)

    @telegram_client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):
        """Handle new messages in the specified Telegram channels."""
        if config.status["discord_available"] is False:
            logger.warning(
                "Discord is not available, queing TG message %s", event.message.id)
            await queued_events.put(event)
            return

        await asyncio.gather(dispatch_queued_events(), handle_new_message(event), handle_restored_internet_connectivity())
        # await handle_new_message(event)

    async def handle_new_message(event):  # pylint: disable=too-many-locals
        """Handle the processing of a new Telegram message."""
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

            if config_data["allowed_forward_hashtags"] or config_data["mention_override"]:
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
                                                              forwarder_name,
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
                await history_manager.save_mapping_data(forwarder_name, event.message.id,
                                                        main_sent_discord_message.id)
                logger.info("Forwarded TG message %s to Discord message %s",
                            event.message.id, main_sent_discord_message.id)


def get_matching_forwarders(tg_channel_id, config: Config):
    """Get the forwarders that match the given Telegram channel ID."""
    return [forwarder_config for forwarder_config in config.telegram_forwarders if tg_channel_id == forwarder_config["tg_channel_id"]]  # pylint: disable=line-too-long
