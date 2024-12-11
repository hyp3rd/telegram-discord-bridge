
from datetime import datetime, timezone
import glob
import os
import uuid

import aiofiles
from telethon import TelegramClient
from bridge.config import Config
from bridge.logger import Logger

config = Config.get_instance()
logger = Logger.get_logger(config.application.name)


class MediaHandler():

    async def download_media(telegram_client: TelegramClient, event ) -> str:
        media_path = await event.message.download_media(os.path.join(config.application.media_store_location, str(uuid.uuid1())))
        return media_path

    async def append_message_to_file(filename, sent_discord_messages) -> None:
        logger.debug("Saving message data to append only file")
        dated_filename = filename + "-" + datetime.now().replace(tzinfo=timezone.utc).strftime('%Y-%m-%d') + ".txt"
        try:
            async with aiofiles.open(dated_filename, "a", encoding="utf-8") as file:
                for message in sent_discord_messages:
                    formatted_message = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime("%Y/%m/%d, %H:%M:%S") + ": " + message.embeds[0].description + "\n"
                    await file.write(formatted_message)

            logger.debug("Message saved successfully.")

        except Exception as ex:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while saving message: %s", ex, exc_info=config.application.debug)

    def clean_old_media() -> None:
        logger.debug("Cleaning old media files")
        try:
            files = glob.glob(config.application.media_store_location + "/" + '[0-9a-f]'*8+'-'+'[0-9a-f]'*4+'-'+'[0-9a-f]'*4+'-'+'[0-9a-f]'*4+'-'+'[0-9a-f]'*12+'.*')
            for file in files:
                os.remove(file)
        except Exception as ex:
            logger.error("Failed deleting old media file! Make sure that the storage growth does not get out of hand!")

