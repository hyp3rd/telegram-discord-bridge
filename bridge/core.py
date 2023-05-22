"""A `bridge` to forward messages from Telegram to a Discord server."""

import asyncio
import sys

import discord
from telethon import TelegramClient, events
from telethon.tl.types import Channel, InputChannel

from bridge.config import Config
from bridge.discord_handler import (fetch_discord_reference,
                                    forward_to_discord, get_mention_roles)
from bridge.history import MessageHistoryHandler
from bridge.logger import Logger
from bridge.telegram_handler import (get_message_forward_hashtags,
                                     handle_message_media,
                                     process_message_text)

tg_to_discord_message_ids = {}
discord_channel_mappings = {}

logger = Logger.get_logger(Config().app.name)
history_manager = MessageHistoryHandler()

queued_events = asyncio.Queue()
queued_event_ids = set()  # Set to store the IDs of queued events


async def add_to_queue(event):
    """Add unique events to the queue."""
    event_id = event.message.id  # This assumes that event.message.id is unique for each event
    if event_id not in queued_event_ids:
        await queued_events.put(event)
        queued_event_ids.add(event_id)  # Add the event ID to the set
        logger.info("Added event with ID %s to the queue", event_id)
    else:
        logger.info(
            "Event with ID %s is already in the queue, skipping", event_id)


async def start(telegram_client: TelegramClient, discord_client: discord.Client, config: Config):
    """Start the bridge."""
    logger.info("Starting the bridge...")

    input_channels_entities = []

    async for dialog in telegram_client.iter_dialogs():
        if not isinstance(dialog.entity, Channel) and not isinstance(dialog.entity, InputChannel):
            if config.app.debug:
                logger.warning("Excluded dialog name: %s, id: %s",
                               dialog.name, dialog.entity.id)
            continue

        logger.debug("Available channel: %s, id: %s",
                     dialog.name, dialog.entity.id)

        for channel_mapping in config.telegram_forwarders:
            forwarder_name = channel_mapping["forwarder_name"]
            tg_channel_id = channel_mapping["tg_channel_id"]
            mention_override = channel_mapping.get("mention_override", [])
            mention_override = {override["tag"].lower(
            ): override["roles"] for override in mention_override}

            discord_channel_config = {
                "discord_channel_id": channel_mapping["discord_channel_id"],
                "strip_off_links": channel_mapping["strip_off_links"],
                "mention_everyone": channel_mapping["mention_everyone"],
                "forward_everything": channel_mapping.get("forward_everything", False),
                "forward_hashtags": channel_mapping.get("forward_hashtags", []),
                "excluded_hashtags": channel_mapping.get("excluded_hashtags", []),
                "mention_override": mention_override,
                "roles": channel_mapping.get("roles", []),
            }

            if tg_channel_id in {dialog.name, dialog.entity.id}:  # type: ignore
                input_channels_entities.append(
                    InputChannel(dialog.entity.id, dialog.entity.access_hash))  # type: ignore
                discord_channel_mappings[forwarder_name] = discord_channel_config
                logger.info("Registered TG channel '%s' with ID %s with Discord channel config %s",
                            dialog.name, dialog.entity.id, discord_channel_config)  # type: ignore

    if not input_channels_entities:
        logger.error("No input channels found, exiting")
        sys.exit(1)

    async def dispatch_queued_events():
        """Dispatch queued events to Discord."""
        while not queued_events.empty():
            event = await queued_events.get()
            event_id = event.message.id
            logger.info("Dispatching queued TG message")
            await handle_new_message(event, config, telegram_client, discord_client)
            # Remove the event ID from the set
            queued_event_ids.remove(event_id)
            queued_events.task_done()

    # Create tasks for dispatch_queued_events and handle_restored_internet_connectivity
    dispatch_task = asyncio.create_task(dispatch_queued_events())

    @telegram_client.on(events.NewMessage(chats=input_channels_entities))
    async def handler(event):
        """Handle new messages in the specified Telegram channels."""
        if config.status["discord_available"] is False and config.status["internet_connected"] is True:
            await add_to_queue(event)
            return

        event_id = event.message.id
        if event_id in queued_event_ids:
            # If the event was previously queued but Discord is now available, remove it from the set
            queued_event_ids.remove(event_id)

        await asyncio.gather(dispatch_task, handle_new_message(event, config, telegram_client, discord_client))


async def handle_new_message(event, config: Config, telegram_client: TelegramClient, discord_client: discord.Client):  # pylint: disable=too-many-locals
    """Handle the processing of a new Telegram message."""
    logger.debug("processing Telegram message: %s", event.message.id)

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
                "Discord channel not found for Telegram channel %s", tg_channel_id, exc_info=True)
            continue

        discord_channel_id = discord_channel_config["discord_channel_id"]

        forwarder_config = {
            "mention_everyone": discord_channel_config["mention_everyone"],
            "strip_off_links": discord_channel_config["strip_off_links"],
            "forward_everything": discord_channel_config["forward_everything"],
            "allowed_forward_hashtags": discord_channel_config["forward_hashtags"],
            "disallowed_hashtags": discord_channel_config["excluded_hashtags"],
            "mention_override": discord_channel_config["mention_override"],
            "roles": discord_channel_config["roles"],
        }

        should_forward_message = forwarder_config["forward_everything"]
        mention_everyone = forwarder_config["mention_everyone"]
        strip_off_links = forwarder_config["strip_off_links"]
        mention_roles = []
        message_forward_hashtags = []

        logger.debug("strip_off_links: %s", strip_off_links)

        if forwarder_config["allowed_forward_hashtags"] or forwarder_config["mention_override"]:
            message_forward_hashtags = get_message_forward_hashtags(
                event.message)

            matching_forward_hashtags = [
                tag for tag in forwarder_config["allowed_forward_hashtags"] if tag["name"].lower() in message_forward_hashtags]

            if len(matching_forward_hashtags) > 0:
                should_forward_message = True
                mention_everyone = any(tag.get("override_mention_everyone", False)
                                       for tag in matching_forward_hashtags)

        if forwarder_config["disallowed_hashtags"]:
            message_forward_hashtags = get_message_forward_hashtags(
                event.message)

            matching_forward_hashtags = [
                tag for tag in forwarder_config["disallowed_hashtags"] if tag["name"].lower() in message_forward_hashtags]

            if len(matching_forward_hashtags) > 0:
                should_forward_message = False

        if not should_forward_message:
            continue

        discord_channel = discord_client.get_channel(discord_channel_id)
        server_roles = discord_channel.guild.roles  # type: ignore

        mention_roles = get_mention_roles(message_forward_hashtags,
                                          discord_channel_config["mention_override"],
                                          config.discord.built_in_roles,
                                          server_roles)

        message_text = await process_message_text(
            event, forwarder_config, mention_everyone, mention_roles, config.openai.enabled)

        discord_reference = await fetch_discord_reference(event,
                                                          forwarder_name,
                                                          discord_channel) if event.message.reply_to_msg_id else None

        if event.message.media:
            sent_discord_messages = await handle_message_media(telegram_client, event,
                                                               discord_channel,
                                                               message_text,
                                                               discord_reference)
        else:
            sent_discord_messages = await forward_to_discord(discord_channel,  # type: ignore
                                                             message_text,
                                                             reference=discord_reference)  # type: ignore

        if sent_discord_messages:
            logger.debug("Forwarded TG message %s to Discord channel %s",
                         sent_discord_messages[0].id, discord_channel_id)

            logger.debug("Saving mapping data for forwarder %s",
                         forwarder_name)
            main_sent_discord_message = sent_discord_messages[0]
            await history_manager.save_mapping_data(forwarder_name, event.message.id,
                                                    main_sent_discord_message.id)
            logger.info("Forwarded TG message %s to Discord message %s",
                        event.message.id, main_sent_discord_message.id)
        else:
            await history_manager.save_missed_message(forwarder_name,
                                                      event.message.id,
                                                      discord_channel_id,
                                                      None)
            logger.error("Failed to forward TG message %s to Discord",
                         event.message.id, exc_info=config.app.debug)


def get_matching_forwarders(tg_channel_id, config: Config):
    """Get the forwarders that match the given Telegram channel ID."""
    return [forwarder_config for forwarder_config in config.telegram_forwarders if tg_channel_id == forwarder_config["tg_channel_id"]]  # pylint: disable=line-too-long


async def on_restored_connectivity(config: Config, telegram_client: TelegramClient, discord_client: discord.Client):
    """Check and restore internet connectivity."""
    logger.debug("Checking for internet connectivity")

    if config.status["internet_connected"] and config.status["telegram_available"] is True:
        logger.debug(
            "Internet connection active and Telegram is connected, checking for missed messages")
        try:
            last_messages = await history_manager.get_last_messages_for_all_forwarders()

            logger.debug("Last forwarded messages: %s", last_messages)

            for last_message in last_messages:
                forwarder_name = last_message["forwarder_name"]
                last_tg_message_id = last_message["telegram_id"]

                channel_id = config.get_telegram_channel_by_forwarder_name(
                    forwarder_name)

                if channel_id:
                    fetched_messages = await history_manager.fetch_messages_after(last_tg_message_id,
                                                                                  channel_id,
                                                                                  telegram_client)
                    for fetched_message in fetched_messages:

                        logger.debug(
                            "Recovered message %s from channel %s", fetched_message.id, channel_id)
                        event = events.NewMessage.Event(
                            message=fetched_message)
                        event.peer = await telegram_client.get_input_entity(
                            channel_id)

                        if config.status["discord_available"] is False:
                            logger.warning("Discord is not available despite the connectivty is restored, queing TG message %s",
                                           event.message.id)
                            await add_to_queue(event)
                            continue
                        # delay the message delivery to avoid rate limit and flood
                        await asyncio.sleep(config.app.recoverer_delay)
                        logger.debug(
                            "Forwarding recovered Telegram message %s", event.message.id)
                        await handle_new_message(event, config,
                                                 telegram_client,
                                                 discord_client)

        except Exception as exception:  # pylint: disable=broad-except
            logger.error(
                "Failed to fetch missed messages: %s", exception, exc_info=config.app.debug)

    logger.debug("on_restored_connectivity will trigger again in for %s seconds",
                 config.app.healthcheck_interval)
    await asyncio.sleep(config.app.healthcheck_interval)
    await on_restored_connectivity(config, telegram_client, discord_client)
