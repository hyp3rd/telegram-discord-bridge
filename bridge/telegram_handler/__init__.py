"""Initialize the telegram_handler module."""

try:
    from .core import (get_message_forward_hashtags, handle_message_media,
                       process_media_message, process_message_text,
                       process_url_message, start_telegram_client,
                       check_telegram_session)
except ImportError as ex:
    raise ex
