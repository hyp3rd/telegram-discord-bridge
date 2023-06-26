"""A `bridge` to forward messages from Telegram to a Discord server."""

import asyncio
import os
import sys
from typing import List

import discord
from discord import Message as DiscordMessage
from telethon import TelegramClient, events
from telethon.tl.types import (Channel, InputChannel, Message,
                               MessageEntityHashtag, MessageEntityTextUrl,
                               MessageEntityUrl)

from bridge.config import Config, ForwarderConfig
from bridge.discord import DiscordHandler
from bridge.history import MessageHistoryHandler
from bridge.logger import Logger
from bridge.openai.handler import OpenAIHandler
from bridge.utils import telegram_entities_to_markdown


class Bridge:
    """Bridge between Telegram and Discord."""
    config = Config.get_instance()
    logger = Logger.get_logger(config.application.name)

    def __init__(self, telegram_client: TelegramClient, discord_client: discord.Client):
        self.telegram_client = telegram_client
        self.discord_client = discord_client
        self.discord_handler = DiscordHandler()
        self.history_manager = MessageHistoryHandler()
        self.input_channels_entities = []

        self.logger.debug("Forwarders: %s", self.config.telegram_forwarders)


    async def start(self):
        """Start the bridge."""
        await self._register_forwarders()
        await self._register_telegram_handlers()

        # @self.telegram_client.on(events.NewMessage(chats=self.input_channels_entities))
        # async def handler(self, event):
        #     """Handle new messages in the specified Telegram channels."""
        #     if self.config.discord.is_healthy is False and self.config.application.internet_connected is True:
        #         # await add_to_queue(event)
        #         return

        #     await self.handle_new_message(event)
        # self.discord_client.add_listener(self._handle_discord_message, "on_message")

    async def _register_forwarders(self):
        """Register the forwarders."""
        self.logger.info("Registering forwarders...")

        if not self.telegram_client.is_connected():
            self.logger.warning("Telegram client not connected, retrying...")
            await asyncio.sleep(1)
            await self._register_forwarders()
            return

        self.logger.debug("Iterating dialogs...")
        try:
            async for dialog in self.telegram_client.iter_dialogs():

                if not isinstance(dialog.entity, Channel) and not isinstance(dialog.entity, InputChannel):
                    if self.config.telegram.log_unhandled_dialogs:
                        self.logger.warning("Excluded dialog name: %s, id: %s, type: %s",
                                        dialog.name, dialog.entity.id, type(dialog.entity))
                    continue


                for forwarder in self.config.telegram_forwarders:
                    if forwarder.tg_channel_id in {dialog.name, dialog.entity.id}: # type: ignore
                        self.input_channels_entities.append(
                            InputChannel(dialog.entity.id, dialog.entity.access_hash)) # type: ignore

                        self.logger.info("Registered Forwarder %s: Telegram channel '%s' (ID %s) with Discord Channel %s",
                                    forwarder.forwarder_name, dialog.name, dialog.entity.id, forwarder.discord_channel_id)  # type: ignore

            if len(self.input_channels_entities) <= 0:
                self.logger.error("No channel matching found, exiting...")
                sys.exit(1)

        except Exception as ex: # pylint: disable=broad-except
            self.logger.error("Error while registering forwarders: %s", ex)
            sys.exit(1)


    async def _register_telegram_handlers(self):
        """Register the Telegram handlers."""
        self.logger.info("Registering Telegram handlers...")
        self.telegram_client.add_event_handler(self._handle_new_message, events.NewMessage(chats=self.input_channels_entities))

        if self.config.telegram.subscribe_to_edit_events:
            self.telegram_client.add_event_handler(self._handle_edit_message, events.MessageEdited(chats=self.input_channels_entities))
            self.logger.info("Subscribed to Telegram edit events")

        if self.config.telegram.subscribe_to_delete_events:
            self.telegram_client.add_event_handler(self._handle_deleted_message, events.MessageDeleted(chats=self.input_channels_entities))
            self.logger.info("Subscribed to Telegram delete events")


    async def _handle_new_message(self, event):  # pylint: disable=too-many-locals
        """Handle the processing of a new Telegram message."""
        self.logger.debug("processing Telegram message: %s", event)

        if not isinstance(event.message, Message):
            self.logger.error("Event message is not a Telegram message")
            return

        message: Message = event.message

        self.logger.debug("message: %s", message)
        # self.logger.debug("message with markdown: %s", message.text)

        tg_channel_id = message.peer_id.channel_id  # type: ignore

        matching_forwarders: List[ForwarderConfig] = self.get_matching_forwarders(tg_channel_id)

        if len(matching_forwarders) < 1:
            self.logger.error(
                "No forwarders found for Telegram channel %s", tg_channel_id)
            return

        self.logger.debug("Found %s matching forwarders", len(matching_forwarders))
        self.logger.debug("Matching forwarders: %s", matching_forwarders)

        for forwarder in matching_forwarders:
            self.logger.debug("Forwarder config: %s", forwarder)


            should_forward_message = forwarder.forward_everything
            mention_everyone = forwarder.mention_everyone
            message_forward_hashtags: List[str] = []

            if not should_forward_message or forwarder.mention_override:
                message_forward_hashtags = self.get_message_forward_hashtags(
                    message)

                self.logger.debug("message_forward_hashtags: %s",
                                message_forward_hashtags)

                self.logger.debug("mention_override: %s",
                                forwarder.mention_override)

                self.logger.debug("forward_hashtags: %s",
                                forwarder.forward_hashtags)

                matching_forward_hashtags = []

                if message_forward_hashtags and forwarder.forward_hashtags:
                    matching_forward_hashtags = [
                        tag for tag in forwarder.forward_hashtags if tag["name"].lower() in message_forward_hashtags]

                if len(matching_forward_hashtags) > 0:
                    should_forward_message = True
                    mention_everyone = any(tag.get("override_mention_everyone", False)
                                        for tag in matching_forward_hashtags)

            if forwarder.excluded_hashtags:
                message_forward_hashtags = self.get_message_forward_hashtags(
                    message)

                matching_forward_hashtags = [
                    tag for tag in forwarder.excluded_hashtags if tag["name"].lower() in message_forward_hashtags]

                if len(matching_forward_hashtags) > 0:
                    should_forward_message = False

            if not should_forward_message:
                continue

            discord_channel = self.discord_client.get_channel(forwarder.discord_channel_id)  # type: ignore
            server_roles = discord_channel.guild.roles  # type: ignore

            mention_roles = self.discord_handler.get_mention_roles(message_forward_hashtags,
                                            forwarder.mention_override,
                                            self.config.discord.built_in_roles,
                                            server_roles)

            message_text = await self.process_message_text(
                message, forwarder.strip_off_links, mention_everyone, mention_roles, self.config.openai.enabled)

            if message.reply_to and message.reply_to.reply_to_msg_id:
                discord_reference = await self.discord_handler.fetch_reference(message,
                                                                forwarder.forwarder_name,
                                                                discord_channel) if message.reply_to.reply_to_msg_id else None
            else:
                discord_reference = None

            if message.media:
                sent_discord_messages = await self.handle_message_media(message,
                                                                discord_channel,
                                                                message_text,
                                                                discord_reference)
            else:
                sent_discord_messages = await self.discord_handler.forward_message(discord_channel,  # type: ignore
                                                                message_text,
                                                                reference=discord_reference)  # type: ignore

            if sent_discord_messages:
                self.logger.debug("Forwarded TG message %s to Discord channel %s",
                            sent_discord_messages[0].id, forwarder.discord_channel_id)

                self.logger.debug("Saving mapping data for forwarder %s",
                            forwarder.forwarder_name)
                main_sent_discord_message = sent_discord_messages[0]
                await self.history_manager.save_mapping_data(forwarder.forwarder_name, message.id,
                                                        main_sent_discord_message.id)
                self.logger.info("Forwarded TG message %s to Discord message %s",
                            message.id, main_sent_discord_message.id)
            else:
                await self.history_manager.save_missed_message(forwarder.forwarder_name,
                                                        message.id,
                                                        forwarder.discord_channel_id,
                                                        None)
                self.logger.error("Failed to forward TG message %s to Discord",
                            message.id, exc_info=self.config.application.debug)


    async def _handle_edit_message(self, event):
        """Handle the processing of a Telegram edited message."""
        self.logger.debug("processing Telegram edited message event: %s", event)

        if event.message is None:
            self.logger.debug("No Telegram message found, skipping...")
            return

        tg_channel_id = event.original_update.message.peer_id.channel_id
        tg_message_id = event.message.id
        tg_message_text = event.message.message


        self.logger.debug("Editing message id %s from Telegram channel_id: %s", tg_message_id, tg_channel_id)

        matching_forwarders: List[ForwarderConfig] = self.get_matching_forwarders(tg_channel_id)

        if len(matching_forwarders) < 1:
            self.logger.error(
                "No forwarders found for Telegram channel %s", tg_channel_id)
            return

        for forwarder in matching_forwarders:
            self.logger.debug("Forwarder config: %s", forwarder)

            discord_message_id = await self.history_manager.get_discord_message_id(
                forwarder.forwarder_name, tg_message_id)

            if discord_message_id is None:
                self.logger.debug("No Discord message found for Telegram message %s", tg_message_id)
                continue

            self.logger.debug("Discord message ID: %s", discord_message_id)

            discord_channel = self.discord_client.get_channel(
                forwarder.discord_channel_id)

            if discord_channel is None:
                self.logger.error("Discord channel not found, skipping...")
                continue

            self.logger.debug("Discord channel: %s", discord_channel)

            try:
                discord_message = await discord_channel.fetch_message(discord_message_id) # type: ignore

                if discord_message is None:
                    self.logger.error("Discord message not found, skipping...")
                    continue

                self.logger.debug("Discord message: %s", discord_message)

                await discord_message.edit(content=tg_message_text)
            except discord.NotFound:
                self.logger.error("Discord message not found, skipping...")
                return
            except discord.Forbidden:
                self.logger.error("Insufficient permissions to edit a message on Discord...")
                return
            except discord.HTTPException as ex:
                self.logger.error("Error while editing Discord message: %s", ex, exc_info=self.config.application.debug)
                return


    async def _handle_deleted_message(self, event):
        """Handle the deletion of a Telegram message."""
        self.logger.debug("processing Telegram deleted message event: %s", event)

        self.logger.debug("Deleted messages: %s", event.deleted_ids)
        self.logger.debug("Telegram channel_id: %s", event.original_update.channel_id)

        tg_channel_id = event.original_update.channel_id

        matching_forwarders: List[ForwarderConfig] = self.get_matching_forwarders(tg_channel_id)

        if len(matching_forwarders) < 1:
            self.logger.error(
                "No forwarders found for Telegram channel %s", tg_channel_id)
            return

        for forwarder in matching_forwarders:
            self.logger.debug("Forwarder config: %s", forwarder)

            for deleted_id in event.deleted_ids:
                discord_message_id = await self.history_manager.get_discord_message_id(
                    forwarder.forwarder_name, deleted_id)

                if discord_message_id is None:
                    self.logger.debug("No Discord message found for Telegram message %s", deleted_id)
                    continue

                self.logger.debug("Discord message ID: %s", discord_message_id)

                discord_channel = self.discord_client.get_channel(
                    forwarder.discord_channel_id)

                if discord_channel is None:
                    self.logger.error("Discord channel %s not found",
                                    forwarder.discord_channel_id)
                    return

                try:
                    discord_message = await discord_channel.fetch_message(discord_message_id) # type: ignore
                except discord.errors.NotFound:
                    self.logger.debug("Discord message %s not found", discord_message_id)
                    return

                self.logger.debug("Discord message: %s", discord_message)

                try:
                    await discord_message.delete()
                except discord.errors.NotFound:
                    self.logger.debug("Discord message %s not found", discord_message_id, exc_info=self.config.application.debug)
                    return
                except discord.errors.Forbidden:
                    self.logger.error("Discord forbade deleting message %s", discord_message_id, exc_info=self.config.application.debug)
                    return
                except discord.errors.HTTPException as ex:
                    self.logger.error("Failed deleting message %s: %s", discord_message_id, ex, exc_info=self.config.application.debug)
                    return


    def get_matching_forwarders(self, tg_channel_id: int) -> List[ForwarderConfig]:
        """Get the forwarders that match the given Telegram channel ID."""
        return [forwarder_config for forwarder_config in self.config.telegram_forwarders if tg_channel_id == forwarder_config["tg_channel_id"]]  # pylint: disable=line-too-long

    @staticmethod
    def get_message_forward_hashtags(message: Message):
        """Get forward_hashtags from a message."""
        if not message.entities:
            return []
        entities = message.entities or []
        forward_hashtags = [entity for entity in entities if isinstance(
            entity, MessageEntityHashtag)]

        return [message.message[hashtag.offset:hashtag.offset + hashtag.length] for hashtag in forward_hashtags]   # pylint: disable=line-too-long

    @staticmethod
    async def process_message_text(message: Message, 
                                strip_off_links: bool,
                                mention_everyone: bool,
                                mention_roles: List[str],
                                openai_enabled: bool) -> str:  # pylint: disable=too-many-arguments
        """Process the message text and return the processed text."""

        if message.entities:
            message_text = telegram_entities_to_markdown(message,
                                            strip_off_links)
        else:
            message_text = message.message

        if openai_enabled:
            suggestions = await OpenAIHandler.analyze_message_sentiment(message.message)
            message_text = f'{message_text}\n{suggestions}'

        if mention_everyone:
            message_text += '\n' + '@everyone'

        if mention_roles:
            mention_text = ", ".join(role for role in mention_roles)
            message_text = f"{mention_text}\n{message_text}"

        return message_text


    async def process_media_message(self,
                                    message: Message, discord_channel,
                                    message_text, discord_reference) -> List[DiscordMessage] | None:
        """Process a message that contains media."""
        file_path = await self.telegram_client.download_media(message)
        try:
            with open(file_path, "rb") as image_file:  # type: ignore
                sent_discord_messages = await self.discord_handler.forward_message(discord_channel,
                                                                message_text,
                                                                image_file=image_file,
                                                                reference=discord_reference)
                if not sent_discord_messages:
                    self.logger.error("Failed to send message to Discord")
                    return

        except OSError as ex:
            self.logger.error(
                "An error occurred while opening the file %s: %s",  file_path, ex)
            return
        finally:
            os.remove(file_path)  # type: ignore

        return sent_discord_messages

    async def handle_message_media(self, message: Message,
                                discord_channel, message_text,
                                discord_reference) -> List[DiscordMessage] | None:
        """Handle a message that contains media."""
        contains_url = any(isinstance(entity, (MessageEntityTextUrl,
                                            MessageEntityUrl))
                        for entity in message.entities or [])

        sent_discord_messages: List[DiscordMessage] | None = None

        if contains_url:
            sent_discord_messages = await self.process_url_message(discord_channel,
                                                            message_text,
                                                            discord_reference)
        else:
            sent_discord_messages = await self.process_media_message(message,
                                                                discord_channel,
                                                                message_text,
                                                                discord_reference)

        return sent_discord_messages


    async def process_url_message(self, discord_channel, message_text, discord_reference) -> List[DiscordMessage]:
        """Process a message that contains a URL."""
        sent_discord_messages = await self.discord_handler.forward_message(discord_channel,
                                                        message_text,
                                                        reference=discord_reference)
        return sent_discord_messages


    async def on_restored_connectivity(self):
        """Check and restore internet connectivity."""
        self.logger.debug("Checking for internet connectivity")
        while True:

            if self.config.application.internet_connected and self.config.telegram.is_healthy is True:
                self.logger.debug(
                    "Internet connection active and Telegram is connected, checking for missed messages")
                try:
                    last_messages = await self.history_manager.get_last_messages_for_all_forwarders()

                    self.logger.debug("Last forwarded messages: %s", last_messages)

                    for last_message in last_messages:
                        forwarder_name = last_message["forwarder_name"]
                        last_tg_message_id = last_message["telegram_id"]

                        channel_id = self.config.get_telegram_channel_by_forwarder_name(
                            forwarder_name)

                        if channel_id:
                            fetched_messages = await self.history_manager.fetch_messages_after(last_tg_message_id,
                                                                                        channel_id,
                                                                                        self.telegram_client)
                            for fetched_message in fetched_messages:

                                self.logger.debug(
                                    "Recovered message %s from channel %s", fetched_message.id, channel_id)
                                event = events.NewMessage.Event(
                                    message=fetched_message)
                                event.peer = await self.telegram_client.get_input_entity( # type: ignore
                                    channel_id)

                                if self.config.discord.is_healthy is False:
                                    self.logger.warning("Discord is not available despite the connectivty is restored, queing TG message %s",
                                                event.message.id)
                                    # await add_to_queue(event)
                                    continue
                                # delay the message delivery to avoid rate limit and flood
                                await asyncio.sleep(self.config.application.recoverer_delay)
                                self.logger.debug(
                                    "Forwarding recovered Telegram message %s", event.message.id)
                                await self._handle_new_message(event)

                except Exception as exception:  # pylint: disable=broad-except
                    self.logger.error(
                        "Failed to fetch missed messages: %s", exception, exc_info=self.config.application.debug)

            self.logger.debug("on_restored_connectivity will trigger again in for %s seconds",
                        self.config.application.healthcheck_interval)
            await asyncio.sleep(self.config.application.healthcheck_interval)
