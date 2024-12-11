"""Discord embed handler."""
import os
from typing import List
import uuid

import discord
from discord import Message, TextChannel
from telethon import TelegramClient
from telethon.types import Message

from bridge.config import Config
from bridge.logger import Logger
from bridge.mediahandler import MediaHandler
from bridge.utils import split_message

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class DiscordeEmbedHandler():
    """Discord embed handler class."""

    async def forward_embed(telegram_client: TelegramClient, discord_channel: TextChannel, event, sidebarcolor: str, discord_reference: discord.MessageReference) -> List[Message]:
        sent_messages = []
        files = []
        message_parts = split_message(event.message.message)
        embed = discord.Embed(type="rich", color=discord.Color.from_str(sidebarcolor),title="test")
        try:
            if event.message.forward:
                timestamp = event.message.forward.date
                thumbnail_path = await telegram_client.download_profile_photo(event.message.forward.chat, file=str(uuid.uuid1()))
                author_path = await telegram_client.download_profile_photo(event.chat,file=str(uuid.uuid1()))
                main_url="https://t.me/" + event.message.forward.chat.username + "/" + str(event.message.forward.channel_post)
                author_url="https://t.me/" + event.chat.username + "/" + str(event._message_id)
                main_title=event.message.forward.chat.title
                author_title=event.chat.title

                embed.url=main_url
                embed.timestamp=timestamp
                embed.title=main_title

                author_file=discord.File(str(author_path))
                thumbnail_file=discord.File(str(thumbnail_path))
                files.append(author_file)
                files.append(thumbnail_file)
                embed.set_author(name=author_title,url=author_url,icon_url="attachment://"+str(author_path))
                embed.set_thumbnail(url="attachment://"+str(thumbnail_path))

            else:
                timestamp = event.message.date
                main_url="https://t.me/" + event.chat.username + "/" + str(event._message_id)
                main_title=event.chat.title
                author_path = await telegram_client.download_profile_photo(entity=event.chat,file=str(uuid.uuid1()))

                embed.timestamp=timestamp
                embed.url = main_url
                embed.title=main_title

                author_file=discord.File(str(author_path))
                files.append(author_file)
                embed.set_thumbnail(url="attachment://"+str(author_path))
            if event.message.media:
                media_path = await MediaHandler.download_media(telegram_client, event)
                if os.stat(media_path).st_size < config.application.media_max_size_bytes:  
                    discord_file = discord.File(str(media_path))
                    files.append(discord_file)
                    if hasattr(event.message.media, 'photo'):
                        embed.set_image(url="attachment://"+str(os.path.basename(media_path)))
                else:
                    embed.set_footer(text="MEDIA TOO BIG", icon_url=config.application.media_max_size_photo)

            for message_part in message_parts:
                    embed.description=message_part
                    sent_message = await discord_channel.send(embed=embed, files=files, reference=discord_reference)
                    sent_messages.append(sent_message)
        except Exception as ex:
            logger.error("An error occured while sending a message to discord.")
            logger.error(str(ex))
            return sent_messages
        finally:
            os.remove(author_path)
        return sent_messages
    