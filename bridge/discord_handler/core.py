"""Discord handler."""
import asyncio
import sys
from typing import List, Sequence

import discord
from discord import Message, MessageReference, TextChannel

from bridge.config import Config
from bridge.history import MessageHistoryHandler
from bridge.logger import Logger
from bridge.utils import split_message

# from discord.abc import GuildChannel, PrivateChannel,

logger = Logger.get_logger(Config().app.name)
history_manager = MessageHistoryHandler()


async def start_discord(config: Config) -> discord.Client:
    """Start the Discord client."""
    async def start_discord_client(discord_client: discord.Client, token: str):
        try:
            logger.info("Starting Discord client...")

            # setup discord logger
            discord_logging_handler = Logger.generate_handler(
                f"{config.app.name}_discord", config.logger)
            discord.utils.setup_logging(handler=discord_logging_handler)

            await discord_client.start(token)
            logger.info("Discord client started the session: %s, with identity: %s",
                        config.app.name, discord_client.user.id)

        except (discord.LoginFailure, TypeError) as login_failure:
            logger.error(
                "Error while connecting to Discord: %s", login_failure)
            sys.exit(1)
        except discord.HTTPException as http_exception:
            logger.critical(
                "Discord client failed to connect with status: %s - %s", http_exception.status, http_exception.response.reason)

    discord_client = discord.Client(intents=discord.Intents.default())
    _ = asyncio.ensure_future(
        start_discord_client(discord_client, config.discord.bot_token))

    return discord_client

#  -> Optional[Union[GuildChannel, Thread, PrivateChannel]]:


async def forward_to_discord(discord_channel: TextChannel, message_text: str,
                             image_file=None, reference: MessageReference = ...) -> List[Message]:
    """Send a message to Discord."""
    sent_messages = []
    message_parts = split_message(message_text)
    try:
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
    except discord.Forbidden:
        logger.error("Discord client doesn't have permission to send messages to channel %s",
                     discord_channel.id)
    except discord.HTTPException as http_exception:
        logger.error("Error while sending message to Discord: %s",
                     http_exception)

    return sent_messages


async def fetch_discord_reference(event, forwarder_name: str, discord_channel) -> MessageReference | None:
    """Fetch the Discord message reference."""
    discord_message_id = await history_manager.get_discord_message_id(
        forwarder_name,
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


def get_mention_roles(message_forward_hashtags: List[str],
                      mention_override: dict,
                      discord_built_in_roles: List[str],
                      server_roles: Sequence[discord.Role]) -> List[str]:
    """Get the roles to mention."""
    mention_roles = set()

    for tag in message_forward_hashtags:
        if tag.lower() in mention_override:
            logger.debug("Found mention override for tag %s: %s",
                         tag, mention_override[tag.lower()])
            for role_name in mention_override[tag.lower()]:
                if is_builtin_mention(role_name, discord_built_in_roles):
                    mention_roles.add("@" + role_name)
                else:
                    role = discord.utils.get(server_roles, name=role_name)
                    if role:
                        mention_roles.add(role.mention)

    return list(mention_roles)


def is_builtin_mention(role_name: str, discord_built_in_roles: List[str]) -> bool:
    """Check if a role name is a Discord built-in mention."""
    return role_name.lower() in discord_built_in_roles
