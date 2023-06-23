"""Telegram handler."""
import asyncio
import json
import os
from asyncio.events import AbstractEventLoop

from telethon import TelegramClient
from telethon.errors.rpcerrorlist import (FloodWaitError,
                                          PhoneCodeInvalidError,
                                          SessionPasswordNeededError,
                                          SessionRevokedError)

from bridge.config import Config
from bridge.logger import Logger

logger = Logger.get_logger(Config.get_instance().application.name)

tg_to_discord_message_ids = {}


# Check if the session file and the auth file exist
# to estabils the user has an active session
def check_telegram_session() -> bool:
    """Check if the Telegram session file exists."""
    config = Config.get_instance()
    if os.path.isfile(f"{config.application.name}.session") and os.path.isfile(config.api.telegram_auth_file):
        return True
    return False


async def get_auth_value_from_file(key: str) -> str | int:
    """Wait for the auth file to be created and then read a value from it."""
    config = Config.get_instance()
    # Wait for the auth file to be created with a timeout of 120 seconds
    for _ in range(config.api.telegram_auth_request_expiration):
        if os.path.isfile(config.api.telegram_auth_file):
            with open(config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                value = json.load(auth_file).get(key)
            if value:
                logger.debug("Got the Telegram %s", key)
                return value
        await asyncio.sleep(1)
    raise TimeoutError(f"Timeout waiting for {key}")


async def get_telegram_password(api_auth: bool) -> str:
    """Get the Telegram password from the API payload,
    the `TELEGRAM_PASSWORD` environment variable, or the config file."""
    telegram_password = os.getenv("TELEGRAM_PASSWORD", None)
    logger.debug("Attempting to get the Telegram password")
    if telegram_password is not None:
        return telegram_password
    config = Config.get_instance()
    if not api_auth:
        return config.telegram.password.get_secret_value()

    telegram_password = await get_auth_value_from_file('password')
    return str(telegram_password)


async def get_telegram_auth_code(api_auth: bool) -> str | int:
    """Get the Telegram auth code from the API payload, or the user's input."""
    logger.debug("Attempting to get the Telegram auth code")
    if api_auth:
        return await get_auth_value_from_file('code')

    code = input("Enter the Telegram 2FA code: ")
    if not code:
        raise ValueError("No code was entered.")

    return code


async def start_telegram_client(config: Config, event_loop: AbstractEventLoop | None = None) -> TelegramClient: # pylint: disable=too-many-statements
    """Start the Telegram client."""
    logger.info("Starting Telegram client...")

    if event_loop is None:
        logger.debug("Creating a new event loop for Telegram client")
        event_loop = asyncio.get_event_loop()

    telethon_logger = Logger.get_telethon_logger()
    telethon_logger_handler = Logger.generate_handler(
        f"{config.application.name}_telegram", config.logger)
    telethon_logger.addHandler(telethon_logger_handler)

    telegram_client = TelegramClient(
        session=config.application.name,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash,
        connection_retries=15,
        retry_delay=4,
        # base_logger=telethon_logger,
        lang_code="en",
        system_lang_code="en",
        loop=event_loop,)

    telegram_client.parse_mode = "markdown"
    await telegram_client.connect()

    logger.info("Signing in to Telegram...")

    def code_callback():
        return get_telegram_auth_code(config.api.telegram_login_enabled)

    try:
        await telegram_client.start(
            phone=config.telegram.phone, # type: ignore
            code_callback=code_callback,  # type: ignore
            password=lambda: get_telegram_password(config.api.telegram_login_enabled))  # type: ignore
    except FloodWaitError as ex:
        logger.error("Telegram client failed to start: %s",
                     ex, exc_info=config.application.debug)

        logger.warning(
            "Retrying Telegram client start in %s seconds", ex.seconds)
        await asyncio.sleep(ex.seconds)
        await telegram_client.start(
            phone=config.telegram.phone, # type: ignore
            code_callback=code_callback,  # type: ignore
            password=lambda: get_telegram_password(config.api.telegram_login_enabled))  # type: ignore

    except SessionPasswordNeededError:
        logger.error("Telegram client failed to start: %s",
                     "2FA is enabled but no password was provided",
                     exc_info=config.application.debug)
        # append to the json file that 2FA is enabled
        if os.path.isfile(config.api.telegram_auth_file) and config.api.telegram_login_enabled:
            with open(config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                auth_data = json.load(auth_file)
            auth_data["mfa_required"] = True
            auth_data["error"] = "2FA is enabled but no password was provided"
            with open(config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
                json.dump(auth_data, auth_file)
        raise

    except SessionRevokedError:
        logger.error("Telegram client failed to start: %s",
                     "The current session was revoked",
                     exc_info=config.application.debug)
        if os.path.isfile(config.api.telegram_auth_file) and config.api.telegram_login_enabled:
            # append to the json file that the session was revoked
            with open(config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                auth_data = json.load(auth_file)
            auth_data["session_revoked"] = True
            auth_data["error"] = "The current session was revoked"
            with open(config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
                json.dump(auth_data, auth_file)
        raise
    except PhoneCodeInvalidError:
        logger.error("Telegram client failed to start: %s",
                     "The phone code is invalid",
                     exc_info=config.application.debug)
        if os.path.isfile(config.api.telegram_auth_file) and config.api.telegram_login_enabled:
            # append to the json file that the phone code is invalid
            with open(config.api.telegram_auth_file, 'r', encoding="utf-8") as auth_file:
                auth_data = json.load(auth_file)
            auth_data["phone_code_invalid"] = True
            auth_data["error"] = "The phone code is invalid"
            with open(config.api.telegram_auth_file, 'w', encoding="utf-8") as auth_file:
                json.dump(auth_data, auth_file)
        raise

    # os.remove(config.telegram.auth_file)

    bot_identity = await telegram_client.get_me(input_peer=False)
    logger.info("Telegram client started the session: %s, with identity: %s",
                config.application.name, bot_identity.id)  # type: ignore

    return telegram_client


# def get_message_forward_hashtags(message: TelegramMessage):
#     """Get forward_hashtags from a message."""
#     entities = message.entities or []
#     forward_hashtags = [entity for entity in entities if isinstance(
#         entity, MessageEntityHashtag)]

#     return [message.message[hashtag.offset:hashtag.offset + hashtag.length] for hashtag in forward_hashtags]   # pylint: disable=line-too-long


# async def process_message_text(message: TelegramMessage, 
#                                strip_off_links: bool,
#                                mention_everyone: bool,
#                                mention_roles: List[str],
#                                openai_enabled: bool) -> str:  # pylint: disable=too-many-arguments
#     """Process the message text and return the processed text."""

#     if message.entities:
#         message_text = telegram_entities_to_markdown(message,
#                                          strip_off_links)
#     else:
#         message_text = message.message

#     if openai_enabled:
#         suggestions = await OpenAIHandler.analyze_message_sentiment(message.message)
#         message_text = f'{message_text}\n{suggestions}'

#     if mention_everyone:
#         message_text += '\n' + '@everyone'

#     if mention_roles:
#         mention_text = ", ".join(role for role in mention_roles)
#         message_text = f"{mention_text}\n{message_text}"

#     return message_text


# async def process_media_message(telegram_client: TelegramClient,
#                                 event, discord_channel,
#                                 message_text, discord_reference):
#     """Process a message that contains media."""
#     file_path = await telegram_client.download_media(event.message)
#     try:
#         with open(file_path, "rb") as image_file:  # type: ignore
#             sent_discord_messages = await forward_to_discord(discord_channel,
#                                                              message_text,
#                                                              image_file=image_file,
#                                                              reference=discord_reference)
#     except OSError as ex:
#         logger.error(
#             "An error occurred while opening the file %s: %s",  file_path, ex)
#         return
#     finally:
#         os.remove(file_path)  # type: ignore

#     return sent_discord_messages


# async def handle_message_media(telegram_client: TelegramClient, event,
#                                discord_channel, message_text,
#                                discord_reference) -> List[Message] | None:
#     """Handle a message that contains media."""
#     contains_url = any(isinstance(entity, (MessageEntityTextUrl,
#                                            MessageEntityUrl))
#                        for entity in event.message.entities or [])

#     if contains_url:
#         sent_discord_messages = await process_url_message(discord_channel,
#                                                           message_text,
#                                                           discord_reference)
#     else:
#         sent_discord_messages = await process_media_message(telegram_client,
#                                                             event,
#                                                             discord_channel,
#                                                             message_text,
#                                                             discord_reference)

#     return sent_discord_messages


# async def process_url_message(discord_channel, message_text, discord_reference):
#     """Process a message that contains a URL."""
#     sent_discord_messages = await forward_to_discord(discord_channel,
#                                                      message_text,
#                                                      reference=discord_reference)
#     return sent_discord_messages
