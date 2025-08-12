"""A `bridge` to forward messages from Telegram to a Discord server."""

import asyncio
import os
import sys
from typing import List

import discord
from discord import Message as DiscordMessage
from telethon import TelegramClient, events
from telethon.tl.types import (
    Channel,
    InputChannel,
    Message,
    MessageEntityHashtag,
    MessageEntityTextUrl,
    MessageEntityUrl,
)

from bridge.config import Config, ForwarderConfig
from bridge.discord import DiscordHandler
from bridge.history import MessageHistoryHandler
from bridge.logger import Logger
from bridge.openai.handler import OpenAIHandler
from bridge.utils import telegram_entities_to_markdown
from bridge.stats import StatsTracker

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class Bridge:
    """Bridge between Telegram and Discord."""

    def __init__(self, telegram_client: TelegramClient, discord_client: discord.Client):
        self.telegram_client = telegram_client
        self.discord_client = discord_client
        self.discord_handler = DiscordHandler()
        self.history_manager = MessageHistoryHandler()
        self.input_channels_entities = []

        logger.debug("Forwarders: %s", config.telegram_forwarders)

    async def start(self):
        """Start the bridge."""
        await self._register_forwarders()
        await self._register_telegram_handlers()

        # @self.telegram_client.on(events.NewMessage(chats=self.input_channels_entities))
        # async def handler(self, event):
        #     """Handle new messages in the specified Telegram channels."""
        #     if config.discord.is_healthy is False and config.application.internet_connected is True:
        #         # await add_to_queue(event)
        #         return

        #     await self.handle_new_message(event)
        # self.discord_client.add_listener(self._handle_discord_message, "on_message")

    async def _register_forwarders(self):
        """Register the forwarders."""
        logger.info("Registering forwarders...")

        if not self.telegram_client.is_connected():
            logger.warning("Telegram client not connected, retrying...")
            await asyncio.sleep(1)
            await self._register_forwarders()
            return

        logger.debug("Iterating dialogs...")
        try:
            async for dialog in self.telegram_client.iter_dialogs():
                if not isinstance(dialog.entity, Channel) and not isinstance(
                    dialog.entity, InputChannel
                ):
                    if config.telegram.log_unhandled_dialogs:
                        logger.warning(
                            "Excluded dialog name: %s, id: %s, type: %s",
                            dialog.name,
                            dialog.entity.id,
                            type(dialog.entity),
                        )
                    continue

                for forwarder in config.telegram_forwarders:
                    # type: ignore
                    if forwarder.tg_channel_id in {dialog.name, dialog.entity.id}:
                        self.input_channels_entities.append(
                            InputChannel(dialog.entity.id, dialog.entity.access_hash)
                        )  # type: ignore

                        logger.info(
                            "Registered Forwarder %s: Telegram channel '%s' (ID %s) with Discord Channel %s",
                            forwarder.forwarder_name,
                            dialog.name,
                            dialog.entity.id,
                            forwarder.discord_channel_id,
                        )  # type: ignore

            if len(self.input_channels_entities) <= 0:
                logger.error("No channel matching found, exiting...")
                sys.exit(1)

        except Exception as ex:  # pylint: disable=broad-except
            logger.error("Error while registering forwarders: %s", ex)
            sys.exit(1)

    async def _register_telegram_handlers(self):
        """Register the Telegram handlers."""
        logger.info("Registering Telegram handlers...")
        self.telegram_client.add_event_handler(
            self._handle_new_message,
            events.NewMessage(chats=self.input_channels_entities),
        )

        if config.telegram.subscribe_to_edit_events:
            self.telegram_client.add_event_handler(
                self._handle_edit_message,
                events.MessageEdited(chats=self.input_channels_entities),
            )
            logger.info("Subscribed to Telegram edit events")

        if config.telegram.subscribe_to_delete_events:
            self.telegram_client.add_event_handler(
                self._handle_deleted_message,
                events.MessageDeleted(chats=self.input_channels_entities),
            )
            logger.info("Subscribed to Telegram delete events")

    async def _handle_new_message(
        self, event
    ):  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
        """Handle the processing of a new Telegram message."""
        logger.debug("processing Telegram message: %s", event)

        if not isinstance(event.message, Message):
            logger.error("Event message is not a Telegram message")
            return

        message: Message = event.message

        logger.debug("message: %s", message)
        # logger.debug("message with markdown: %s", message.text)

        tg_channel_id = message.peer_id.channel_id  # type: ignore

        if config.application.anti_spam_enabled:
            # check for duplicate messages
            if await self.history_manager.spam_filter(
                telegram_message=message,
                channel_id=tg_channel_id,
                tgc=self.telegram_client,
            ):
                logger.debug("Duplicate message found, skipping...")
                return

        matching_forwarders: List[ForwarderConfig] = self.get_matching_forwarders(
            tg_channel_id
        )

        if len(matching_forwarders) < 1:
            logger.error("No forwarders found for Telegram channel %s", tg_channel_id)
            return

        logger.debug("Found %s matching forwarders", len(matching_forwarders))
        logger.debug("Matching forwarders: %s", matching_forwarders)

        for forwarder in matching_forwarders:
            logger.debug("Forwarder config: %s", forwarder)

            should_forward_message = forwarder.forward_everything
            mention_everyone = forwarder.mention_everyone
            message_forward_hashtags: List[str] = []

            if not should_forward_message or forwarder.mention_override:
                message_forward_hashtags = self.get_message_forward_hashtags(message)

                logger.debug("message_forward_hashtags: %s", message_forward_hashtags)

                logger.debug("mention_override: %s", forwarder.mention_override)

                logger.debug("forward_hashtags: %s", forwarder.forward_hashtags)

                matching_forward_hashtags = []

                if message_forward_hashtags and forwarder.forward_hashtags:
                    matching_forward_hashtags = [
                        tag
                        for tag in forwarder.forward_hashtags
                        if tag["name"].lower() in message_forward_hashtags
                    ]

                if len(matching_forward_hashtags) > 0:
                    should_forward_message = True
                    mention_everyone = any(
                        tag.get("override_mention_everyone", False)
                        for tag in matching_forward_hashtags
                    )

            if forwarder.excluded_hashtags:
                message_forward_hashtags = self.get_message_forward_hashtags(message)

                matching_forward_hashtags = [
                    tag
                    for tag in forwarder.excluded_hashtags
                    if tag["name"].lower() in message_forward_hashtags
                ]

                if len(matching_forward_hashtags) > 0:
                    should_forward_message = False

            if not should_forward_message:
                continue

            discord_channel = self.discord_client.get_channel(
                forwarder.discord_channel_id
            )  # type: ignore
            server_roles = discord_channel.guild.roles  # type: ignore

            mention_roles = self.discord_handler.get_mention_roles(
                message_forward_hashtags,
                forwarder.mention_override,
                config.discord.built_in_roles,
                server_roles,
            )

            message_text = await self.process_message_text(
                message,
                forwarder.strip_off_links,
                mention_everyone,
                mention_roles,
                config.openai.enabled,
            )

            if message.reply_to and message.reply_to.reply_to_msg_id:
                discord_reference = (
                    await self.discord_handler.fetch_reference(
                        message, forwarder.forwarder_name, discord_channel
                    )
                    if message.reply_to.reply_to_msg_id
                    else None
                )
            else:
                discord_reference = None

            if message.media:
                sent_discord_messages = await self.handle_message_media(
                    message, discord_channel, message_text, discord_reference
                )
            else:
                sent_discord_messages = await self.discord_handler.forward_message(
                    discord_channel,  # type: ignore
                    message_text,
                    reference=discord_reference,
                )  # type: ignore

            if sent_discord_messages:
                logger.debug(
                    "Forwarded TG message %s to Discord channel %s",
                    sent_discord_messages[0].id,
                    forwarder.discord_channel_id,
                )

                logger.debug(
                    "Saving mapping data for forwarder %s", forwarder.forwarder_name
                )
                main_sent_discord_message = sent_discord_messages[0]
                await self.history_manager.save_mapping_data(
                    forwarder.forwarder_name, message.id, main_sent_discord_message.id
                )
                StatsTracker().increment(forwarder.forwarder_name)
                logger.info(
                    "Forwarded TG message %s to Discord message %s",
                    message.id,
                    main_sent_discord_message.id,
                )
            else:
                await self.history_manager.save_missed_message(
                    forwarder.forwarder_name,
                    message.id,
                    forwarder.discord_channel_id,
                    None,
                )
                logger.error(
                    "Failed to forward TG message %s to Discord",
                    message.id,
                    exc_info=config.application.debug,
                )

    async def _handle_edit_message(self, event):
        """Handle the processing of a Telegram edited message."""
        logger.debug("processing Telegram edited message event: %s", event)

        if event.message is None:
            logger.debug("No Telegram message found, skipping...")
            return

        tg_channel_id = event.original_update.message.peer_id.channel_id
        tg_message_id = event.message.id
        tg_message_text = event.message.message

        logger.debug(
            "Editing message id %s from Telegram channel_id: %s",
            tg_message_id,
            tg_channel_id,
        )

        matching_forwarders: List[ForwarderConfig] = self.get_matching_forwarders(
            tg_channel_id
        )

        if len(matching_forwarders) < 1:
            logger.error("No forwarders found for Telegram channel %s", tg_channel_id)
            return

        for forwarder in matching_forwarders:
            logger.debug("Forwarder config: %s", forwarder)

            discord_message_id = await self.history_manager.get_discord_message_id(
                forwarder.forwarder_name, tg_message_id
            )

            if discord_message_id is None:
                logger.debug(
                    "No Discord message found for Telegram message %s", tg_message_id
                )
                continue

            logger.debug("Discord message ID: %s", discord_message_id)

            discord_channel = self.discord_client.get_channel(
                forwarder.discord_channel_id
            )

            if discord_channel is None:
                logger.error("Discord channel not found, skipping...")
                continue

            logger.debug("Discord channel: %s", discord_channel)

            try:
                # type: ignore
                discord_message = await discord_channel.fetch_message(
                    discord_message_id
                )

                if discord_message is None:
                    logger.error("Discord message not found, skipping...")
                    continue

                logger.debug("Discord message: %s", discord_message)

                await discord_message.edit(content=tg_message_text)
            except discord.NotFound:
                logger.error("Discord message not found, skipping...")
                return
            except discord.Forbidden:
                logger.error("Insufficient permissions to edit a message on Discord...")
                return
            except discord.HTTPException as ex:
                logger.error(
                    "Error while editing Discord message: %s",
                    ex,
                    exc_info=config.application.debug,
                )
                return

    async def _handle_deleted_message(self, event):
        """Handle the deletion of a Telegram message."""
        logger.debug("processing Telegram deleted message event: %s", event)

        logger.debug("Deleted messages: %s", event.deleted_ids)
        logger.debug("Telegram channel_id: %s", event.original_update.channel_id)

        tg_channel_id = event.original_update.channel_id

        matching_forwarders: List[ForwarderConfig] = self.get_matching_forwarders(
            tg_channel_id
        )

        if len(matching_forwarders) < 1:
            logger.error("No forwarders found for Telegram channel %s", tg_channel_id)
            return

        for forwarder in matching_forwarders:
            logger.debug("Forwarder config: %s", forwarder)

            for deleted_id in event.deleted_ids:
                discord_message_id = await self.history_manager.get_discord_message_id(
                    forwarder.forwarder_name, deleted_id
                )

                if discord_message_id is None:
                    logger.debug(
                        "No Discord message found for Telegram message %s", deleted_id
                    )
                    continue

                logger.debug("Discord message ID: %s", discord_message_id)

                discord_channel = self.discord_client.get_channel(
                    forwarder.discord_channel_id
                )

                if discord_channel is None:
                    logger.error(
                        "Discord channel %s not found", forwarder.discord_channel_id
                    )
                    return

                try:
                    # type: ignore
                    discord_message = await discord_channel.fetch_message(
                        discord_message_id
                    )
                except discord.errors.NotFound:
                    logger.debug("Discord message %s not found", discord_message_id)
                    return

                logger.debug("Discord message: %s", discord_message)

                try:
                    await discord_message.delete()
                except discord.errors.NotFound:
                    logger.debug(
                        "Discord message %s not found",
                        discord_message_id,
                        exc_info=config.application.debug,
                    )
                    return
                except discord.errors.Forbidden:
                    logger.error(
                        "Discord forbade deleting message %s",
                        discord_message_id,
                        exc_info=config.application.debug,
                    )
                    return
                except discord.errors.HTTPException as ex:
                    logger.error(
                        "Failed deleting message %s: %s",
                        discord_message_id,
                        ex,
                        exc_info=config.application.debug,
                    )
                    return

    def get_matching_forwarders(self, tg_channel_id: int) -> List[ForwarderConfig]:
        """Get the forwarders that match the given Telegram channel ID."""
        return [
            forwarder_config
            for forwarder_config in config.telegram_forwarders
            if tg_channel_id == forwarder_config["tg_channel_id"]
        ]  # pylint: disable=line-too-long

    @staticmethod
    def get_message_forward_hashtags(message: Message):
        """Get forward_hashtags from a message."""
        if not message.entities:
            return []
        entities = message.entities or []
        forward_hashtags = [
            entity for entity in entities if isinstance(entity, MessageEntityHashtag)
        ]

        return [
            message.message[hashtag.offset : hashtag.offset + hashtag.length]
            for hashtag in forward_hashtags
        ]  # pylint: disable=line-too-long

    @staticmethod
    async def process_message_text(
        message: Message,
        strip_off_links: bool,
        mention_everyone: bool,
        mention_roles: List[str],
        openai_enabled: bool,
    ) -> str:  # pylint: disable=too-many-arguments
        """Process the message text and return the processed text."""

        if message.entities:
            message_text = telegram_entities_to_markdown(message, strip_off_links)
        else:
            message_text = message.message

        if openai_enabled:
            suggestions = await OpenAIHandler().analyze_message_sentiment(
                message.message
            )
            message_text = f"{message_text}\n{suggestions}"

        if mention_everyone:
            message_text += "\n" + "@everyone"

        if mention_roles:
            mention_text = ", ".join(role for role in mention_roles)
            message_text = f"{mention_text}\n{message_text}"

        return message_text

    async def process_media_message(
        self, message: Message, discord_channel, message_text, discord_reference
    ) -> List[DiscordMessage] | None:
        """Process a message that contains media."""
        file_path = await self.telegram_client.download_media(message)
        try:
            with open(file_path, "rb") as image_file:  # type: ignore
                sent_discord_messages = await self.discord_handler.forward_message(
                    discord_channel,
                    message_text,
                    image_file=image_file,
                    reference=discord_reference,
                )
                if not sent_discord_messages:
                    logger.error("Failed to send message to Discord")
                    return

        except OSError as ex:
            logger.error(
                "An error occurred while opening the file %s: %s", file_path, ex
            )
            return
        finally:
            os.remove(file_path)  # type: ignore

        return sent_discord_messages

    async def handle_message_media(
        self, message: Message, discord_channel, message_text, discord_reference
    ) -> List[DiscordMessage] | None:
        """Handle a message that contains media."""
        contains_url = any(
            isinstance(entity, (MessageEntityTextUrl, MessageEntityUrl))
            for entity in message.entities or []
        )

        sent_discord_messages: List[DiscordMessage] | None = None

        if contains_url:
            sent_discord_messages = await self.process_url_message(
                discord_channel, message_text, discord_reference
            )
        else:
            sent_discord_messages = await self.process_media_message(
                message, discord_channel, message_text, discord_reference
            )

        return sent_discord_messages

    async def process_url_message(
        self, discord_channel, message_text, discord_reference
    ) -> List[DiscordMessage]:
        """Process a message that contains a URL."""
        sent_discord_messages = await self.discord_handler.forward_message(
            discord_channel, message_text, reference=discord_reference
        )
        return sent_discord_messages

    async def on_restored_connectivity(self):
        """Check and restore internet connectivity."""
        logger.debug("Checking for internet connectivity")
        while True:
            if (
                config.application.internet_connected
                and config.telegram.is_healthy is True
            ):
                logger.debug(
                    "Internet connection active and Telegram is connected, checking for missed messages"
                )
                try:
                    last_messages = (
                        await self.history_manager.get_last_messages_for_all_forwarders()
                    )

                    logger.debug("Last forwarded messages: %s", last_messages)

                    for last_message in last_messages:
                        forwarder_name = last_message["forwarder_name"]
                        last_tg_message_id = last_message["telegram_id"]

                        channel_id = config.get_telegram_channel_by_forwarder_name(
                            forwarder_name
                        )

                        if channel_id:
                            fetched_messages = (
                                await self.history_manager.fetch_messages_after(
                                    last_tg_message_id, channel_id, self.telegram_client
                                )
                            )
                            for fetched_message in fetched_messages:
                                logger.debug(
                                    "Recovered message %s from channel %s",
                                    fetched_message.id,
                                    channel_id,
                                )
                                event = events.NewMessage.Event(message=fetched_message)
                                event.peer = await self.telegram_client.get_input_entity(  # type: ignore
                                    channel_id
                                )

                                if config.discord.is_healthy is False:
                                    logger.warning(
                                        "Discord is not available despite the connectivty is restored, queing TG message %s",
                                        event.message.id,
                                    )
                                    # await add_to_queue(event)
                                    continue
                                # delay the message delivery to avoid rate limit and flood
                                await asyncio.sleep(config.application.recoverer_delay)
                                logger.debug(
                                    "Forwarding recovered Telegram message %s",
                                    event.message.id,
                                )
                                await self._handle_new_message(event)

                except Exception as exception:  # pylint: disable=broad-except
                    logger.error(
                        "Failed to fetch missed messages: %s",
                        exception,
                        exc_info=config.application.debug,
                    )

            logger.debug(
                "on_restored_connectivity will trigger again in for %s seconds",
                config.application.healthcheck_interval,
            )
            await asyncio.sleep(config.application.healthcheck_interval)
